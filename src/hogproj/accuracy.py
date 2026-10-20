"""How far to trust the app's own hog price estimate. Replays the seasonal estimate (today's
index moved by the typical seasonal pattern, the default for contract prices) from the start
of every month since 2022, using only the data available then, and compares it with what the
Lean Hog Index actually averaged 1 to 9 months later, and with simply assuming no change.
Pure: index in, error table out.
"""

import numpy as np
import pandas as pd

from hogproj.markets import seasonal_factors, seasonal_price_on

HORIZONS = (1, 2, 3, 4, 5, 6, 7, 8, 9)  # months ahead


def backtest(index: pd.DataFrame, start: str = "2022-01-01") -> pd.DataFrame:
    """One row per (month the estimate was made, months ahead): estimate, no-change and actual
    monthly average index, $/cwt carcass."""
    ix = index.assign(index_date=pd.to_datetime(index["index_date"])).sort_values("index_date")
    s = ix.set_index("index_date")["lean_hog_index_usd_per_cwt_carcass"]
    monthly = s.resample("MS").mean()
    last_full = monthly.index.max() - pd.DateOffset(months=1)  # the latest month may be partial
    rows = []
    for made in pd.date_range(start, monthly.index.max(), freq="MS"):
        hist = ix[ix["index_date"] < made]
        f = seasonal_factors(hist)
        if f.empty or len(hist) < 5:
            continue
        now = float(hist["lean_hog_index_usd_per_cwt_carcass"].iloc[-5:].mean())
        for h in HORIZONS:
            target = made + pd.DateOffset(months=h)
            if target > last_full or pd.isna(monthly.get(target)):
                continue
            mid = (target + pd.Timedelta(days=14)).date()
            est = float(seasonal_price_on([mid], made.date(), now, f)[0])
            rows.append({"made": made, "months_ahead": h, "estimate": est, "no_change": now,
                         "actual": float(monthly[target])})  # fmt: skip
    return pd.DataFrame(rows)


def summary(bt: pd.DataFrame) -> pd.DataFrame:
    """By months ahead: count, average miss of the estimate and of no-change, bias (+ = the
    estimate ran high) and the miss that 8 in 10 estimates stayed within."""
    if bt.empty:
        return pd.DataFrame(columns=["months_ahead", "n", "miss", "miss_no_change", "bias",
                                     "within_8_in_10", "better_than_no_change"])  # fmt: skip
    e = bt["estimate"] - bt["actual"]
    n_ = bt["no_change"] - bt["actual"]
    g = pd.DataFrame({"h": bt["months_ahead"], "e": e, "n": n_}).groupby("h")
    out = pd.DataFrame({
        "n": g["e"].size(), "miss": g["e"].apply(lambda x: float(np.abs(x).mean())),
        "miss_no_change": g["n"].apply(lambda x: float(np.abs(x).mean())),
        "bias": g["e"].mean(),
        "within_8_in_10": g["e"].apply(lambda x: float(np.percentile(np.abs(x), 80))),
    })  # fmt: skip
    out["better_than_no_change"] = 1 - out["miss"] / out["miss_no_change"]
    return out.rename_axis("months_ahead").reset_index()


def band_cwt(summ: pd.DataFrame, months_ahead: float) -> float | None:
    """The 8-in-10 miss ($/cwt carcass) for an estimate this many months ahead (nearest
    horizon backtested; beyond the last one, the last one)."""
    if summ.empty:
        return None
    h = int(min(max(round(months_ahead), int(summ["months_ahead"].min())),
                int(summ["months_ahead"].max())))  # fmt: skip
    row = summ[summ["months_ahead"] == h]
    return float(row["within_8_in_10"].iloc[0]) if len(row) else None
