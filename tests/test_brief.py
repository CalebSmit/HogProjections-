"""Weekly brief: moves, movers in words, calendar."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from hogproj.brief import calendar, move, movers


def _series(days: int = 400, start: float = 100.0, step: float = 0.1):
    d = pd.bdate_range("2025-06-02", periods=days)
    return d, start + step * np.arange(days)


def test_move_week_and_year():
    d, v = _series()
    m = move("Index", "/cwt", d, v)
    assert m.now == pytest.approx(v[-1])
    assert m.week_ago == pytest.approx(v[-6])  # 5 business days = 7 calendar days back
    assert m.year_ago is not None and m.year_pct is not None and m.year_pct > 0
    assert m.week_change == pytest.approx(0.5)


def test_move_without_a_year_of_history():
    d, v = _series(days=30)
    assert move("x", "", d, v).year_ago is None


def test_move_ignores_missing_values():
    d, v = _series(days=20)
    v = v.copy()
    v[-1] = np.nan
    assert move("x", "", d, v).now == pytest.approx(v[-2])


def test_movers_sorted_by_size_in_words():
    d, v = _series()
    big = move("Weaned pigs", "/head", d, v * np.linspace(1, 1.5, len(v)))
    small = move("Corn", "/bu", d, v)
    flat = move("Cutout", "/cwt", d, np.full(len(v), 90.0))
    out = movers([small, flat, big])
    assert out[0].startswith("Weaned pigs rose")
    assert out[-1] == "Cutout was steady at $90.00/cwt."


def test_calendar_has_exact_expiries_in_order():
    ev = calendar(date(2026, 10, 20), months_ahead=4)
    assert (date(2026, 12, 14), "Dec 2026 lean hogs expire") in ev
    assert (date(2027, 2, 12), "Feb 2027 lean hogs expire") in ev
    assert ev == sorted(ev)
    assert any("feeder pig" in e for _, e in ev)


def test_move_without_data_raises():
    with pytest.raises(ValueError):
        move("x", "", pd.Series([], dtype="datetime64[ns]"), np.array([], dtype=float))
