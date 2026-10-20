"""USDA AMS My Market News (MARS API v1.2): history for the reports the app reads. Needs the
free USDA_MMN_API_KEY (HTTP basic auth: key as user, empty password).

- AMS_2810 National Direct Feeder Pig: weekly early weaned 10-12 lb cash and formula composites
  (head, price, range) and 40 lb pigs, Feb 2020 on.
- AMS_2850 Iowa Daily Cash Grain Bids: corn by region → Iowa average cash and basis, Feb 2020 on.
- AMS_3511 National Grain and Oilseed Processor Feedstuff: Iowa soybean meal and DDGS, weekly,
  Feb 2022 on.

The key never reaches logs or the UI: it is scrubbed from any error text.
"""

from datetime import date, timedelta
from typing import Any, Literal

import httpx
import numpy as np
import pandas as pd

from hogproj.config import CACHE_DIR

BASE = "https://marsapi.ams.usda.gov/services/v1.2/reports"
START = date(2020, 1, 1)
Source = Literal["live", "cache", "none"]


def _num(v: Any) -> float:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return float("nan")


def fetch(key: str, slug: int, section: str, start: date, end: date,
          client: httpx.Client | None = None) -> list[dict]:  # fmt: skip
    """All rows of one report section between two report dates, in one-year requests."""
    rows: list[dict] = []
    with client or httpx.Client(auth=(key, ""), timeout=120, follow_redirects=True) as c:
        while start <= end:
            stop = min(end, start + timedelta(days=364))
            q = f"report_begin_date={start:%m/%d/%Y}:{stop:%m/%d/%Y}"
            try:
                resp = c.get(f"{BASE}/{slug}/{section}", params={"q": q})
                resp.raise_for_status()
            except httpx.HTTPError as e:  # never let the key reach logs or the UI
                raise httpx.HTTPError(str(e).replace(key, "***")) from None
            rows += resp.json().get("results", [])
            start = stop + timedelta(days=1)
    return rows


# --- Parsers (pure) -----------------------------------------------------------------------------
def feeder(rows: list[dict]) -> pd.DataFrame:
    """Report Details -> one row per week: early weaned cash/formula composites and 40 lb pigs."""
    out: dict[pd.Timestamp, dict] = {}
    for r in rows:
        if r.get("lot_size") != "Total Composite":
            continue
        week = pd.Timestamp(pd.to_datetime(r["report_end_date"], format="%m/%d/%Y"))
        row = out.setdefault(week, {"week_ending": week})
        cls, kind = r.get("class"), str(r.get("purchase_type", "")).lower()
        if cls == "Pigs Early Weaned":
            row[f"ew_{kind}_usd"] = _num(r.get("wtd_avg_price"))
            row[f"ew_{kind}_head"] = _num(r.get("head_count"))
            if kind == "cash":
                row["low_usd"], row["high_usd"] = _num(r.get("price_Min")), _num(r.get("price_Max"))
        elif cls == "Pigs" and kind == "cash":
            row["pig40_cash_usd"] = _num(r.get("wtd_avg_price"))
    cols = ["week_ending", "ew_cash_usd", "ew_cash_head", "ew_formula_usd", "ew_formula_head",
            "low_usd", "high_usd", "pig40_cash_usd"]  # fmt: skip
    df = pd.DataFrame(list(out.values())).reindex(columns=cols)
    return df.sort_values("week_ending").reset_index(drop=True)


def iowa_corn(rows: list[dict]) -> pd.DataFrame:
    """Report Detail -> daily Iowa cash corn (average of the six country-elevator regions) and
    basis ($/bu vs the nearby futures quoted)."""
    recs = []
    for r in rows:
        if r.get("commodity") != "Corn" or r.get("delivery_point") != "Country Elevators":
            continue
        bmin, bmax = _num(r.get("basis Min")), _num(r.get("basis Max"))
        basis = np.nanmean([bmin, bmax]) / 100 if not np.isnan(bmin) else np.nan  # ¢ -> $
        recs.append({"date": pd.to_datetime(r["report_date"], format="%m/%d/%Y"),
                     "price": _num(r.get("avg_price")), "basis": basis})  # fmt: skip
    if not recs:
        return pd.DataFrame(columns=["date", "corn_cash_iowa", "corn_basis_iowa"])
    df = pd.DataFrame(recs).groupby("date").agg(corn_cash_iowa=("price", "mean"),
                                                 corn_basis_iowa=("basis", "mean"))  # fmt: skip
    return df.reset_index().sort_values("date").reset_index(drop=True)


def iowa_feedstuffs(rows: list[dict]) -> pd.DataFrame:
    """Report Detail -> weekly Iowa soybean meal 46.5-48% and DDGS ($/ton)."""
    recs: dict[pd.Timestamp, dict] = {}
    for r in rows:
        if "Iowa" not in (r.get("trade Loc"), r.get("trade_loc"), r.get("location_State")):
            continue
        item = ("sbm_iowa" if r.get("commodity") == "Soybean Meal"
                and str(r.get("protein", "")).startswith("46.5") else
                "ddgs_iowa" if r.get("commodity") == "Corn Distillers" else None)  # fmt: skip
        if item is None:
            continue
        day = pd.Timestamp(pd.to_datetime(r["report_end_date"], format="%m/%d/%Y"))
        recs.setdefault(day, {"date": day})[item] = _num(r.get("avg_price"))
    df = pd.DataFrame(list(recs.values())).reindex(columns=["date", "sbm_iowa", "ddgs_iowa"])
    return df.sort_values("date").reset_index(drop=True)


DATASETS = {
    "feeder": (2810, "Report Details", feeder, "week_ending", "mars_feeder_pigs.csv"),
    "corn": (2850, "Report Detail", iowa_corn, "date", "mars_iowa_corn.csv"),
    "feedstuffs": (3511, "Report Detail", iowa_feedstuffs, "date", "mars_iowa_feedstuffs.csv"),
}


def load(name: str, key: str, offline: bool) -> tuple[pd.DataFrame, Source, str]:
    """One dataset: incremental from the cache (two weeks of overlap for revisions). Unlike the
    other loaders there's no bundled sample — without a key the app uses the public PDFs."""
    slug, section, parser, date_col, file = DATASETS[name]
    cache = CACHE_DIR / file
    saved = pd.read_csv(cache, parse_dates=[date_col]) if cache.exists() else None
    if not key:
        problem = "Add USDA_MMN_API_KEY to .env for USDA history."
    elif offline:
        problem = "Offline mode."
    else:
        try:
            since = (pd.Timestamp(str(saved[date_col].max())).date() - timedelta(days=14)
                     if saved is not None and len(saved) else START)  # fmt: skip
            new = parser(fetch(key, slug, section, since, date.today()))
            df = new if saved is None else pd.concat([saved, new], ignore_index=True)
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.drop_duplicates(date_col, keep="last").sort_values(date_col)
            df = df.reset_index(drop=True)
            if df.empty:
                raise ValueError("USDA returned no rows")
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", f"Live from USDA My Market News (AMS_{slug})."
        except (httpx.HTTPError, ValueError, KeyError) as e:
            problem = f"Couldn't reach My Market News ({type(e).__name__})."
    if saved is not None:
        return saved, "cache", f"{problem} Showing saved history."
    return pd.DataFrame(), "none", problem
