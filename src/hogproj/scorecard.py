"""The weekly scorecard: each market number with its change on the week and the year, where it
sits against the same time in past years, and what that means for a hog producer. Pure.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from hogproj import seasonal


@dataclass
class Metric:
    name: str
    series: pd.Series  # dated values (daily or weekly)
    prefix: str = "$"
    suffix: str = ""
    decimals: int = 2
    good: int = 0  # +1: higher helps a hog producer, -1: higher hurts, 0: depends on the seat
    how: str = "mean"  # weekly mean, or "sum" for counts (slaughter)
    note: str = ""
    week: str = "W-FRI"  # week end (slaughter weeks run Sunday to Saturday: "W-SAT")
    year_ago: pd.Series | None = None  # the source's own year-ago figures, if it publishes them


@dataclass
class Row:
    name: str
    latest: float
    as_of: pd.Timestamp
    week_change: float | None
    year_pct: float | None
    verdict: seasonal.Verdict | None
    tone: str  # "good", "bad", "neutral"
    status: str  # "High for the season", "Lowest in 6 years", "Normal"...
    trend: list[float] = field(default_factory=list)  # last 26 weekly values
    metric: Metric | None = None

    def fmt(self, x: float, unit: bool = True) -> str:
        m = self.metric or Metric(self.name, pd.Series(dtype=float))
        sign = "−" if x < 0 else ""
        return f"{sign}{m.prefix}{abs(x):,.{m.decimals}f}{m.suffix if unit else ''}"

    def rank_text(self) -> str:
        """'lowest', 'highest' or '40th pct' against the same week in past years."""
        v = self.verdict
        if v is None:
            return ""
        if v.extreme:
            return v.extreme
        n = round(v.percentile)
        suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix} pct"


def _at_or_before(s: pd.Series, day: pd.Timestamp) -> float | None:
    x = s[s.index <= day]
    return float(x.iloc[-1]) if len(x) else None


def row(m: Metric) -> Row | None:
    s = pd.Series(m.series.to_numpy(dtype=float), index=pd.to_datetime(m.series.index))
    s = s.dropna().sort_index()
    if s.empty:
        return None
    weeks = seasonal.by_week(s, m.how, m.week)
    if m.how == "sum":  # counts: compare whole weeks, leaving out the one still in progress
        weeks = weeks[weeks["week_ending"] <= s.index.max()]
        if weeks.empty:
            return None
        latest, as_of = float(weeks["value"].iloc[-1]), pd.Timestamp(weeks["week_ending"].iloc[-1])
        prev = float(weeks["value"].iloc[-2]) if len(weeks) > 1 else None
        if m.year_ago is not None:  # e.g. USDA's own same-days-a-year-ago slaughter
            ya = pd.Series(m.year_ago.to_numpy(dtype=float), index=pd.to_datetime(m.year_ago.index))
            ya_w = ya.resample(m.week).sum(min_count=1)
            ago = float(ya_w.loc[as_of]) if as_of in ya_w.index else None
        else:
            ago_w = weeks[(weeks["year"] == weeks["year"].iloc[-1] - 1)
                          & (weeks["wk"] == weeks["wk"].iloc[-1])]  # fmt: skip
            ago = float(ago_w["value"].iloc[0]) if len(ago_w) else None
    else:
        latest, as_of = float(s.iloc[-1]), pd.Timestamp(s.index[-1])
        prev = _at_or_before(s, as_of - pd.Timedelta(days=7))
        ago = _at_or_before(s, as_of - pd.Timedelta(days=364))
    v = seasonal.verdict(weeks)
    tone, status = "neutral", "Normal for the season"
    if v is not None:
        if v.where != "inside":
            high = v.where == "above"
            status = (f"{'Highest' if high else 'Lowest'} in {v.n_years} years" if v.extreme
                      else f"{'High' if high else 'Low'} for the season")  # fmt: skip
            if m.good:
                tone = "good" if (high and m.good > 0) or (not high and m.good < 0) else "bad"
    else:
        status = "Not enough history"
    return Row(m.name, latest, as_of, None if prev is None else latest - prev,
               None if not ago else latest / ago - 1, v, tone, status,
               [float(x) for x in weeks["value"].tail(26)], m)  # fmt: skip


def build(metrics: list[Metric]) -> list[Row]:
    return [r for r in (row(m) for m in metrics) if r is not None]


def table(rows: list[Row]) -> pd.DataFrame:
    """Plain table for Excel."""
    return pd.DataFrame([{
        "measure": r.name, "latest": r.latest, "as_of": r.as_of, "week_change": r.week_change,
        "year_change_pct": r.year_pct,
        "percentile_vs_past_years": None if r.verdict is None else r.verdict.percentile,
        "past_years_low": None if r.verdict is None else r.verdict.lo,
        "past_years_high": None if r.verdict is None else r.verdict.hi,
        "status": r.status, "for_hog_producers": r.tone,
    } for r in rows])  # fmt: skip


def sparkline(values: list[float], color: str, width: int = 96, height: int = 26) -> str:
    """Inline SVG trend line (no axes), last point marked."""
    v = np.asarray([x for x in values if np.isfinite(x)], dtype=float)
    if len(v) < 2:
        return ""
    lo, hi = float(v.min()), float(v.max())
    span = hi - lo or 1.0
    xs = np.linspace(2, width - 4, len(v))
    ys = height - 3 - (v - lo) / span * (height - 6)
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys, strict=True))
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'aria-hidden="true"><polyline points="{pts}" fill="none" stroke="{color}" '
        f'stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="2.4" fill="{color}"/></svg>'
    )
