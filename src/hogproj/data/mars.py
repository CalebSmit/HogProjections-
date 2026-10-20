"""USDA AMS My Market News (MARS API v1.2): history for the reports the app reads. Needs the
free USDA_MMN_API_KEY (HTTP basic auth: key as user, empty password).

- AMS_2810 National Direct Feeder Pig: weekly early weaned 10-12 lb cash and formula composites
  (head, price, range) and 40 lb pigs, Feb 2020 on.
- AMS_2850 Iowa Daily Cash Grain Bids: corn by region → Iowa average cash and basis, Feb 2020 on.
- AMS_3511 National Grain and Oilseed Processor Feedstuff: Iowa soybean meal and DDGS, weekly,
  Feb 2022 on.
- MULTI below: state grain bids, feeder pig flows (2810), drop value (2835), retail features
  (2868) and daily federally inspected slaughter (3208).

The key never reaches logs or the UI: it is scrubbed from any error text.
"""

from datetime import date, timedelta
from typing import Any, Literal

import httpx
import numpy as np
import pandas as pd

from hogproj.config import CACHE_DIR, SAMPLE_DIR

BASE = "https://marsapi.ams.usda.gov/services/v1.2/reports"
START = date(2020, 1, 1)
Source = Literal["live", "cache", "sample", "none"]


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


STATES = {  # state grain bid reports with corn by region
    "Iowa": 2850, "Minnesota": 3049, "South Dakota": 3186, "Nebraska": 3225, "Illinois": 3192,
    "Indiana": 3463, "Ohio": 2851, "Missouri": 2932, "Kansas": 2886, "North Carolina": 3156,
    "Texas": 2711,
}  # fmt: skip


def state_corn(rows: list[dict], state: str) -> pd.DataFrame:
    """Daily state average cash corn and basis (country elevators where reported)."""
    corn = [r for r in rows if r.get("commodity") == "Corn"]
    country = [r for r in corn if r.get("delivery_point") == "Country Elevators"]
    df = iowa_corn(country or [{**r, "delivery_point": "Country Elevators"} for r in corn])
    df = df.rename(columns={"corn_cash_iowa": "cash", "corn_basis_iowa": "basis"})
    df.insert(1, "state", state)
    return df


def flows(rows: list[dict], _: object = None) -> pd.DataFrame:
    """Feeder pig volume by state: share of pigs from (origin) and to (destination) each state."""
    recs = [{"week_ending": pd.to_datetime(r["report_end_date"], format="%m/%d/%Y"),
             "state": str(r.get("state")), "origin_pct": _num(r.get("origin_pct")),
             "destination_pct": _num(r.get("destination_pct"))}
            for r in rows if r.get("state")]  # fmt: skip
    return pd.DataFrame(recs, columns=["week_ending", "state", "origin_pct", "destination_pct"])


def drop_value(rows: list[dict], _: object = None) -> pd.DataFrame:
    """Weekly hog by-product (drop) value, $/cwt live and dressed equivalent."""
    recs = [{"week_ending": pd.to_datetime(r["report_end_date"], format="%m/%d/%Y"),
             "drop_usd_per_cwt_live": _num(r.get("total_value")),
             "drop_usd_per_cwt_carcass": _num(r.get("dressed_equivalent_value"))}
            for r in rows if r.get("sub_Group") == "Hog Drop"]  # fmt: skip
    return pd.DataFrame(recs, columns=["week_ending", "drop_usd_per_cwt_live",
                                       "drop_usd_per_cwt_carcass"])  # fmt: skip


def retail(rows: list[dict], _: object = None) -> pd.DataFrame:
    """Weekly grocery pork feature activity by region (feature rate, activity index)."""
    recs = [{"week_ending": pd.to_datetime(r["report_end_date"], format="%m/%d/%Y"),
             "region": str(r.get("region")), "stores": _num(r.get("stores")),
             "feature_rate": _num(r.get("feature")),
             "feature_rate_last_year": _num(r.get("last_Year_Feature")),
             "activity_index": _num(r.get("activity_Index")),
             "activity_index_last_year": _num(r.get("last_Year_Activity_Index"))}
            for r in rows if r.get("region")]  # fmt: skip
    return pd.DataFrame(recs)


def fi_slaughter(rows: list[dict], _: object = None) -> pd.DataFrame:
    """Daily federally inspected hog slaughter (all hogs, packer-owned included) with USDA's
    same-day-a-year-ago figure. Each report also revises the prior day, so the newest report
    for a slaughter day wins."""
    recs = [{"date": pd.to_datetime(r["slaughter_date"]),
             "report_date": pd.to_datetime(r["report_date"], format="%m/%d/%Y"),
             "head": _num(r.get("slaughter")), "head_year_ago": _num(r.get("year_ago"))}
            for r in rows
            if r.get("commodity") == "Hogs" and r.get("class") == "All"
            and r.get("slaughter_date")]  # fmt: skip
    cols = ["date", "head", "head_year_ago"]
    if not recs:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(recs).sort_values(["date", "report_date"])
    return df.drop_duplicates("date", keep="last")[cols].reset_index(drop=True)


# name -> ([(slug, section or None = its detail section, tag)], parser, date column, file, keys)
MULTI: dict[str, tuple[list[tuple[int, str | None, object]], Any, str, str, list[str]]] = {
    "state_corn": ([(slug, None, st) for st, slug in STATES.items()], state_corn, "date",
                   "mars_state_corn.csv", ["date", "state"]),
    "flows": ([(2810, "Report Volume", None)], flows, "week_ending", "mars_feeder_flows.csv",
              ["week_ending", "state"]),
    "drop": ([(2835, "Report Totals", None)], drop_value, "week_ending", "mars_drop_value.csv",
             ["week_ending"]),
    "retail": ([(2868, "Report Metrics", None)], retail, "week_ending",
               "mars_retail_pork.csv", ["week_ending", "region"]),
    "fi_slaughter": ([(3208, "Report Livestock Commodity", None)], fi_slaughter, "date",
                     "mars_fi_slaughter.csv", ["date"]),
}  # fmt: skip


def _detail_section(key: str, slug: int) -> str:
    with httpx.Client(auth=(key, ""), timeout=120, follow_redirects=True) as c:
        try:
            secs = c.get(f"{BASE}/{slug}").json().get("reportSections") or []
        except httpx.HTTPError as e:
            raise httpx.HTTPError(str(e).replace(key, "***")) from None
    return next((x for x in secs if "Detail" in x), "Report Detail")


DATASETS = {
    "feeder": (2810, "Report Details", feeder, "week_ending", "mars_feeder_pigs.csv"),
    "corn": (2850, "Report Detail", iowa_corn, "date", "mars_iowa_corn.csv"),
    "feedstuffs": (3511, "Report Detail", iowa_feedstuffs, "date", "mars_iowa_feedstuffs.csv"),
}


def _fetch_multi(name: str, key: str, since: date) -> pd.DataFrame:
    sources, parser, _, _, _ = MULTI[name]
    parts = []
    for slug, section, tag in sources:
        sec = section or _detail_section(key, slug)
        parts.append(parser(fetch(key, slug, sec, since, date.today()), tag))
    parts = [p for p in parts if not p.empty]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def load(name: str, key: str, offline: bool) -> tuple[pd.DataFrame, Source, str]:
    """One dataset: incremental from the cache (two weeks of overlap for revisions), else the
    bundled sample, else nothing (without a key the app uses the public PDFs)."""
    section: str = ""
    parser: Any = None
    if name in MULTI:
        _, _, date_col, file, keys = MULTI[name]
        slug = MULTI[name][0][0][0]
    else:
        slug, section, parser, date_col, file = DATASETS[name]
        keys = [date_col]
    cache = CACHE_DIR / file
    path = cache if cache.exists() else SAMPLE_DIR / file
    saved = pd.read_csv(path, parse_dates=[date_col]) if path.exists() else None
    if not key:
        problem = "Add USDA_MMN_API_KEY to .env for USDA history."
    elif offline:
        problem = "Offline mode."
    else:
        try:
            since = (pd.Timestamp(str(saved[date_col].max())).date() - timedelta(days=14)
                     if saved is not None and len(saved) else START)  # fmt: skip
            new = (_fetch_multi(name, key, since) if name in MULTI
                   else parser(fetch(key, slug, section, since, date.today())))  # fmt: skip
            df = new if saved is None else pd.concat([saved, new], ignore_index=True)
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.drop_duplicates(keys, keep="last").sort_values(keys)
            df = df.reset_index(drop=True)
            if df.empty:
                raise ValueError("USDA returned no rows")
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", f"Live from USDA My Market News (AMS_{slug})."
        except (httpx.HTTPError, ValueError, KeyError) as e:
            problem = f"Couldn't reach My Market News ({type(e).__name__})."
    if saved is not None:
        where: Source = "cache" if path == cache else "sample"
        return saved, where, f"{problem} Showing saved history."
    return pd.DataFrame(), "none", problem
