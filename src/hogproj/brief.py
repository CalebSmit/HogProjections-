"""The weekly brief: week-over-week and year-over-year moves, the biggest movers in words, and
the dates coming up. Pure: no Streamlit.
"""

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from hogproj.crush import LH_MONTHS, contract_expiry, contract_label


@dataclass
class Move:
    name: str
    unit: str  # e.g. "/cwt", "/head", "/bu"
    now: float
    week_ago: float | None
    year_ago: float | None
    as_of: pd.Timestamp

    @property
    def week_change(self) -> float | None:
        return None if self.week_ago is None else self.now - self.week_ago

    @property
    def week_pct(self) -> float | None:
        return None if not self.week_ago else self.now / self.week_ago - 1

    @property
    def year_pct(self) -> float | None:
        return None if not self.year_ago else self.now / self.year_ago - 1


def move(name: str, unit: str, dates: pd.Series | np.ndarray, values: pd.Series | np.ndarray,
         week_days: int = 7, year_days: int = 364) -> Move:  # fmt: skip
    """Latest value, and the last value at least `week_days` / `year_days` earlier."""
    d = pd.to_datetime(pd.Series(dates)).to_numpy()
    v = np.asarray(values, dtype=float)
    ok = ~np.isnan(v)
    d, v = d[ok], v[ok]
    if len(v) == 0:
        raise ValueError(f"no data for {name}")
    order = np.argsort(d)
    d, v = d[order], v[order]
    end = d[-1]

    def at(days: int) -> float | None:
        m = d <= end - np.timedelta64(days, "D")
        return float(v[m][-1]) if m.any() else None

    return Move(name, unit, float(v[-1]), at(week_days), at(year_days), pd.Timestamp(end))


def movers(moves: list[Move], n: int = 3) -> list[str]:
    """The biggest week-over-week moves, as sentences."""
    ranked = sorted((m for m in moves if m.week_pct is not None),
                    key=lambda m: abs(m.week_pct or 0), reverse=True)  # fmt: skip
    out = []
    for m in ranked[:n]:
        pct = m.week_pct or 0
        if abs(pct) < 0.005:
            out.append(f"{m.name} was steady at ${m.now:,.2f}{m.unit}.")
            continue
        verb = "rose" if pct > 0 else "fell"
        out.append(f"{m.name} {verb} {abs(pct):.1%} on the week to ${m.now:,.2f}{m.unit}.")
    return out


def calendar(today: date, months_ahead: int = 4) -> list[tuple[date, str]]:
    """Dated events in the next few months: lean hog contract expiries (exact, 10th business day)
    and the recurring USDA reports the app reads."""
    end = today + timedelta(days=30 * months_ahead)
    events: list[tuple[date, str]] = []
    y, m = today.year, today.month
    while date(y, m, 1) <= end:
        if m in LH_MONTHS:
            exp = contract_expiry(y, m)
            if today <= exp <= end:
                events.append((exp, f"{contract_label((y, m))} lean hogs expire"))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    # Next Friday: weekly feeder pig and feedstuff reports.
    friday = today + timedelta(days=(4 - today.weekday()) % 7)
    events.append((friday, "USDA feeder pig and feedstuff reports (weekly, Fridays)"))
    return sorted(events)


QUARTERLY_REPORTS = (
    "USDA Quarterly Hogs and Pigs: late March, June, September and December. Check the NASS "
    "calendar for exact dates."
)
