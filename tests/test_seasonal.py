"""Seasonal ranges and verdicts."""

import numpy as np
import pandas as pd

from hogproj import seasonal


def _series(last_year_value: float, years=range(2019, 2027)) -> pd.Series:
    """Daily values: each year flat at 70 + (year - 2019), the final year as given."""
    idx = pd.date_range(f"{min(years)}-01-01", "2026-10-16", freq="D")
    v = 70 + (idx.year - 2019).to_numpy(dtype=float)
    v[idx.year == 2026] = last_year_value
    return pd.Series(v, index=idx)


def test_by_week_folds_week_53_and_keeps_last_day():
    wk = seasonal.by_week(_series(80))
    assert wk["wk"].max() == 52
    assert wk["through"].iloc[-1] == pd.Timestamp("2026-10-16")


def test_band_skips_2020_and_uses_five_prior_years():
    b = seasonal.band(seasonal.by_week(_series(80)), 2026)
    assert b.attrs["years"] == [2021, 2022, 2023, 2024, 2025]
    assert b["lo"].min() == 72 and b["hi"].max() == 76


def test_verdict_below_range_and_lowest():
    v = seasonal.verdict(seasonal.by_week(_series(60)))
    assert v is not None and v.where == "below" and v.extreme == "lowest"
    assert v.percentile == 0
    assert v.sentence("their").startswith("below their 2021–25 range for mid-October")
    assert "lowest for the week in 7 years" in v.sentence()  # 2019, 2021-26


def test_verdict_inside_range():
    v = seasonal.verdict(seasonal.by_week(_series(74.5)))
    assert v is not None and v.where == "inside" and v.extreme == ""
    assert 0 < v.percentile < 100


def test_verdict_needs_history():
    s = pd.Series(np.ones(30), index=pd.date_range("2026-09-01", periods=30))
    assert seasonal.verdict(seasonal.by_week(s)) is None
