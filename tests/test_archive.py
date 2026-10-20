"""Weekly archive: joins on week ending Friday, annual averages, year change."""

import numpy as np
import pandas as pd
import pytest

from hogproj.archive import COLUMNS, annual, weekly, year_change


def _inputs():
    weeks = pd.to_datetime(["2025-01-10", "2025-01-17", "2026-01-09"])
    mk = pd.DataFrame({"week_ending": weeks, "index": [80.0, 82.0, 90.0],
                       "cutout": [90.0, 91.0, 99.0], "spread_per_head": [20.0, 19.0, 15.0],
                       "head": [1.2e6, 1.1e6, 1.0e6],
                       "weight_lb": [214.0, 215.0, 216.0]})  # fmt: skip
    pigs = pd.DataFrame({"week_ending": weeks, "cash_usd_per_head": [40.0, 42.0, 60.0]})
    corn = pd.DataFrame({"month": pd.to_datetime(["2025-01-01"]), "usd_per_bu": [4.5]})
    crush = pd.DataFrame(
        {"placed": pd.to_datetime(["2025-01-06", "2025-01-13"]), "status": ["sold", "on feed"],
         "margin_usd": [12.0, -3.0]}
    )  # fmt: skip
    return mk, pigs, corn, crush


def test_weekly_joins_each_source_on_its_week():
    w = weekly(*_inputs())
    assert list(w.columns[:1]) == ["week_ending"] and set(COLUMNS) <= set(w.columns)
    first = w.iloc[0]
    assert first["weaned_pig"] == 40.0
    assert first["crush_margin"] == 12.0  # placed Monday Jan 6 -> week ending Friday Jan 10
    assert np.isnan(w.iloc[1]["crush_margin"])  # still on feed: not realized
    assert first["corn"] == 4.5
    assert np.isnan(w.iloc[2]["corn"])  # month not reported


def test_annual_means_and_year_change():
    a = annual(weekly(*_inputs())).set_index("year")
    assert a.loc[2025, "index"] == pytest.approx(81.0)
    assert a.loc[2025, "weeks"] == 2
    assert year_change(a.reset_index(), "index") == pytest.approx(90 / 81 - 1)
    assert year_change(a.reset_index().iloc[:1], "index") is None


def test_short_weeks_drop_slaughter_totals():
    mk, pigs, corn, crush = _inputs()
    mk = mk.assign(days=[5, 4, 5])  # the second week had a holiday
    w = weekly(mk, pigs, corn, crush)
    assert np.isnan(w.iloc[1]["head"]) and w.iloc[0]["head"] == 1.2e6
