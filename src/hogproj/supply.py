"""Industry hog supply from the quarterly NASS Hogs and Pigs report. Pure: DataFrames in/out.

Each class of hogs on farms reaches market at a predictable time (docs/research/domain.md §4):
heavier market hogs within weeks, lighter ones months later; the latest pig crop about six
months on; farrowing intentions about nine to twelve. Comparing each with the same report a
year earlier gives a forward-looking supply signal. The windows are rules of thumb [VERIFY:
calibrate against FIS slaughter data].
"""

from typing import cast

import pandas as pd
from pydantic import BaseModel


class Window(BaseModel):
    label: str
    series: str
    months_from: float  # months after the report's reference date
    months_to: float
    kind: str = "actual"


WINDOWS = [
    Window(label="180 lb and up", series="market_ge180", months_from=0, months_to=1.5),
    Window(label="120–179 lb", series="market_120_179", months_from=1.5, months_to=3),
    Window(label="50–119 lb", series="market_50_119", months_from=3, months_to=4.5),
    Window(label="Under 50 lb", series="market_lt50", months_from=4.5, months_to=6),
]


def _ts(x: object) -> pd.Timestamp:
    return cast(pd.Timestamp, pd.Timestamp(str(x)))


def _value(df: pd.DataFrame, series: str, when: pd.Timestamp, kind: str = "actual") -> float | None:
    m = df[(df["series"] == series) & (df["period_start"] == when) & (df["kind"] == kind)]
    return float(m["value"].iloc[0]) if len(m) else None


def latest_report(df: pd.DataFrame) -> pd.Timestamp:
    """Reference date (first of Mar/Jun/Sep/Dec) of the newest inventory in the data."""
    inv = df[(df["series"] == "all_hogs") & (df["kind"] == "actual")]
    return _ts(inv["period_start"].max())


def yoy(df: pd.DataFrame, series: str, when: pd.Timestamp, kind: str = "actual") -> dict:
    """Value at `when`, a year earlier (always the actual), and the % change."""
    now = _value(df, series, when, kind)
    before = _value(df, series, when - pd.DateOffset(years=1), "actual")
    pct = (now / before - 1) if now is not None and before else None
    return {"value": now, "year_ago": before, "pct": pct}


def outlook(df: pd.DataFrame) -> pd.DataFrame:
    """Expected market supply by time window vs a year earlier, from the latest report.

    Rows: label, window start/end dates, value, year-ago value, % change, basis.
    """
    ref = latest_report(df)
    rows = []
    for w in WINDOWS:
        y = yoy(df, w.series, ref)
        rows.append({"label": w.label, "basis": "Market hogs on farms", "start": ref
                     + pd.DateOffset(days=round(w.months_from * 30.4)), "end": ref
                     + pd.DateOffset(days=round(w.months_to * 30.4)), **y})  # fmt: skip

    # Latest pig crop (the quarter ending at the report) reaches market ~6 months on.
    crops = df[(df["series"] == "pig_crop") & (df["kind"] == "actual")]
    last_crop = _ts(crops["period_start"].max())
    y = yoy(df, "pig_crop", last_crop)
    rows.append({"label": f"Pig crop {last_crop:%b}–{last_crop + pd.DateOffset(months=2):%b}",
                 "basis": "Pigs born last quarter", "start": last_crop + pd.DateOffset(months=6),
                 "end": last_crop + pd.DateOffset(months=9), **y})  # fmt: skip

    # Farrowing intentions for the next two quarters: pigs reach market ~6 months after birth.
    intents = df[(df["series"] == "sows_farrowed") & (df["kind"] != "actual")]
    newest = intents[intents["released"] == intents["released"].max()]
    for _, r in pd.DataFrame(newest).sort_values("period_start").iterrows():
        start = _ts(r["period_start"])
        if start <= last_crop:
            continue
        y = yoy(df, "sows_farrowed", start, str(r["kind"]))
        rows.append({"label": f"Farrowings {start:%b}–{start + pd.DateOffset(months=2):%b}",
                     "basis": "Sows expected to farrow", "start": start + pd.DateOffset(months=6),
                     "end": start + pd.DateOffset(months=9), **y})  # fmt: skip
    return pd.DataFrame(rows)


def next_six_months(df: pd.DataFrame) -> dict:
    """Head-weighted change in market hogs on farms (all four weight classes) vs a year ago."""
    ref = latest_report(df)
    now = sum(_value(df, w.series, ref) or 0 for w in WINDOWS)
    before = sum(_value(df, w.series, ref - pd.DateOffset(years=1)) or 0 for w in WINDOWS)
    return {"value": now, "year_ago": before, "pct": (now / before - 1) if before else None}


def history(df: pd.DataFrame, series: str) -> pd.DataFrame:
    h = df[(df["series"] == series) & (df["kind"] == "actual")]
    return (
        pd.DataFrame(h, columns=["period_start", "value"])
        .sort_values("period_start")
        .reset_index(drop=True)
    )


def lowest_since(df: pd.DataFrame, series: str) -> int | None:
    """Year of the last report with a value at or below the latest one (None if record low)."""
    h = history(df, series)
    last = h.iloc[-1]
    same_month = h[(h["period_start"].dt.month == last["period_start"].month)].iloc[:-1]
    lower = same_month[same_month["value"] <= last["value"]]
    return int(lower["period_start"].dt.year.max()) if len(lower) else None
