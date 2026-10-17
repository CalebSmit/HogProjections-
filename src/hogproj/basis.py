"""Lean hog contract calendar and historical basis. Pure functions.

Basis = CME Lean Hog Index - nearby Lean Hog futures, on the same day. Daily values are
averaged per (year, half-month period) and then across years, per period. The projection
adds that average to today's futures price for the contract each load is priced off.

Half-month periods follow Iowa State Ag Decision Maker B2-41 ("Lean Hog Basis"): days 1-14
and 15-end of each month, so 24 periods a year. HE futures expire on the 10th business day of
the contract month. Sales on days 1-14 of a contract month use that month's contract; from the
15th on they use the next contract.
"""

from datetime import date

import pandas as pd

# CME Lean Hog (HE) listed contract months: Feb Apr May Jun Jul Aug Oct Dec
LEAN_HOG_CONTRACT_MONTHS = (2, 4, 5, 6, 7, 8, 10, 12)
PERIODS = range(1, 25)
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def lean_hog_contract_for(d: date) -> str:
    """Contract code 'YYYY-MM' that prices hogs sold on date d."""
    if d.month in LEAN_HOG_CONTRACT_MONTHS and d.day <= 14:
        return f"{d.year}-{d.month:02d}"
    later = [m for m in LEAN_HOG_CONTRACT_MONTHS if m > d.month]
    if later:
        return f"{d.year}-{later[0]:02d}"
    return f"{d.year + 1}-{LEAN_HOG_CONTRACT_MONTHS[0]:02d}"


def basis_period(d: date) -> int:
    """Half-month period 1..24: Jan 1-14 = 1, Jan 15-31 = 2, ..., Dec 15-31 = 24."""
    return (d.month - 1) * 2 + (1 if d.day <= 14 else 2)


def period_label(period: int) -> str:
    month = MONTH_ABBR[(period - 1) // 2]
    return f"{month} 1-14" if period % 2 == 1 else f"{month} 15-end"


def daily_basis(index_cwt: pd.Series, nearby_futures_cwt: pd.Series) -> pd.Series:
    """Both inputs are indexed by date. Only dates present in both series are used."""
    df = pd.concat({"index": index_cwt, "futures": nearby_futures_cwt}, axis=1).dropna()
    df.index = pd.to_datetime(df.index)
    return (df["index"] - df["futures"]).rename("basis_cwt")


def basis_by_year_period(daily: pd.Series) -> pd.DataFrame:
    """Rows = year, columns = period 1..24, values = average basis in that half-month."""
    when = pd.Series(pd.to_datetime(daily.index)).dt
    df = pd.DataFrame(
        {
            "basis_cwt": daily.to_numpy(),
            "year": when.year.to_numpy(),
            "period": ((when.month - 1) * 2 + (when.day > 14) + 1).to_numpy(),
        }
    )
    table = df.pivot_table(index="year", columns="period", values="basis_cwt", aggfunc="mean")
    return table.reindex(columns=list(PERIODS))


def average_basis_by_period(
    by_year_period: pd.DataFrame, years: list[int] | None = None
) -> dict[int, float]:
    """Average of each period across the chosen years (default: all). No data -> 0."""
    t = by_year_period if years is None else by_year_period.loc[by_year_period.index.isin(years)]
    means = t.mean(axis=0, skipna=True).to_dict()
    out: dict[int, float] = {}
    for period in PERIODS:
        v = means.get(period)
        out[period] = float(v) if v is not None and pd.notna(v) else 0.0
    return out
