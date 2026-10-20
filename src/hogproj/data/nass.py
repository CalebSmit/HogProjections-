"""USDA NASS Quick Stats client for the quarterly Hogs and Pigs report. Needs NASS_API_KEY.

Load order mirrors data/ams.py: live API -> local cache -> bundled sample, always with a note
the UI can show. The key is sent as a query parameter, so it is scrubbed from any error text.
"""

from datetime import date
from typing import Any, Literal

import httpx
import pandas as pd

from hogproj.config import CACHE_DIR, SAMPLE_DIR

QUICKSTATS_URL = "https://quickstats.nass.usda.gov/api/api_GET/"
NASS_FILE = "nass_hogs_and_pigs.csv"

# short_desc -> our series name
SERIES = {
    "HOGS - INVENTORY": "all_hogs",
    "HOGS, BREEDING - INVENTORY": "breeding",
    "HOGS, MARKET - INVENTORY": "market",
    "HOGS, MARKET, LT 50 LBS - INVENTORY": "market_lt50",
    "HOGS, MARKET, 50 TO 119 LBS - INVENTORY": "market_50_119",
    "HOGS, MARKET, 120 TO 179 LBS - INVENTORY": "market_120_179",
    "HOGS, MARKET, GE 180 LBS - INVENTORY": "market_ge180",
    "HOGS - PIG CROP, MEASURED IN HEAD": "pig_crop",
    "HOGS - LITTER RATE, MEASURED IN PIGS / LITTER": "pigs_per_litter",
    "HOGS, SOWS - FARROWED, MEASURED IN HEAD": "sows_farrowed",
}
# Inventories are "first of" a month; production is reported per quarter.
INVENTORY_MONTH = {"FIRST OF MAR": 3, "FIRST OF JUN": 6, "FIRST OF SEP": 9, "FIRST OF DEC": 12}
QUARTER_START = {"DEC THRU FEB": 12, "MAR THRU MAY": 3, "JUN THRU AUG": 6, "SEP THRU NOV": 9}

Source = Literal["live", "cache", "sample"]


def _num(v: Any) -> float | None:
    s = str(v).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:  # "(D)" withheld, "(NA)" etc.
        return None


def parse(payload: dict[str, Any]) -> pd.DataFrame:
    """Quick Stats JSON -> tidy rows: series, period_start, kind (actual/intentions), value.

    `period_start` is the first day of the inventory month or of the 3-month production period
    (Dec-Feb starts in December of the previous year). Intentions are farrowing forecasts made
    in an earlier report, e.g. "SEP THRU NOV - SEP FORECAST".
    """
    rows = []
    for r in payload.get("data", []):
        series = SERIES.get(r.get("short_desc", ""))
        value = _num(r.get("Value"))
        if series is None or value is None or r.get("agg_level_desc") != "NATIONAL":
            continue
        ref = str(r.get("reference_period_desc", ""))
        year = int(r["year"])
        kind = "actual"
        if ref in INVENTORY_MONTH:
            month = INVENTORY_MONTH[ref]
        else:
            base, _, forecast = ref.partition(" - ")
            if base not in QUARTER_START:
                continue  # single months and marketing-year totals aren't used
            month = QUARTER_START[base]
            if month == 12:
                year -= 1  # Dec-Feb of year Y starts in December of Y-1
            if forecast:
                kind = f"intentions ({forecast.lower()})"
        rows.append(
            {
                "series": series,
                "period_start": pd.Timestamp(year=year, month=month, day=1),
                "kind": kind,
                "value": value,
                "released": str(r.get("load_time", ""))[:10],
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values("released").drop_duplicates(["series", "period_start", "kind"], keep="last")
    return df.sort_values(["series", "kind", "period_start"]).reset_index(drop=True)


def fetch(key: str, since_year: int, client: httpx.Client | None = None) -> pd.DataFrame:
    params = {
        "key": key,
        "commodity_desc": "HOGS",
        "agg_level_desc": "NATIONAL",
        "source_desc": "SURVEY",
        "year__GE": str(since_year),
        "format": "JSON",
    }
    with client or httpx.Client(timeout=180, follow_redirects=True) as c:
        try:
            resp = c.get(QUICKSTATS_URL, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as e:  # never let the key reach logs or the UI
            raise httpx.HTTPError(str(e).replace(key, "***")) from None
        return parse(resp.json())


def _read(path) -> pd.DataFrame:  # noqa: ANN001 - Path
    return pd.read_csv(path, parse_dates=["period_start"])


def load(key: str, offline: bool, years: int = 16) -> tuple[pd.DataFrame, Source, str]:
    """Return (data, source, note). Never raises for missing keys or network problems."""
    cache = CACHE_DIR / NASS_FILE
    if not key:
        problem = "Add a free NASS_API_KEY to .env for live USDA inventory data."
    elif offline:
        problem = "Offline mode."
    else:
        try:
            df = fetch(key, date.today().year - years)
            if df.empty:
                raise ValueError("USDA returned no rows")
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", "Live from USDA NASS Quick Stats (Hogs and Pigs)."
        except (httpx.HTTPError, ValueError) as e:
            problem = f"Couldn't reach USDA NASS ({type(e).__name__})."
    if cache.exists():
        df = _read(cache)
        return df, "cache", f"{problem} Showing saved data."
    return _read(SAMPLE_DIR / NASS_FILE), "sample", f"{problem} Showing bundled sample data."
