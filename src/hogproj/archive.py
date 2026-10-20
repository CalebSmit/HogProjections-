"""The weekly record: every series the app tracks, one row per week (ending Friday), since 2020.
Pure: DataFrames in, DataFrames out.
"""

import numpy as np
import pandas as pd

COLUMNS = {
    "index": ("Lean Hog Index", "$/cwt"),
    "cutout": ("Pork cutout", "$/cwt"),
    "spread_per_head": ("Packer spread", "$/head"),
    "head": ("Slaughter (producer-sold)", "head"),
    "weight_lb": ("Carcass weight", "lb"),
    "weaned_pig": ("Weaned pig (USDA cash)", "$/head"),
    "corn": ("Iowa corn (NASS, monthly)", "$/bu"),
    "crush_margin": ("Crush margin, pigs placed", "$/pig"),
}


def weekly(market_weekly: pd.DataFrame, pigs: pd.DataFrame, corn: pd.DataFrame,
           crush_rows: pd.DataFrame) -> pd.DataFrame:  # fmt: skip
    """Join the weekly market table, USDA weaned pig prices, Iowa corn (by month) and the
    realized crush margin of pigs placed that week. Weeks with no data at all are dropped."""
    w = market_weekly[["week_ending", "index", "cutout", "spread_per_head", "head", "weight_lb"]]
    w = w.copy()
    if "days" in market_weekly:  # holiday and part weeks would look like a slaughter drop
        w.loc[market_weekly["days"].to_numpy() < 5, "head"] = np.nan
    w["week_ending"] = pd.to_datetime(w["week_ending"])
    p = pd.DataFrame({"week_ending": pd.to_datetime(pigs["week_ending"]).to_numpy(),
                      "weaned_pig": pigs["cash_usd_per_head"].to_numpy(dtype=float)})  # fmt: skip
    sold = crush_rows[crush_rows["status"] == "sold"]
    cr = pd.DataFrame(
        {"week_ending": pd.to_datetime(sold["placed"]).to_numpy() + np.timedelta64(4, "D"),
         "crush_margin": sold["margin_usd"].to_numpy(dtype=float)}
    )  # fmt: skip
    df = w.merge(p, on="week_ending", how="outer").merge(cr, on="week_ending", how="left")
    month = df["week_ending"].to_numpy(dtype="datetime64[M]")
    by_month = dict(zip(pd.to_datetime(corn["month"]).to_numpy(dtype="datetime64[M]"),
                        corn["usd_per_bu"].to_numpy(dtype=float), strict=True))  # fmt: skip
    df["corn"] = [by_month.get(m, np.nan) for m in month]
    df = df[df["week_ending"] >= pd.Timestamp("2020-01-01")]
    values = df[list(COLUMNS)]
    df = df[values.notna().any(axis=1)]
    return df.sort_values("week_ending").reset_index(drop=True)


def annual(w: pd.DataFrame) -> pd.DataFrame:
    """Yearly averages (slaughter: average per full week) with the number of weeks covered."""
    year = w["week_ending"].to_numpy(dtype="datetime64[Y]").astype(int) + 1970
    out = []
    for y in sorted(set(year.tolist())):
        g = w[year == y]
        row: dict[str, float | int] = {"year": y, "weeks": len(g)}
        for col in COLUMNS:
            v = g[col].to_numpy(dtype=float)
            v = v[~np.isnan(v)]
            row[col] = float(v.mean()) if len(v) else float("nan")
        out.append(row)
    return pd.DataFrame(out)


def year_change(a: pd.DataFrame, col: str) -> float | None:
    """Latest year's average vs the year before, as a fraction."""
    s = a.dropna(subset=[col])
    if len(s) < 2:
        return None
    return float(s[col].iloc[-1] / s[col].iloc[-2] - 1)
