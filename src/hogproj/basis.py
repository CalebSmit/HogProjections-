"""Historical lean hog basis: CME Lean Hog Index minus nearby Lean Hog futures. Pure functions.

For every trading day d: basis_d = Index_d - NearbyFutures_d. Daily values are averaged into
one number per (year, month), and then averaged across years per calendar month. The result
is added to today's futures price for the month each load is sold.
"""

import pandas as pd


def daily_basis(index_cwt: pd.Series, nearby_futures_cwt: pd.Series) -> pd.Series:
    """Both inputs are indexed by date. Only dates present in both series are used."""
    df = pd.concat({"index": index_cwt, "futures": nearby_futures_cwt}, axis=1).dropna()
    df.index = pd.to_datetime(df.index)
    return (df["index"] - df["futures"]).rename("basis_cwt")


def basis_by_year_month(daily: pd.Series) -> pd.DataFrame:
    """Rows = year, columns = month 1..12, values = average basis that month."""
    df = daily.to_frame()
    df["year"] = df.index.year  # type: ignore[attr-defined]
    df["month"] = df.index.month  # type: ignore[attr-defined]
    table = df.pivot_table(index="year", columns="month", values="basis_cwt", aggfunc="mean")
    return table.reindex(columns=range(1, 13))


def average_basis_by_month(
    by_year_month: pd.DataFrame, years: list[int] | None = None
) -> dict[int, float]:
    """Average of each calendar month across the chosen years (default: all). Missing -> 0."""
    t = by_year_month if years is None else by_year_month.loc[by_year_month.index.isin(years)]
    means = t.mean(axis=0, skipna=True).to_dict()
    out: dict[int, float] = {}
    for m in range(1, 13):
        v = means.get(m)
        out[m] = float(v) if v is not None and pd.notna(v) else 0.0
    return out
