"""The hog market behind the price: cutout, packer spread, slaughter, weights, and plain-rule
signals. Pure: DataFrames in, DataFrames and dicts out.

Packer spread (gross) = pork cutout + by-product (drop) value − Lean Hog Index, all $/cwt
carcass: what a packer gets for the whole hog minus what it paid, before plant costs.
Per head = spread × average carcass weight / 100. It's a relative gauge: wide spreads mean
packers can afford to bid more for hogs.

Signals are deliberately simple and written out (`rule`) so anyone can check them. "good"
means supportive of hog prices (good for a hog seller), "bad" the opposite.
"""

from dataclasses import dataclass
from typing import Literal, cast

import numpy as np
import pandas as pd

from hogproj.text import ordinal

ALL_TYPES = "Prod. Sold (All Purchase Types)"
Tone = Literal["good", "bad", "neutral"]


def daily(hg201: pd.DataFrame, index: pd.DataFrame, cutout: pd.DataFrame,
          drop: pd.DataFrame | None = None) -> pd.DataFrame:  # fmt: skip
    """One row per slaughter day: index, cutout, by-product (drop) value, packer spread,
    producer-sold head and carcass weight.

    With `drop` (weekly, $/cwt carcass equivalent) the spread is cutout + drop − index: what a
    packer gets for the whole hog minus what it paid. Days before the drop series starts use
    its first value (it moves within a few dollars), so the history stays comparable.
    """
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
    df["drop"] = 0.0
    if drop is not None and not drop.empty:
        dv = pd.DataFrame(
            {
                "date": pd.to_datetime(drop["week_ending"]).to_numpy(),
                "drop": drop["drop_usd_per_cwt_carcass"].to_numpy(dtype=float),
            }
        )
        dv = dv.dropna().sort_values("date")
        df = pd.merge_asof(df.drop(columns="drop"), dv, on="date", direction="backward")
        df["drop"] = df["drop"].fillna(float(dv["drop"].iloc[0]))
    df["spread"] = df["cutout"] + df["drop"] - df["index"]
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


def wasde_outlook(w: pd.DataFrame, today: pd.Timestamp) -> dict | None:
    """USDA's pork production for the next two quarters vs the same quarters a year earlier,
    and its barrow/gilt price forecast for the next quarter ($/cwt live)."""
    if w is None or w.empty:
        return None
    q_now = (today.year, (today.month - 1) // 3 + 1)

    def nxt(y: int, q: int) -> tuple[int, int]:
        return (y + 1, 1) if q == 4 else (y, q + 1)

    ahead = [nxt(*q_now), nxt(*nxt(*q_now))]
    prod = w[w["series"] == "pork_production_mlb"].set_index(["year", "quarter"])["value"]
    price = w[w["series"] == "barrows_gilts_usd_cwt_live"].set_index(["year", "quarter"])["value"]
    try:
        now = sum(float(prod.loc[q]) for q in ahead)
        before = sum(float(prod.loc[(y - 1, q)]) for y, q in ahead)
    except KeyError:
        return None
    first = ahead[0]
    return {"pct": now / before - 1, "quarters": ahead,
            "price_next_q": float(price.loc[first]) if first in price.index else None,
            "report": str(w["report"].iloc[0])}  # fmt: skip


def storage_vs_normal(cs: pd.DataFrame, years: int = 5) -> dict | None:
    """Latest month's pork in cold storage vs the average of the same month in the prior
    `years` years."""
    if cs is None or cs.empty:
        return None
    month = pd.to_datetime(cs["month"])
    last = _ts(month.max())
    now = float(cs.loc[month == last, "pork_stocks_mlb"].iloc[0])
    prior = cs[(month.dt.month == last.month) & (month.dt.year < last.year)
               & (month.dt.year >= last.year - years)]  # fmt: skip
    if prior.empty:
        return None
    avg = float(prior["pork_stocks_mlb"].mean())
    return {"month": last, "now": now, "avg": avg, "pct": now / avg - 1, "years": len(prior)}


def retail_vs_year_ago(retail: pd.DataFrame, weeks: int = 4) -> dict | None:
    """National grocery pork feature activity over the last `weeks` vs the same weeks a year
    earlier (USDA's own last-year columns)."""
    if retail is None or retail.empty:
        return None
    nat = retail[retail["region"] == "NATIONAL"].sort_values("week_ending").tail(weeks)
    if nat.empty or nat["activity_index_last_year"].sum() == 0:
        return None
    pct = nat["activity_index"].sum() / nat["activity_index_last_year"].sum() - 1
    return {"pct": float(pct), "feature_rate": float(nat["feature_rate"].mean()),
            "week": _ts(nat["week_ending"].iloc[-1])}  # fmt: skip


def fi_weekly(fi: pd.DataFrame) -> pd.DataFrame:
    """Federally inspected hog slaughter by week (ending Saturday) with USDA's year-ago head."""
    x = fi.assign(date=pd.to_datetime(fi["date"])).set_index("date")
    w = x[["head", "head_year_ago"]].resample("W-SAT").sum(min_count=1)
    return w.dropna(subset=["head"]).reset_index().rename(columns={"date": "week_ending"})


def fi_vs_year_ago(fi: pd.DataFrame | None, days: int = 28) -> dict | None:
    """All federally inspected hogs over the last `days` days vs the same days a year ago."""
    if fi is None or fi.empty:
        return None
    d = pd.to_datetime(fi["date"])
    x = fi[d > d.max() - pd.Timedelta(days=days)].dropna(subset=["head", "head_year_ago"])
    if x.empty or x["head_year_ago"].sum() == 0:
        return None
    return {"pct": float(x["head"].sum() / x["head_year_ago"].sum() - 1),
            "head": float(x["head"].sum()), "end": _ts(d.max())}  # fmt: skip


def sow_slaughter_vs_year_ago(fw: pd.DataFrame | None, weeks: int = 4) -> dict | None:
    """Sows slaughtered over the last `weeks` reported weeks vs the same weeks a year earlier:
    more culls than a year ago means the breeding herd is being cut (fewer pigs later)."""
    if fw is None or fw.empty:
        return None
    sows = fw[fw["class"] == "Sows"].assign(week_ending=lambda x: pd.to_datetime(x["week_ending"]))
    sows = sows.set_index("week_ending")["head"].sort_index()
    last = sows.tail(weeks)
    ago = sows.reindex(last.index - pd.Timedelta(days=364))
    if len(last) < weeks or ago.isna().any() or ago.sum() == 0:
        return None
    return {"pct": float(last.sum() / ago.sum() - 1), "per_week": float(last.mean()),
            "end": _ts(last.index[-1])}  # fmt: skip


def exports_ytd(trade: pd.DataFrame | None, countries: int = 5) -> dict | None:
    """Pork exports so far this year vs the same months last year, in total and for the
    biggest buyers (carcass weight)."""
    if trade is None or trade.empty:
        return None
    ex = trade[(trade["flow"] == "Exports") & (trade["commodity"] == "Pork")]
    ex = ex.assign(month=pd.to_datetime(ex["month"]))
    last = ex["month"].max()
    this = ex[(ex["month"].dt.year == last.year) & (ex["month"] <= last)]
    prev = ex[(ex["month"].dt.year == last.year - 1) & (ex["month"].dt.month <= last.month)]
    a = this.groupby("country")["amount"].sum()
    b = prev.groupby("country")["amount"].sum()
    if "World total" not in a or not b.get("World total"):
        return None
    top = a.drop("World total").sort_values(ascending=False).head(countries)
    by = pd.DataFrame({"ytd": top, "ytd_last_year": b.reindex(top.index)})
    by["pct"] = by["ytd"] / by["ytd_last_year"] - 1
    by["share"] = by["ytd"] / a["World total"]
    return {"pct": float(a["World total"] / b["World total"] - 1), "through": _ts(last),
            "total_mlb": float(a["World total"]) / 1000, "by_country": by}  # fmt: skip


def export_sales_weekly(es: pd.DataFrame | None, countries: int = 5) -> dict | None:
    """USDA weekly export sales of pork: shipments so far this year vs the same weeks last year
    (in total and for the biggest buyers), the last 4 weeks' shipments and net new sales vs a
    year earlier, and the latest week's top buyers. Metric tons."""
    if es is None or es.empty:
        return None
    x = es.assign(week_ending=pd.to_datetime(es["week_ending"]))
    last = x["week_ending"].max()
    wk = x.groupby("week_ending")[["exports_mt", "net_sales_mt"]].sum().sort_index()
    year_ago = last - pd.Timedelta(days=364)
    this_ytd = x[(x["week_ending"].dt.year == last.year)]
    prev_ytd = x[(x["week_ending"].dt.year == last.year - 1) & (x["week_ending"] <= year_ago)]
    a, b = this_ytd["exports_mt"].sum(), prev_ytd["exports_mt"].sum()
    if not b:
        return None
    four = wk[wk.index > last - pd.Timedelta(days=28)]
    four_ago = wk[(wk.index > year_ago - pd.Timedelta(days=28)) & (wk.index <= year_ago)]
    by_a = this_ytd.groupby("country")["exports_mt"].sum().drop("Unknown", errors="ignore")
    by_b = prev_ytd.groupby("country")["exports_mt"].sum()
    top = by_a.sort_values(ascending=False).head(countries)
    by = pd.DataFrame({"ytd": top, "ytd_last_year": by_b.reindex(top.index)})
    by["pct"] = by["ytd"] / by["ytd_last_year"] - 1
    by["share"] = by["ytd"] / a
    week = x[x["week_ending"] == last].groupby("country")["net_sales_mt"].sum()
    return {
        "pct": float(a / b - 1), "through": _ts(last), "ytd_mt": float(a),
        "by_country": by, "weekly": wk,
        "ship_4wk_pct": float(four["exports_mt"].sum() / four_ago["exports_mt"].sum() - 1)
        if four_ago["exports_mt"].sum() else float("nan"),
        "sales_4wk_pct": float(four["net_sales_mt"].sum() / four_ago["net_sales_mt"].sum() - 1)
        if four_ago["net_sales_mt"].sum() else float("nan"),
        "week_sales_mt": float(week.sum()),
        "week_top": week.drop("Unknown", errors="ignore").sort_values(ascending=False).head(3),
        "label": f"week ending {last:%b} {last.day}",
    }  # fmt: skip


def farmer_share(spreads: pd.DataFrame | None) -> dict | None:
    """Net farm value as a share of the retail pork dollar: latest month and a year earlier."""
    if spreads is None or spreads.empty:
        return None
    w = spreads.pivot_table(index="month", columns="item", values="value").sort_index()
    if not {"net_farm", "retail"} <= set(w.columns):
        return None
    share = (w["net_farm"] / w["retail"]).dropna()
    last = share.index[-1]
    ago = share.get(last - pd.DateOffset(years=1))
    return {
        "share": float(share.iloc[-1]),
        "year_ago": None if ago is None else float(ago),
        "month": _ts(last),
        "retail": float(w["retail"].iloc[-1]),
        "wholesale": float(w["wholesale"].iloc[-1]),
        "net_farm": float(w["net_farm"].iloc[-1]),
    }


def signals(d: pd.DataFrame, supply_pct: float | None = None,
            wasde: dict | None = None, storage: dict | None = None,
            retail: dict | None = None, fi: dict | None = None, sows: dict | None = None,
            exports: dict | None = None) -> list[Signal]:  # fmt: skip
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
        out.append(Signal("Packer spread", f"{_fmt_usd(now)}/head, 5-day avg",
                          read + f" ({ordinal(rank)} "
                          "percentile since 2020)", tone,
                          "Top 25% of history = supportive; bottom 25% = negative"))  # fmt: skip

    # 2. Cutout trend, 4 weeks.
    cut = pd.DataFrame(d[d["cutout"].notna()])
    if len(cut) > 30:
        end = _ts(cut["date"].max())
        now = window(d, "cutout", end, 7)
        before = window(d, "cutout", _ts(end - pd.Timedelta(days=28)), 7)
        pct = now / before - 1
        if np.isnan(pct):
            pct = 0.0  # no comparison window: treat as steady rather than print "nan%"
        tone = "good" if pct >= 0.03 else "bad" if pct <= -0.03 else "neutral"
        read = {"good": "Pork demand is pulling the cutout higher.",
                "bad": "The cutout is sliding; packers will push hog bids lower.",
                "neutral": "The cutout is steady."}[tone]  # fmt: skip
        out.append(Signal("Pork cutout", f"{_fmt_usd(now)}/cwt, 5-day avg",
                          read + f" ({pct:+.1%} in 4 "
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

    # 4. Slaughter vs a year ago, 4 weeks: all federally inspected hogs when available (packer-
    # owned included), else producer-sold barrows and gilts from LMR.
    s = vs_year_ago(d, "head", how="sum")
    who = "producer-sold barrows and gilts"
    if fi is not None:
        s, who = {"pct": fi["pct"]}, "all federally inspected hogs"
    if not np.isnan(s["pct"]):
        tone = "bad" if s["pct"] >= 0.03 else "good" if s["pct"] <= -0.03 else "neutral"
        read = {"bad": "More hogs are coming to market than a year ago.",
                "good": "Fewer hogs are coming to market than a year ago.",
                "neutral": "Slaughter is close to last year."}[tone]  # fmt: skip
        out.append(Signal("Slaughter", f"{s['pct']:+.1%}".replace("-", "−") + " vs last year",
                          read + f" (last 4 weeks, {who})", tone,
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
    # 7. Pork in cold storage vs the 5-year average for the month.
    if storage is not None:
        p = storage["pct"]
        tone = "bad" if p >= 0.05 else "good" if p <= -0.05 else "neutral"
        read = {
            "bad": "More pork is in storage than usual, which weighs on prices.",
            "good": "Less pork is in storage than usual, so the pipeline is lean.",
            "neutral": "Pork in storage is about normal for the month.",
        }[tone]
        out.append(Signal("Cold storage", f"{p:+.0%}".replace("-", "−") + " vs 5-yr avg",
                          read + f" ({storage['month']:%B} stocks {storage['now']:,.0f}M lb)",
                          tone, "5%+ above the 5-year average for the month = negative; 5%+ "
                          "below = supportive"))  # fmt: skip

    # 8. Retail demand: grocery pork features vs a year ago.
    if retail is not None:
        p = retail["pct"]
        tone = "good" if p >= 0.05 else "bad" if p <= -0.05 else "neutral"
        read = {
            "good": "Grocers are featuring pork more than a year ago.",
            "bad": "Grocers are featuring pork less than a year ago.",
            "neutral": "Grocery pork features are close to last year.",
        }[tone]
        out.append(Signal("Retail features", f"{p:+.0%}".replace("-", "−") + " vs last year",
                          read + f" ({retail['feature_rate']:.0%} of stores featured pork, "
                          "4-week average)",
                          tone, "5%+ more feature activity than a year ago = supportive; 5%+ "
                          "less = negative"))  # fmt: skip

    # 6. USDA's own pork production forecast (WASDE), next two quarters.
    if wasde is not None:
        p = round(wasde["pct"], 3)  # judge the number as shown, so "−1.0%" never reads "same"
        tone = "bad" if p >= 0.01 else "good" if p <= -0.01 else "neutral"
        q = " and ".join(f"Q{qq} {yy}" for yy, qq in wasde["quarters"])
        read = {
            "bad": f"USDA forecasts more pork than a year earlier in {q}.",
            "good": f"USDA forecasts less pork than a year earlier in {q}.",
            "neutral": f"USDA forecasts about the same pork as a year earlier in {q}.",
        }[tone]
        out.append(Signal("USDA pork outlook", f"{p:+.1%}".replace("-", "−") + " production",
                          read + f" ({wasde['report']} WASDE)", tone,
                          "1%+ more pork than a year ago = negative; 1%+ less = "
                          "supportive"))  # fmt: skip

    # 9. Export demand: pork exports so far this year vs last year.
    if exports is not None:
        p = exports["pct"]
        tone = "good" if p >= 0.03 else "bad" if p <= -0.03 else "neutral"
        read = {"good": "Export buyers are taking more U.S. pork than last year.",
                "bad": "Export buyers are taking less U.S. pork than last year.",
                "neutral": "Pork exports are close to last year."}[tone]  # fmt: skip
        out.append(Signal("Pork exports", f"{p:+.1%}".replace("-", "−") + " vs last year",
                          read + " (" + (exports.get("label")
                                         or f"through {exports['through']:%B}") + ")",
                          tone,
                          "3%+ more than a year ago so far this year = supportive; 3%+ less = "
                          "negative"))  # fmt: skip

    # 10. Sow slaughter: is the breeding herd being cut?
    if sows is not None:
        p = sows["pct"]
        tone = "good" if p >= 0.05 else "bad" if p <= -0.05 else "neutral"
        read = {"good": "More sows are going to market than a year ago: the herd is being cut, "
                        "so fewer pigs later.",
                "bad": "Fewer sows are going to market than a year ago: the herd is being "
                       "kept or grown, so more pigs later.",
                "neutral": "Sow slaughter is close to last year."}[tone]  # fmt: skip
        out.append(Signal("Sow slaughter", f"{p:+.1%}".replace("-", "−") + " vs last year",
                          read + f" ({sows['per_week']:,.0f} a week, 4 weeks to "
                          f"{sows['end']:%b %d})", tone,
                          "5%+ more sows culled than a year ago = supportive later (herd "
                          "shrinking); 5%+ fewer = negative later"))  # fmt: skip
    return out


def overall(sigs: list[Signal]) -> tuple[Tone, str]:
    score = sum(1 if s.tone == "good" else -1 if s.tone == "bad" else 0 for s in sigs)
    if score >= 2:
        return "good", f"{score} more supportive than negative signals"
    if score <= -2:
        return "bad", f"{-score} more negative than supportive signals"
    return "neutral", "signals are mixed"


def wasde_to_index_ratio(w: pd.DataFrame, index: pd.DataFrame) -> float | None:
    """Lean Hog Index (carcass, net) ÷ WASDE barrow/gilt price (live, base), averaged over the
    quarters WASDE reports as actual — so USDA's live forecast can be read as an index price."""
    if w is None or w.empty:
        return None
    pr = w[(w["series"] == "barrows_gilts_usd_cwt_live") & (~w["projected"].astype(bool))]
    d = pd.to_datetime(index["index_date"])
    v = index["lean_hog_index_usd_per_cwt_carcass"].to_numpy(dtype=float)
    ratios = []
    for r in pr.to_dict("records"):
        q = (d.dt.year == int(r["year"])) & ((d.dt.month - 1) // 3 + 1 == int(r["quarter"]))
        if q.sum() > 30:
            ratios.append(float(v[q.to_numpy()].mean()) / float(r["value"]))
    return float(np.mean(ratios)) if ratios else None


def wasde_contract_prices(contracts: list, expiries: list, w: pd.DataFrame,
                          ratio: float) -> dict:  # fmt: skip
    """Index-equivalent price for each contract from USDA's forecast for its expiry quarter.
    Contracts past WASDE's horizon are left out (the caller keeps its own estimate)."""
    pr = w[w["series"] == "barrows_gilts_usd_cwt_live"].set_index(["year", "quarter"])["value"]
    out = {}
    for k, exp in zip(contracts, expiries, strict=True):
        q = (exp.year, (exp.month - 1) // 3 + 1)
        if q in pr.index:
            out[k] = round(float(pr.loc[q]) * ratio * 4) / 4
    return out


def wasde_accuracy(hist: pd.DataFrame) -> pd.DataFrame:
    """How far USDA's barrow/gilt price forecasts landed from what was later reported, by how
    many quarters ahead they were made. Rows: horizon (0 = the report's own quarter, 1 = the
    next), forecasts, mean absolute miss and bias ($/cwt live; positive = forecasts ran high)."""
    pr = hist[hist["series"] == "barrows_gilts_usd_cwt_live"].copy()
    if pr.empty:
        return pd.DataFrame(columns=["horizon", "n", "mae", "bias"])
    pr["projected"] = pr["projected"].astype(str).str.lower().isin(["true", "1"])
    actual = pr[~pr["projected"]].drop_duplicates(["year", "quarter"], keep="last")
    actual = actual.set_index(["year", "quarter"])["value"]
    rows = []
    for r in pr[pr["projected"]].to_dict("records"):
        rep = pd.to_datetime("1 " + str(r["report"]))
        rep_q = rep.year * 4 + (rep.month - 1) // 3
        h = int(r["year"]) * 4 + int(r["quarter"]) - 1 - rep_q
        key = (int(r["year"]), int(r["quarter"]))
        if h >= 0 and key in actual.index:
            rows.append({"horizon": h, "error": float(r["value"]) - float(actual.loc[key])})
    if not rows:
        return pd.DataFrame(columns=["horizon", "n", "mae", "bias"])
    e = pd.DataFrame(rows)
    g = e.groupby("horizon")["error"]
    return pd.DataFrame({"n": g.size(), "mae": g.apply(lambda x: x.abs().mean()),
                         "bias": g.mean()}).reset_index()  # fmt: skip
