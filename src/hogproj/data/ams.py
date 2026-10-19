"""USDA AMS Livestock Mandatory Reporting (LMR) datamart client. No API key needed.

LM_HG201 "National Daily Direct Prior Day Slaughtered Swine" (slug 2511) is the report the
CME Lean Hog Index is built from. Load order: live API -> local cache -> bundled sample, and
the caller always learns which one it got so the UI can say so.
"""

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

import httpx
import pandas as pd

from hogproj.config import CACHE_DIR, SAMPLE_DIR

DATAMART_URL = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports"
HG201_SLUG = 2511
HG201_FILE = "lm_hg201_barrows_gilts.csv"

# Producer-sold purchase types the index uses, plus the all-types row for context.
KEEP_PURCHASE_TYPES = [
    "Prod. Sold Negotiated",
    "Prod. Sold Negotiated Formula",
    "Prod. Sold Swine or Pork Market Formula",
    "Prod. Sold (All Purchase Types)",
]

Source = Literal["live", "cache", "sample"]


def _num(x: Any) -> float | None:
    if x is None or x == "":
        return None
    return float(str(x).replace(",", ""))


def parse_hg201(payload: dict[str, Any]) -> pd.DataFrame:
    """Barrows/Gilts section JSON -> one row per report date and purchase type."""
    rows = [
        {
            "report_date": pd.to_datetime(r["report_date"], format="%m/%d/%Y"),
            "slaughter_date": pd.to_datetime(r["for_date_begin"], format="%m/%d/%Y"),
            "purchase_type": r["purchase_type"],
            "head_count": _num(r.get("head_count")),
            "avg_net_price_cwt_carcass": _num(r.get("avg_net_price")),
            "avg_weight_lb_carcass": _num(r.get("avg_carcass_weight")),
            "avg_weight_lb_live": _num(r.get("avg_live_weight")),
        }
        for r in payload.get("results", [])
        if r.get("purchase_type") in KEEP_PURCHASE_TYPES
    ]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["slaughter_date", "purchase_type"]).reset_index(drop=True)


def fetch_hg201(start: date, end: date, client: httpx.Client | None = None) -> pd.DataFrame:
    url = f"{DATAMART_URL}/{HG201_SLUG}/Barrows/Gilts"
    q = f"report_date={start:%m/%d/%Y}:{end:%m/%d/%Y}"
    with client or httpx.Client(timeout=60, follow_redirects=True) as c:
        resp = c.get(url, params={"q": q})
        resp.raise_for_status()
        return parse_hg201(resp.json())


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["report_date", "slaughter_date"])


def load_hg201(offline: bool, years: int = 3) -> tuple[pd.DataFrame, Source, str]:
    """Return (data, source, note). Never raises for network problems."""
    cache = CACHE_DIR / HG201_FILE
    if not offline:
        try:
            end = date.today()
            df = fetch_hg201(end - timedelta(days=365 * years), end)
            if df.empty:
                raise ValueError("USDA returned no rows")
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", "Live from USDA AMS (LM_HG201)."
        except (httpx.HTTPError, ValueError) as e:
            problem = f"Couldn't reach USDA ({type(e).__name__})."
    else:
        problem = "Offline mode."
    if cache.exists():
        df = _read(cache)
        last = df["report_date"].max()
        return df, "cache", f"{problem} Showing saved data through {last:%b %d, %Y}."
    df = _read(SAMPLE_DIR / HG201_FILE)
    last = df["report_date"].max()
    return df, "sample", f"{problem} Showing bundled sample data through {last:%b %d, %Y}."
