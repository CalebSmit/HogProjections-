"""The national view: hog prices by region and how hogs are sold, corn and basis by state,
where weaned pigs and market hogs come from, and the packer weight discount schedule.
Pure: DataFrames in, DataFrames out.
"""

import numpy as np
import pandas as pd

STATE_CODES = {
    "Alabama": "AL", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
    "Florida": "FL", "Georgia": "GA", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN",
    "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maryland": "MD",
    "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND",
    "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Virginia": "VA", "Washington": "WA", "Wisconsin": "WI", "Wyoming": "WY",
}  # fmt: skip


def _latest_day(df: pd.DataFrame, col: str = "date") -> pd.Timestamp:
    return pd.Timestamp(str(pd.to_datetime(df[col]).max()))


def regional_latest(prices: pd.DataFrame, days: int = 5) -> pd.DataFrame:
    """Region × purchase type: head-weighted average price over the last `days` reports and
    total head (prices are blank on days USDA withholds them, so a few days are pooled)."""
    d = pd.to_datetime(prices["date"])
    recent = prices[d.isin(sorted(d.unique())[-days:])].dropna(subset=["price"])
    recent = recent.assign(value=recent["price"] * recent["head"].fillna(0))
    g = recent.groupby(["region", "purchase"]).agg(value=("value", "sum"), head=("head", "sum"),
                                                    price=("price", "mean"))  # fmt: skip
    g["price"] = np.where(g["head"] > 0, g["value"] / g["head"].where(g["head"] > 0), g["price"])
    return g.drop(columns="value").reset_index()


def regional_weekly(prices: pd.DataFrame, purchase: str) -> pd.DataFrame:
    """Weekly (Friday) average price for one purchase type, one column per region."""
    x = prices[prices["purchase"] == purchase].dropna(subset=["price"])
    x = x.assign(date=pd.to_datetime(x["date"]))
    w = x.pivot_table(index="date", columns="region", values="price", aggfunc="mean")
    return w.resample("W-FRI").mean().dropna(how="all")


def purchase_mix(prices: pd.DataFrame, region: str = "National", days: int = 20) -> pd.DataFrame:
    """How hogs were sold over the last `days` reports: share of head and average price."""
    x = prices[prices["region"] == region]
    d = pd.to_datetime(x["date"])
    x = x[d.isin(sorted(d.unique())[-days:])]
    head = x.groupby("purchase")["head"].sum()
    price = x.dropna(subset=["price"]).groupby("purchase")["price"].mean()
    out = pd.DataFrame({"head": head, "share": head / head.sum(), "price": price})
    return out.reset_index().sort_values("share", ascending=False)


def state_corn_snapshot(sc: pd.DataFrame) -> pd.DataFrame:
    """Latest cash corn and basis by state, with the same day a year earlier."""
    rows = []
    for state, g in sc.groupby("state"):
        g = g.sort_values("date")
        last = g.iloc[-1]
        ago = g[
            pd.to_datetime(g["date"]) <= pd.Timestamp(str(last["date"])) - pd.Timedelta(days=364)
        ]
        rows.append({"state": state, "code": STATE_CODES.get(str(state)), "date": last["date"],
                     "cash": float(last["cash"]), "basis": float(last["basis"]),
                     "cash_year_ago": float(ago["cash"].iloc[-1]) if len(ago) else np.nan,
                     "basis_year_ago": float(ago["basis"].iloc[-1]) if len(ago)
                     else np.nan})  # fmt: skip
    return pd.DataFrame(rows).sort_values("cash").reset_index(drop=True)


def flows_latest(fl: pd.DataFrame) -> pd.DataFrame:
    """Latest week's share of feeder pigs by state of origin and destination, with the
    52-week average for comparison."""
    wk = pd.to_datetime(fl["week_ending"])
    last = wk.max()
    now = fl[wk == last].set_index("state")[["origin_pct", "destination_pct"]]
    cols = ["origin_pct", "destination_pct"]
    year = fl[wk > last - pd.Timedelta(weeks=52)].groupby("state")[cols].mean()
    out = now.join(year, rsuffix="_52wk", how="outer").reset_index()
    out["week_ending"] = last
    return out


def origin_share(origin: pd.DataFrame, days: int = 28) -> pd.DataFrame:
    """Share of producer-sold hogs by state of origin over the last `days` calendar days."""
    d = pd.to_datetime(origin["date"])
    x = origin[d > d.max() - pd.Timedelta(days=days)]
    head = x.groupby("state")["head"].sum()
    out = pd.DataFrame({"head": head, "share": head / head.sum()}).reset_index()
    out["code"] = out["state"].map(STATE_CODES)
    return out.sort_values("share", ascending=False).reset_index(drop=True)


def weight_schedule(weights: pd.DataFrame) -> pd.DataFrame:
    """Packer carcass weight discounts ($/cwt, midpoint of USDA's range) by weight band: the
    latest report and a year earlier."""
    d = pd.to_datetime(weights["date"])
    last = d.max()
    now = weights[d == last].set_index("band_lb")["discount"]
    ago_day = d[d <= last - pd.Timedelta(days=364)].max()
    ago = weights[d == ago_day].set_index("band_lb")["discount"] if pd.notna(ago_day) else None
    out = pd.DataFrame({"now": now})
    out["year_ago"] = ago if ago is not None else np.nan
    return out.reset_index()


def sow_price(sows: pd.DataFrame, min_weight: int = 400) -> pd.Series:
    """Daily head-weighted negotiated sow price ($/cwt live) for sows above `min_weight` lb."""
    s = sows.dropna(subset=["price"])
    lb = s["weight_range"].str.extract(r"(\d+)")[0].astype(float)
    s = s[lb >= min_weight]
    s = s.assign(v=s["price"] * s["head"], date=pd.to_datetime(s["date"]))
    g = s.groupby("date").agg(v=("v", "sum"), head=("head", "sum"))
    return (g["v"] / g["head"]).rename("sow_usd_per_cwt_live")
