"""The national view from USDA's keyless LMR datamart (no API key):

- LM_HG218 (slug 3458) prior-day hog report, by region (national, Iowa/Minnesota, Western and
  Eastern Corn Belt) and purchase type; hogs by state of origin; carcass weight discounts.
- LM_HG234 (slug 3452) prior-day sows and boars: negotiated sow prices by weight class.

All since Dec 2020 (when these reports started). Incremental like data/lmr.py: saved copy +
newly fetched days (a week of overlap), long format, one CSV per dataset.
"""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx
import pandas as pd

from hogproj.config import CACHE_DIR, SAMPLE_DIR
from hogproj.data.ams import DATAMART_URL, Source, _num

START = date(2020, 12, 7)
REGIONS = {
    "National Volume and Price Data": "National",
    "Iowa/Minnesota Volume and Price Data": "Iowa/Minnesota",
    "Western Cornbelt Volume and Price Data": "Western Corn Belt",
    "Eastern Cornbelt Volume and Price Data": "Eastern Corn Belt",
}
PURCHASE = {  # carcass-basis purchase types worth showing, short names
    "Negotiated (carcass basis)": "Negotiated",
    "Swine/Pork Market Formula (carcass basis)": "Pork market formula",
    "Other Market Formula (carcass basis)": "Other market formula",
    "Other Purchase Arrangement (carcass basis)": "Other purchase arrangement",
}
WEIGHT_BANDS = [145, 155, 165, 175, 185, 195, 205, 215, 225]


def _day(r: dict) -> pd.Timestamp:
    return pd.Timestamp(pd.to_datetime(r.get("reported_for_date") or r["report_date"],
                                       format="%m/%d/%Y"))  # fmt: skip


def parse_prices(rows: list[dict], region: str) -> list[dict]:
    out = []
    for r in rows:
        kind = PURCHASE.get(str(r.get("purchase_type")))
        if kind is None:
            continue
        out.append({"date": _day(r), "region": region, "purchase": kind,
                    "head": _num(r.get("head_count")),
                    "price": _num(r.get("price_avg"))})  # fmt: skip
    return out


def parse_origin(rows: list[dict]) -> list[dict]:
    return [{"date": _day(r), "state": str(r.get("state_desc")), "head": _num(r.get("head_count"))}
            for r in rows if r.get("state_desc")]  # fmt: skip


def parse_weights(rows: list[dict]) -> list[dict]:
    """Midpoint of USDA's min-max discount range for each carcass weight band ($/cwt)."""
    out = []
    for r in rows:
        for b in WEIGHT_BANDS:
            lo, hi = _num(r.get(f"diff_{b}_min")), _num(r.get(f"diff_{b}_max"))
            if lo is None or hi is None:
                continue
            out.append({"date": _day(r), "band_lb": b, "discount": (lo + hi) / 2,
                        "low": lo, "high": hi})  # fmt: skip
    return out


def parse_sows(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        if "Sows" not in str(r.get("purchase_type")):
            continue
        out.append({"date": _day(r), "weight_range": str(r.get("weight_range")),
                    "head": _num(r.get("head_count")), "price": _num(r.get("wtd_avg")),
                    "avg_weight": _num(r.get("avg_weight"))})  # fmt: skip
    return out


Parser = Callable[[list[dict]], list[dict]]
DATASETS: dict[str, tuple[int, list[tuple[str, Parser]], str, list[str]]] = {
    "prices": (3458, [(sec, lambda rows, reg=reg: parse_prices(rows, reg))
                      for sec, reg in REGIONS.items()], "lm_hg218_regional.csv",
               ["date", "region", "purchase"]),
    "origin": (3458, [("State of Origin", parse_origin)], "lm_hg218_origin.csv",
               ["date", "state"]),
    "weights": (3458, [("Carcass Weight Differentials", parse_weights)],
                "lm_hg218_weights.csv", ["date", "band_lb"]),
    "sows": (3452, [("National Volume and Price Data", parse_sows)], "lm_hg234_sows.csv",
             ["date", "weight_range"]),
}  # fmt: skip


def fetch(name: str, start: date, end: date, client: httpx.Client | None = None) -> pd.DataFrame:
    slug, sections, _, _ = DATASETS[name]
    rows: list[dict[str, Any]] = []
    with client or httpx.Client(timeout=120, follow_redirects=True) as c:
        for section, parser in sections:
            s = start
            while s <= end:
                stop = min(end, s + timedelta(days=364))
                q = f"report_date={s:%m/%d/%Y}:{stop:%m/%d/%Y}"
                resp = c.get(f"{DATAMART_URL}/{slug}/{section}", params={"q": q})
                resp.raise_for_status()
                rows += parser(resp.json().get("results", []))
                s = stop + timedelta(days=1)
    return pd.DataFrame(rows)


def load(name: str, offline: bool) -> tuple[pd.DataFrame, Source, str]:
    """Return (data, source, note). Never raises for network problems."""
    _, _, file, keys = DATASETS[name]
    cache = CACHE_DIR / file
    saved = (pd.read_csv(cache if cache.exists() else SAMPLE_DIR / file, parse_dates=["date"])
             if (cache.exists() or (SAMPLE_DIR / file).exists()) else pd.DataFrame())  # fmt: skip
    saved_source: Source = "cache" if cache.exists() else "sample"
    if not offline:
        try:
            since = (date.fromisoformat(str(saved["date"].max())[:10]) - timedelta(days=7)
                     if len(saved) else START)  # fmt: skip
            new = fetch(name, since, date.today())
            if new.empty:
                raise ValueError("USDA returned no rows")
            df = pd.concat([f for f in (saved, new) if not f.empty], ignore_index=True)
            df["date"] = pd.to_datetime(df["date"])
            df = df.drop_duplicates(keys, keep="last").sort_values(keys).reset_index(drop=True)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", "Live from USDA AMS LMR."
        except (httpx.HTTPError, ValueError, KeyError) as e:
            problem = f"Couldn't reach USDA ({type(e).__name__})."
    else:
        problem = "Offline mode."
    return saved, saved_source, f"{problem} Showing saved data."
