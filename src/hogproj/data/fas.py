"""USDA FAS weekly Export Sales Reporting for pork (fresh, chilled or frozen muscle cuts,
commodity 1702), by country: net new sales, shipments and the year's accumulated exports,
metric tons. Needs the free api.data.gov key (FAS_API_KEY), sent as the X-Api-Key header.
Weeks end Thursday; USDA publishes them the following Thursday. The pork marketing year is the
calendar year. The key never reaches logs or the UI: it is scrubbed from any error text.
"""

from datetime import date
from typing import Literal

import httpx
import pandas as pd

from hogproj.config import CACHE_DIR, SAMPLE_DIR
from hogproj.data.saved import newest

BASE = "https://api.fas.usda.gov/api/esr"
PORK = 1702
START_YEAR = 2020
FILE = "fas_pork_export_sales.csv"
COLUMNS = ["week_ending", "country", "net_sales_mt", "exports_mt", "accumulated_mt",
           "outstanding_mt"]  # fmt: skip
Source = Literal["live", "cache", "sample", "none"]


def parse(rows: list[dict], countries: dict[int, str]) -> pd.DataFrame:
    """ESR export records -> one row per week and country (names tidied, blanks dropped)."""
    recs = [{"week_ending": pd.Timestamp(str(r["weekEndingDate"])[:10]),
             "country": countries.get(int(r["countryCode"]), str(r["countryCode"])),
             "net_sales_mt": float(r.get("currentMYNetSales") or 0),
             "exports_mt": float(r.get("weeklyExports") or 0),
             "accumulated_mt": float(r.get("accumulatedExports") or 0),
             "outstanding_mt": float(r.get("outstandingSales") or 0)}
            for r in rows if r.get("weekEndingDate")]  # fmt: skip
    df = pd.DataFrame(recs, columns=COLUMNS)
    nonzero = df[["net_sales_mt", "exports_mt", "accumulated_mt", "outstanding_mt"]].ne(0)
    return df[nonzero.any(axis=1)].reset_index(drop=True)


def _get(c: httpx.Client, path: str, key: str) -> list[dict]:
    try:
        resp = c.get(f"{BASE}/{path}")
        resp.raise_for_status()
    except httpx.HTTPError as e:  # never let the key reach logs or the UI
        raise httpx.HTTPError(str(e).replace(key, "***")) from None
    return resp.json()


def fetch(key: str, years: list[int]) -> pd.DataFrame:
    with httpx.Client(headers={"X-Api-Key": key}, timeout=60) as c:
        countries = {int(x["countryCode"]): str(x["countryDescription"]).strip().title()
                     for x in _get(c, "countries", key)}  # fmt: skip
        parts = [parse(_get(c, f"exports/commodityCode/{PORK}/allCountries/marketYear/{y}", key),
                       countries) for y in years]  # fmt: skip
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=COLUMNS)


def load(key: str, offline: bool) -> tuple[pd.DataFrame, Source, str]:
    """Saved history plus this year and last year fetched fresh (revisions land in both)."""
    cache = CACHE_DIR / FILE
    path = newest(cache, SAMPLE_DIR / FILE)
    saved = pd.read_csv(path, parse_dates=["week_ending"]) if path.exists() else None
    if not key:
        problem = "Add FAS_API_KEY to .env for weekly export sales."
    elif offline:
        problem = "Offline mode."
    else:
        try:
            this = date.today().year
            have = set() if saved is None else set(saved["week_ending"].dt.year)
            years = sorted({this - 1, this} | (set(range(START_YEAR, this - 1)) - have))
            new = fetch(key, years)
            if new.empty:
                raise ValueError("FAS returned no rows")
            old = saved[~saved["week_ending"].dt.year.isin(years)] if saved is not None else None
            df = pd.concat([f for f in (old, new) if f is not None and not f.empty],
                           ignore_index=True)  # fmt: skip
            df = df.sort_values(["week_ending", "country"]).reset_index(drop=True)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", "Live from USDA FAS Export Sales."
        except (httpx.HTTPError, ValueError, KeyError) as e:
            problem = f"Couldn't reach USDA FAS ({type(e).__name__})."
    if saved is not None:
        return saved, "cache" if path == cache else "sample", f"{problem} Showing saved data."
    return pd.DataFrame(columns=COLUMNS), "none", problem
