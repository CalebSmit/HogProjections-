"""Market price calculations. Pure: DataFrames in, DataFrames out.

CME Lean Hog Index (docs/research/domain.md §3): two-day weighted average of producer-sold
barrows and gilts, Negotiated + Negotiated Formula + Swine/Pork Market Formula, from LM_HG201:
    index = Σ(head × carcass wt × net price) / Σ(head × carcass wt)
The index is dated by the first of its two slaughter days. Checked: slaughter days Oct 12-13,
2026 give 75.75, CME's published index for Oct 12, 2026.
"""

from collections.abc import Sequence
from datetime import date, timedelta

import numpy as np
import pandas as pd

INDEX_PURCHASE_TYPES = [
    "Prod. Sold Negotiated",
    "Prod. Sold Negotiated Formula",
    "Prod. Sold Swine or Pork Market Formula",
]


def lean_hog_index(hg201: pd.DataFrame) -> pd.DataFrame:
    """One row per index date: index value ($/cwt carcass), head and carcass weight."""
    d = hg201[hg201["purchase_type"].isin(INDEX_PURCHASE_TYPES)]
    head = np.asarray(d["head_count"], dtype=float)
    price = np.asarray(d["avg_net_price_cwt_carcass"], dtype=float)
    weight = np.asarray(d["avg_weight_lb_carcass"], dtype=float)
    ok = ~(np.isnan(head) | np.isnan(price) | np.isnan(weight))  # USDA blanks confidential rows
    day = pd.to_datetime(d["slaughter_date"]).to_numpy()[ok]
    cwt = head[ok] * weight[ok] / 100

    days, which = np.unique(day, return_inverse=True)  # sorted slaughter days
    day_head = np.bincount(which, head[ok])
    day_cwt = np.bincount(which, cwt)
    day_value = np.bincount(which, cwt * price[ok])

    def pair(a: np.ndarray) -> np.ndarray:
        """Each slaughter day plus the next one."""
        return a[:-1] + a[1:]

    return pd.DataFrame(
        {
            "index_date": days[:-1],
            "lean_hog_index_usd_per_cwt_carcass": pair(day_value) / pair(day_cwt),
            "head_count": pair(day_head),
            "avg_weight_lb_carcass": pair(day_cwt) * 100 / pair(day_head),
        }
    )


def seasonal_factors(index: pd.DataFrame) -> pd.DataFrame:
    """Average index by calendar month ÷ the average of each month's own year.

    1.10 means that month typically runs 10% above its year's average. Only complete
    calendar years count, so a partial year doesn't skew the months it covers.
    """
    dates = pd.to_datetime(index["index_date"])
    year, month = np.asarray(dates.dt.year), np.asarray(dates.dt.month)
    price = index["lean_hog_index_usd_per_cwt_carcass"].to_numpy(dtype=float)
    per_year = []
    for y in np.unique(year):
        in_year = year == y
        if len(np.unique(month[in_year])) < 12:
            continue
        monthly = np.array([price[in_year & (month == m)].mean() for m in range(1, 13)])
        per_year.append(monthly / monthly.mean())
    if not per_year:
        return pd.DataFrame(columns=["month", "factor", "years"])
    return pd.DataFrame(
        {"month": range(1, 13), "factor": np.mean(per_year, axis=0), "years": len(per_year)}
    )


def seasonal_price_on(
    days: Sequence[date], start: date, price_now: float, factors: pd.DataFrame
) -> np.ndarray:
    """Hog price on each day if it follows the typical seasonal pattern from today's price.

    price(day) = price_now × factor(day) / factor(start). Monthly factors sit at mid-month and
    are interpolated by day of year (wrapping Dec -> Jan) so prices have no monthly steps.
    """
    if factors.empty:
        return np.full(len(days), price_now)
    mid_month_day = np.array([date(2001, m, 15).timetuple().tm_yday for m in range(1, 13)])
    f = factors.sort_values("month")["factor"].to_numpy(dtype=float)
    xp = np.concatenate([mid_month_day - 365, mid_month_day, mid_month_day + 365])
    fp = np.tile(f, 3)
    yday = np.array([d.timetuple().tm_yday for d in days], dtype=float)
    return price_now * np.interp(yday, xp, fp) / float(np.interp(start.timetuple().tm_yday, xp, fp))


def seasonal_price_path(
    start: date, weeks: int, price_now: float, factors: pd.DataFrame
) -> np.ndarray:
    """Weekly hog price that follows the typical seasonal pattern from today's price."""
    days = [start + timedelta(weeks=w) for w in range(weeks)]
    return seasonal_price_on(days, start, price_now, factors)
