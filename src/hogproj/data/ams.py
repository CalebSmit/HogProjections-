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
from hogproj.data.saved import newest

DATAMART_URL = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports"
HG201_SLUG = 2511
HG201_FILE = "lm_hg201_barrows_gilts.csv"
HISTORY_START = date(2020, 1, 1)  # covers every weaned pig week in the bundled sample

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


def merge_hg201(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Saved rows plus newly fetched ones; a re-fetched day replaces the saved copy."""
    both = pd.concat([f for f in (old, new) if not f.empty], ignore_index=True)
    both = both.drop_duplicates(["slaughter_date", "purchase_type"], keep="last")
    return both.sort_values(["slaughter_date", "purchase_type"]).reset_index(drop=True)


def _fetch_range(start: date, end: date) -> pd.DataFrame:
    """Fetch in one-year requests (USDA answers a year in ~2 s)."""
    parts = []
    while start <= end:
        stop = min(end, start + timedelta(days=364))
        parts.append(fetch_hg201(start, stop))
        start = stop + timedelta(days=1)
    parts = [p for p in parts if not p.empty]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def load_hg201(offline: bool, start: date = HISTORY_START) -> tuple[pd.DataFrame, Source, str]:
    """Return (data, source, note). Never raises for network problems.

    Incremental: starts from the saved copy (cache, else the bundled sample), fetches only the
    days after it (plus a week of overlap for revisions) and any years before it back to
    `start`, then saves the merged history.
    """
    cache = CACHE_DIR / HG201_FILE
    saved_path = newest(cache, SAMPLE_DIR / HG201_FILE)
    saved = _read(saved_path)
    saved_source: Source = "cache" if saved_path == cache else "sample"
    if not offline:
        try:
            first = date.fromisoformat(str(saved["report_date"].min())[:10])
            last = date.fromisoformat(str(saved["report_date"].max())[:10])
            new = _fetch_range(last - timedelta(days=7), date.today())
            if first > start + timedelta(days=7):
                new = merge_hg201(_fetch_range(start, first), new)
            if new.empty:
                raise ValueError("USDA returned no rows")
            df = merge_hg201(saved, new)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", "Live from USDA AMS (LM_HG201)."
        except (httpx.HTTPError, ValueError) as e:
            problem = f"Couldn't reach USDA ({type(e).__name__})."
    else:
        problem = "Offline mode."
    last = saved["report_date"].max()
    where = "saved data" if saved_source == "cache" else "bundled sample data"
    return saved, saved_source, f"{problem} Showing {where} through {last:%b %d, %Y}."
