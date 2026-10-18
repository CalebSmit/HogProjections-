"""USDA AMS "National Direct Feeder Pig Report" (weekly; MyMarketNews slug 2810, legacy NW_LS255).

The report gives early weaned pigs (10-12 lb) and feeder pigs (40 lb) in $/head, split into
cash (open market) and formula trades, with lot-size buckets. Recent editions show buckets of
<600, 600-1,200 and >1,200 head. This module picks the largest bucket, or a 2,400+ bucket if the
report has one. Field names in the MARS JSON are not documented for this report [VERIFY], so
the parser looks up columns by keyword. A raw copy of every response goes to data/cache/ for
checking.

Needs a free MyMarketNews API key (USDA_MMN_API_KEY in .env), sent as HTTP Basic (key, "").
"""

import re
from datetime import date, timedelta

import pandas as pd

from hogproj.data.http import FetchError, get_json, write_cached_json

MARS = "https://marsapi.ams.usda.gov/services/v1.2/reports/2810"

_KEYS = {
    "date": ("report_end_date", "report_date", "report_begin_date", "published_date"),
    "class": ("class", "pig_class", "commodity", "category", "description"),
    "type": ("purchase_type", "price_type", "trans_type", "sale_type", "type"),
    "lot": ("lot_desc", "lot_size", "lot", "volume", "head_range"),
    "price": ("wtd_avg", "weighted_avg", "avg_price", "weighted_average", "price_avg"),
    "head": ("head_count", "head", "receipts", "quantity"),
}


def _pick(rec: dict, field: str) -> object:
    lower = {k.lower(): v for k, v in rec.items()}
    for key in _KEYS[field]:
        if key in lower and lower[key] not in (None, ""):
            return lower[key]
    return None


def _num(v: object) -> float | None:
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def lot_min_head(lot: str) -> int:
    """Lower bound of a lot-size label: '1,200 head and over' -> 1200, 'Under 600' -> 0."""
    text = lot.lower().replace(",", "")
    nums = [int(n) for n in re.findall(r"\d+", text)]
    if not nums or "under" in text or "less" in text or "<" in text:
        return 0
    return min(nums)


def parse_feeder_pig(results: list[dict]) -> pd.DataFrame:
    """Early weaned rows -> date, purchase (cash/formula), lot, lot_min_head, head, price."""
    rows = []
    for rec in results:
        cls = str(_pick(rec, "class") or "").lower()
        if "wean" not in cls:
            continue
        kind = str(_pick(rec, "type") or "").lower()
        purchase = (
            "cash"
            if ("cash" in kind or "negotiated" in kind)
            else ("formula" if "formula" in kind else "")
        )
        price = _num(_pick(rec, "price"))
        raw_date = str(_pick(rec, "date") or "")
        if not purchase or price is None or not raw_date:
            continue
        lot = str(_pick(rec, "lot") or "All lots")
        rows.append(
            {
                "date": pd.to_datetime(raw_date, format="%m/%d/%Y", errors="coerce"),
                "purchase": purchase,
                "lot": lot,
                "lot_min_head": lot_min_head(lot),
                "head": _num(_pick(rec, "head")) or 0.0,
                "price_usd_hd": price,
            }
        )
    cols = ["date", "purchase", "lot", "lot_min_head", "head", "price_usd_hd"]
    return pd.DataFrame(rows, columns=cols).dropna(subset=["date"])


def weekly_price(df: pd.DataFrame, purchase: str, min_lot_head: int = 2400) -> pd.DataFrame:
    """One price per week for cash or formula: the largest lot bucket at or above min_lot_head,
    else the largest bucket the report has. Returns date, lot, head, price_usd_hd."""
    by_week: dict[pd.Timestamp, list[dict]] = {}
    for r in df.to_dict("records"):
        if r["purchase"] == purchase:
            by_week.setdefault(r["date"], []).append(r)
    out = []
    for when, rows in sorted(by_week.items()):
        pick = [r for r in rows if r["lot_min_head"] >= min_lot_head]
        if not pick:
            largest = max(r["lot_min_head"] for r in rows)
            pick = [r for r in rows if r["lot_min_head"] == largest]
        head = sum(float(r["head"]) for r in pick)
        if head > 0:
            price = sum(float(r["price_usd_hd"]) * float(r["head"]) for r in pick) / head
        else:
            price = sum(float(r["price_usd_hd"]) for r in pick) / len(pick)
        lots = ", ".join(sorted({str(r["lot"]) for r in pick}))
        out.append({"date": when, "lot": lots, "head": head, "price_usd_hd": price})
    return pd.DataFrame(out, columns=["date", "lot", "head", "price_usd_hd"])


def fetch_feeder_pig(api_key: str, weeks: int = 104) -> pd.DataFrame:
    if not api_key:
        raise FetchError("no USDA MyMarketNews API key (USDA_MMN_API_KEY in .env)")
    end = date.today()
    start = end - timedelta(weeks=weeks)
    data = get_json(
        MARS,
        params={"q": f"report_begin_date={start:%m/%d/%Y}:{end:%m/%d/%Y}", "allSections": "true"},
        auth=(api_key, ""),
    )
    write_cached_json("usda_2810_raw.json", data)
    results: list[dict] = []
    if isinstance(data, dict):
        results = data.get("results", [])
    elif isinstance(data, list):  # allSections returns one block per section
        for block in data:
            if isinstance(block, dict):
                results.extend(block.get("results", []))
    df = parse_feeder_pig(results)
    if df.empty:
        raise FetchError(
            "report 2810 returned no early-weaned rows (see data/cache/usda_2810_raw.json)"
        )
    return df
