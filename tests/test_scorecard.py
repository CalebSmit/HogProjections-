"""Weekly scorecard rows."""

import numpy as np
import pandas as pd

from hogproj import scorecard as sc


def _daily(last: float) -> pd.Series:
    idx = pd.date_range("2019-01-01", "2026-10-16", freq="D")
    v = 80 + (idx.year - 2019).to_numpy(dtype=float)
    v[idx >= "2026-01-01"] = last
    return pd.Series(v, index=idx)


def test_low_price_is_bad_for_producers_when_higher_helps():
    r = sc.row(sc.Metric("Lean hogs", _daily(60), suffix="/cwt", good=1))
    assert r is not None
    assert r.tone == "bad" and r.status == "Lowest in 7 years"
    assert r.year_pct is not None and abs(r.year_pct - (60 / 86 - 1)) < 1e-9  # Oct 17, 2025
    assert r.week_change == 0
    assert r.rank_text() == "lowest"
    assert r.fmt(-2.5) == "−$2.50/cwt" and r.fmt(84, unit=False) == "$84.00"


def _row(m: sc.Metric) -> sc.Row:
    r = sc.row(m)
    assert r is not None
    return r


def test_low_cost_is_good_and_neutral_metrics_stay_grey():
    assert _row(sc.Metric("Corn", _daily(60), good=-1)).tone == "good"
    assert _row(sc.Metric("Weaned pigs", _daily(60))).tone == "neutral"
    inside = _row(sc.Metric("Lean hogs", _daily(84.5), good=1))
    assert inside.tone == "neutral" and inside.status == "Normal for the season"


def test_counts_use_last_full_week():
    idx = pd.date_range("2024-01-01", "2026-10-20", freq="D")  # Oct 17-20 is a partial week
    r = sc.row(sc.Metric("Slaughter", pd.Series(1.0, index=idx), prefix="", how="sum"))
    assert r is not None and r.latest == 7 and r.as_of == pd.Timestamp("2026-10-16")


def test_sparkline_and_empty_series():
    assert sc.sparkline([1, 2, 3], "#000").startswith("<svg")
    assert sc.sparkline([1], "#000") == ""
    assert sc.row(sc.Metric("Empty", pd.Series(dtype=float))) is None
    assert len(sc.table(sc.build([sc.Metric("x", _daily(80.0))]))) == 1
    assert not np.isnan(sc.build([sc.Metric("x", _daily(80.0))])[0].latest)
