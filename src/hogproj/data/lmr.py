"""Generic USDA AMS LMR datamart loader for one daily report section. No API key needed.

A `Spec` names the report slug, section, date field and the columns to keep. Loading is
incremental like data/ams.py: saved copy (cache, else bundled sample) + newly fetched days (with
a week of overlap for corrections), back to `HISTORY_START`. Values arrive as strings with
thousands separators; they're converted to floats here.
"""

from datetime import date, timedelta
from typing import Any

import httpx
import pandas as pd
from pydantic import BaseModel

from hogproj.config import CACHE_DIR, SAMPLE_DIR
from hogproj.data.ams import DATAMART_URL, Source, _num

HISTORY_START = date(2020, 1, 1)


class Spec(BaseModel):
    name: str  # what the UI calls it
    slug: int
    section: str
    date_field: str
    fields: dict[str, str]  # USDA field -> our column
    file: str


CUTOUT = Spec(
    name="pork cutout (LM_PK602)",
    slug=2498,
    section="Cutout and Primal Values",
    date_field="report_date",
    fields={
        "pork_carcass": "carcass",
        "pork_loin": "loin",
        "pork_butt": "butt",
        "pork_picnic": "picnic",
        "pork_rib": "rib",
        "pork_ham": "ham",
        "pork_belly": "belly",
        "total_loads_date_1": "loads",
    },
    file="lm_pk602_cutout.csv",
)


def parse(payload: dict[str, Any], spec: Spec) -> pd.DataFrame:
    rows = []
    for r in payload.get("results", []):
        when = r.get(spec.date_field)
        if not when:
            continue
        row: dict[str, Any] = {"date": pd.to_datetime(when, format="%m/%d/%Y")}
        row.update({col: _num(r.get(src)) for src, col in spec.fields.items()})
        rows.append(row)
    df = pd.DataFrame(rows, columns=["date", *spec.fields.values()])
    return df.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)


def fetch(spec: Spec, start: date, end: date, client: httpx.Client | None = None) -> pd.DataFrame:
    """Fetch in one-year requests."""
    parts = []
    with client or httpx.Client(timeout=90, follow_redirects=True) as c:
        while start <= end:
            stop = min(end, start + timedelta(days=364))
            q = f"report_date={start:%m/%d/%Y}:{stop:%m/%d/%Y}"
            resp = c.get(f"{DATAMART_URL}/{spec.slug}/{spec.section}", params={"q": q})
            resp.raise_for_status()
            parts.append(parse(resp.json(), spec))
            start = stop + timedelta(days=1)
    parts = [p for p in parts if not p.empty]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def merge(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    both = pd.concat([f for f in (old, new) if not f.empty], ignore_index=True)
    both["date"] = pd.to_datetime(both["date"])
    return both.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)


def _read(path) -> pd.DataFrame:  # noqa: ANN001 - Path
    return pd.read_csv(path, parse_dates=["date"])


def load(
    spec: Spec, offline: bool, start: date = HISTORY_START
) -> tuple[pd.DataFrame, Source, str]:
    """Return (data, source, note). Never raises for network problems."""
    cache = CACHE_DIR / spec.file
    saved = _read(cache) if cache.exists() else _read(SAMPLE_DIR / spec.file)
    saved_source: Source = "cache" if cache.exists() else "sample"
    if not offline:
        try:
            first = date.fromisoformat(str(saved["date"].min())[:10])
            last = date.fromisoformat(str(saved["date"].max())[:10])
            new = fetch(spec, last - timedelta(days=7), date.today())
            if first > start + timedelta(days=7):
                new = (
                    merge(fetch(spec, start, first), new)
                    if not new.empty
                    else fetch(spec, start, first)
                )
            if new.empty:
                raise ValueError("USDA returned no rows")
            df = merge(saved, new)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", f"Live from USDA AMS ({spec.name})."
        except (httpx.HTTPError, ValueError) as e:
            problem = f"Couldn't reach USDA ({type(e).__name__})."
    else:
        problem = "Offline mode."
    last_day = pd.Timestamp(str(saved["date"].max()))
    return saved, saved_source, f"{problem} Showing saved {spec.name} through {last_day:%b %d, %Y}."
