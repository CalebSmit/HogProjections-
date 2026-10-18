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


def lean_hog_expiry(year: int, month: int) -> date:
    """Last trading day of a HE contract: 10th business day (Mon-Fri; exchange holidays
    are ignored, so in a holiday month the real expiry is a day later)."""
    d, count = date(year, month, 1), 0
    while True:
        if d.weekday() < 5:
            count += 1
            if count == 10:
                return d
        d = date.fromordinal(d.toordinal() + 1)


def in_roll_gap(d: date) -> bool:
    """True after a contract's expiry but still on/before the 14th. On those days a front-month
    series already quotes the next contract, while lean_hog_contract_for still maps sales to
    the expiring one. Those days are dropped so basis and pricing use the same contract."""
    return (
        d.month in LEAN_HOG_CONTRACT_MONTHS and d.day <= 14 and d > lean_hog_expiry(d.year, d.month)
    )


def daily_basis(index_cwt: pd.Series, nearby_futures_cwt: pd.Series) -> pd.Series:
    """Index minus front-month futures on each date both series have, excluding roll-gap days.
    The front-month series must roll at expiry (Yahoo HE=F does [VERIFY])."""
    df = pd.concat({"index": index_cwt, "futures": nearby_futures_cwt}, axis=1).dropna()
    df.index = pd.to_datetime(df.index)
    keep = [not in_roll_gap(ts.date()) for ts in df.index]
    df = df.loc[keep]
    return pd.Series(
        (df["index"] - df["futures"]).to_numpy(), index=df.index, name="basis_cwt", dtype="float64"
    )


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
