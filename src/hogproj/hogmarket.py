"""The hog market behind the price: cutout, packer spread, slaughter, weights, and plain-rule
signals. Pure: DataFrames in, DataFrames and dicts out.

Packer spread (gross) = pork cutout − Lean Hog Index, both $/cwt carcass, so it's the wholesale
value of a carcass minus what packers paid for it — before plant costs and by-product credit.
Per head = spread × average carcass weight / 100. It's a relative gauge: wide spreads mean
packers can afford to bid more for hogs.

Signals are deliberately simple and written out (`rule`) so anyone can check them. "good"
means supportive of hog prices (good for a hog seller), "bad" the opposite.
"""

from dataclasses import dataclass
from typing import Literal, cast

import numpy as np
import pandas as pd

ALL_TYPES = "Prod. Sold (All Purchase Types)"
Tone = Literal["good", "bad", "neutral"]


def daily(hg201: pd.DataFrame, index: pd.DataFrame, cutout: pd.DataFrame) -> pd.DataFrame:
    """One row per slaughter day: index, cutout, spread, producer-sold head and carcass weight."""
    allp = pd.DataFrame(hg201[hg201["purchase_type"] == ALL_TYPES])
    vol = pd.DataFrame(
        {
            "date": pd.to_datetime(allp["slaughter_date"]).to_numpy(),
            "head": allp["head_count"].to_numpy(dtype=float),
            "weight_lb": allp["avg_weight_lb_carcass"].to_numpy(dtype=float),
        }
    ).drop_duplicates("date", keep="last")
    idx = pd.DataFrame(
        {
            "date": pd.to_datetime(index["index_date"]).to_numpy(),
            "index": index["lean_hog_index_usd_per_cwt_carcass"].to_numpy(dtype=float),
        }
    )
    cut = pd.DataFrame(
        {
            "date": pd.to_datetime(cutout["date"]).to_numpy(),
            "cutout": cutout["carcass"].to_numpy(dtype=float),
            "belly": cutout["belly"].to_numpy(dtype=float),
            "loin": cutout["loin"].to_numpy(dtype=float),
            "ham": cutout["ham"].to_numpy(dtype=float),
        }
    )
    df = vol.merge(idx, on="date", how="outer").merge(cut, on="date", how="outer")
    df = df.sort_values("date").reset_index(drop=True)
    df["spread"] = df["cutout"] - df["index"]
    df["spread_per_head"] = df["spread"] * df["weight_lb"] / 100
    return df


def weekly(d: pd.DataFrame) -> pd.DataFrame:
    """Weeks ending Friday: averages for prices, total head, head-weighted carcass weight."""
    x = d.set_index("date")
    w = pd.DataFrame(
        {
            "index": x["index"].resample("W-FRI").mean(),
            "cutout": x["cutout"].resample("W-FRI").mean(),
            "spread": x["spread"].resample("W-FRI").mean(),
            "spread_per_head": x["spread_per_head"].resample("W-FRI").mean(),
            "head": x["head"].resample("W-FRI").sum(min_count=1),
            "days": x["head"].resample("W-FRI").count(),
            "weight_lb": (x["head"] * x["weight_lb"]).resample("W-FRI").sum(min_count=1)
            / x["head"].resample("W-FRI").sum(min_count=1),
        }
    )
    w.index.name = "week_ending"
    return w.reset_index()


def _ts(x: object) -> pd.Timestamp:
    return cast(pd.Timestamp, pd.Timestamp(str(x)))


def window(d: pd.DataFrame, col: str, end: pd.Timestamp, days: int, how: str = "mean") -> float:
    """Mean (or sum) of `col` over the `days` up to and including `end`."""
    m = (d["date"] > end - pd.Timedelta(days=days)) & (d["date"] <= end)
    v = d.loc[m, col].to_numpy(dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return float("nan")
    return float(v.sum() if how == "sum" else v.mean())


def vs_year_ago(d: pd.DataFrame, col: str, days: int = 28, how: str = "mean") -> dict:
    """Last `days` vs the same days a year earlier (364 days back, so weekdays line up)."""
    have = pd.DataFrame(d[d[col].notna()])
    end = _ts(have["date"].max())
    now = window(d, col, end, days, how)
    before = window(d, col, _ts(end - pd.Timedelta(days=364)), days, how)
    return {"now": now, "year_ago": before, "change": now - before,
            "pct": now / before - 1 if before else float("nan"), "end": end}  # fmt: skip


def percentile(value: float, history: np.ndarray) -> float:
    h = history[~np.isnan(history)]
    return float((h < value).mean() * 100) if len(h) else float("nan")


@dataclass
class Signal:
    name: str
    value: str  # the number, formatted
    read: str  # one sentence
    tone: Tone
    rule: str  # how the tone was decided


def _fmt_usd(x: float) -> str:
    return ("−" if x < 0 else "") + f"${abs(x):,.2f}"


def signals(d: pd.DataFrame, supply_pct: float | None = None) -> list[Signal]:
    out: list[Signal] = []

    # 1. Packer spread per head vs its own history.
    sp = pd.DataFrame(d[d["spread_per_head"].notna()])
    if len(sp) > 60:
        end = _ts(sp["date"].max())
        now = window(d, "spread_per_head", end, 7)
        rank = percentile(now, np.asarray(sp["spread_per_head"].rolling(5).mean(), dtype=float))
        tone: Tone = "good" if rank >= 75 else "bad" if rank <= 25 else "neutral"
        read = {
            "good": "Packers' margins are wide, so they can afford to bid up for hogs.",
            "bad": "Packers' margins are thin, which limits what they'll pay for hogs.",
            "neutral": "Packers' margins are about normal.",
        }[tone]
        out.append(Signal("Packer spread", f"{_fmt_usd(now)}/head", read + f" ({rank:.0f}th "
                          "percentile since 2020)", tone,
                          "Top 25% of history = supportive; bottom 25% = negative"))  # fmt: skip

    # 2. Cutout trend, 4 weeks.
    cut = pd.DataFrame(d[d["cutout"].notna()])
    if len(cut) > 30:
        end = _ts(cut["date"].max())
        now = window(d, "cutout", end, 7)
        before = window(d, "cutout", _ts(end - pd.Timedelta(days=28)), 7)
        pct = now / before - 1
        tone = "good" if pct >= 0.03 else "bad" if pct <= -0.03 else "neutral"
        read = {"good": "Pork demand is pulling the cutout higher.",
                "bad": "The cutout is sliding; packers will push hog bids lower.",
                "neutral": "The cutout is steady."}[tone]  # fmt: skip
        out.append(Signal("Pork cutout", f"{_fmt_usd(now)}/cwt", read + f" ({pct:+.1%} in 4 "
                          "weeks)".replace("-", "−"), tone,
                          "Up 3%+ in 4 weeks = supportive; down 3%+ = negative"))  # fmt: skip

    # 3. Carcass weights vs a year ago.
    w = vs_year_ago(d, "weight_lb")
    if not np.isnan(w["change"]):
        tone = "bad" if w["change"] >= 2 else "good" if w["change"] <= -2 else "neutral"
        read = {"bad": "Hogs are heavier than last year: marketings are falling behind.",
                "good": "Hogs are lighter than last year: producers are current.",
                "neutral": "Weights are in line with last year."}[tone]  # fmt: skip
        out.append(Signal("Carcass weights", f"{w['now']:.1f} lb",
                          read + f" ({w['change']:+.1f} lb)".replace("-", "−"), tone,
                          "2+ lb heavier than a year ago = negative; 2+ lb lighter = "
                          "supportive"))  # fmt: skip

    # 4. Slaughter vs a year ago (producer-sold head, 4 weeks).
    s = vs_year_ago(d, "head", how="sum")
    if not np.isnan(s["pct"]):
        tone = "bad" if s["pct"] >= 0.03 else "good" if s["pct"] <= -0.03 else "neutral"
        read = {"bad": "More hogs are coming to market than a year ago.",
                "good": "Fewer hogs are coming to market than a year ago.",
                "neutral": "Slaughter is close to last year."}[tone]  # fmt: skip
        out.append(Signal("Slaughter", f"{s['pct']:+.1%}".replace("-", "−") + " vs last year",
                          read + " (last 4 weeks, producer-sold barrows and gilts)", tone,
                          "3%+ above a year ago = negative; 3%+ below = supportive"))  # fmt: skip

    # 5. Supply ahead (NASS Hogs and Pigs).
    if supply_pct is not None and not np.isnan(supply_pct):
        tone = "bad" if supply_pct >= 0.01 else "good" if supply_pct <= -0.01 else "neutral"
        read = {"bad": "USDA counts more hogs coming over the next six months.",
                "good": "USDA counts fewer hogs coming over the next six months.",
                "neutral": "USDA's count of hogs coming is close to last year."}[tone]  # fmt: skip
        out.append(Signal("Supply ahead", f"{supply_pct:+.1%}".replace("-", "−") + " vs last year",
                          read, tone, "1%+ more hogs than a year ago = negative; 1%+ fewer = "
                          "supportive"))  # fmt: skip
    return out


def overall(sigs: list[Signal]) -> tuple[Tone, str]:
    score = sum(1 if s.tone == "good" else -1 if s.tone == "bad" else 0 for s in sigs)
    if score >= 2:
        return "good", f"{score} more supportive than negative signals"
    if score <= -2:
        return "bad", f"{-score} more negative than supportive signals"
    return "neutral", "signals are mixed"
