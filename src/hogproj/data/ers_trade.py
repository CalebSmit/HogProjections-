"""USDA ERS monthly trade and price spreads (public CSVs, no key):

- pork exports and imports by country, carcass weight, 1,000 lb;
- live hog imports by size class (mostly Canadian feeder pigs and slaughter hogs), head;
- pork values and spreads: retail, wholesale and farm value (cents/lb retail weight) and the
  farmer's share of the retail dollar.

The `/media/NNNN/` ids are ERS's own and can change; the loader falls back to the saved copy.
"""

import io
from typing import Literal

import httpx
import pandas as pd

from hogproj.config import CACHE_DIR, SAMPLE_DIR
from hogproj.data.saved import newest

BASE = "https://www.ers.usda.gov/media"
FILES = {  # name -> (url path, saved file)
    "pork_trade": ("29546/pork-monthly-us-trade-carcass-weight-1000-pounds.csv",
                   "ers_pork_trade.csv"),
    "hog_trade": ("29547/hogs-monthly-us-trade-head.csv", "ers_hog_trade.csv"),
    "spreads": ("5026/pork-values-and-spreads.csv", "ers_pork_spreads.csv"),
}  # fmt: skip
SPREADS_HISTORY = "5028/historical-monthly-price-spread-data-for-beef-pork-broilers.csv"
SPREAD_ITEMS = {  # ERS item (lower case, either file) -> short name, cents/lb retail weight
    "pork retail value": "retail", "pork wholesale value": "wholesale",
    "pork net farm value": "net_farm", "pork gross farm value": "gross_farm",
}  # fmt: skip
START_YEAR = 2015
HOG_CLASSES = {  # ERS commodity -> short name (imports)
    "Hog, less than 7 kilograms (15.4 pounds)": "Weaned pigs (under 7 kg)",
    "Hog, 7 to less than 23 kilograms (50.7 pounds)": "Feeder pigs (7-23 kg)",
    "Hog, 50 kilograms (110.2 pounds) or more for immediate slaughter": "Slaughter hogs",
    "Hog, total": "All hogs",
}
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June",
                                      "July", "August", "September", "October", "November",
                                      "December"], start=1)}  # fmt: skip
Source = Literal["live", "cache", "sample"]


def parse_trade(text: str, hogs: bool = False) -> pd.DataFrame:
    """ERS trade CSV -> month, flow, country, commodity, amount (from 2015)."""
    df = pd.read_csv(io.StringIO(text))
    df = df[(df["YEAR_ID"] >= START_YEAR) & df["TIMEPERIOD_ID"].between(1, 12)]
    if hogs:
        df = df[(df["TRADE_FLOW"] == "Imports") & df["COMMODITY_DESC"].isin(HOG_CLASSES)]
        commodity = df["COMMODITY_DESC"].map(HOG_CLASSES)
    else:
        commodity = df["COMMODITY_DESC"]
    return pd.DataFrame({
        "month": pd.to_datetime(dict(year=df["YEAR_ID"], month=df["TIMEPERIOD_ID"], day=1)),
        "flow": df["TRADE_FLOW"], "country": df["GEOGRAPHY_DESC"].fillna("World total"),
        "commodity": commodity, "amount": pd.to_numeric(df["AMOUNT"], errors="coerce"),
    }).dropna(subset=["amount"]).reset_index(drop=True)  # fmt: skip


def parse_spreads(text: str) -> pd.DataFrame:
    """ERS pork values and spreads (current or historical file) -> month, item, value in cents
    per lb retail weight, monthly rows only, from 2015."""
    df = pd.read_csv(io.StringIO(text.lstrip("﻿")))
    period = "Period" if "Period" in df.columns else "Month"
    df = df[df[period].isin(MONTHS) & (df["Year"] >= START_YEAR)]
    item = df["Data_Item"].str.strip().str.lower().map(SPREAD_ITEMS)
    out = pd.DataFrame({
        "month": pd.to_datetime(dict(year=df["Year"], month=df[period].map(MONTHS), day=1)),
        "item": item, "value": pd.to_numeric(df["Value"], errors="coerce"),
    })  # fmt: skip
    return out.dropna().reset_index(drop=True)


def _get(client: httpx.Client, path: str) -> str:
    resp = client.get(f"{BASE}/{path}")
    resp.raise_for_status()
    return resp.content.decode("utf-8-sig")


def load(name: str, offline: bool) -> tuple[pd.DataFrame, Source, str]:
    url, file = FILES[name]
    cache = CACHE_DIR / file
    if not offline:
        try:
            with httpx.Client(
                timeout=60,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (HogProjections)"},
            ) as c:
                text = _get(c, url)
                if name == "spreads":  # history to Dec 2025 + the current two years
                    df = pd.concat([parse_spreads(_get(c, SPREADS_HISTORY)), parse_spreads(text)])
                    df = df.drop_duplicates(["month", "item"], keep="last")
                    df = df.sort_values(["month", "item"]).reset_index(drop=True)
                else:
                    df = parse_trade(text, name == "hog_trade")  # fmt: skip
            if df.empty:
                raise ValueError("ERS returned no rows")
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", "Live from USDA ERS."
        except (httpx.HTTPError, ValueError, KeyError) as e:
            problem = f"Couldn't reach USDA ERS ({type(e).__name__})."
    else:
        problem = "Offline mode."
    path = newest(cache, SAMPLE_DIR / file)
    df = pd.read_csv(path, parse_dates=["month"])
    return df, "cache" if path == cache else "sample", f"{problem} Showing saved data."
