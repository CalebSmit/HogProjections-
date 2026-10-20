"""Backtest of the seasonal hog price estimate."""

import numpy as np
import pandas as pd

from hogproj import accuracy


def _index(noise: float = 0.0) -> pd.DataFrame:
    """A perfectly seasonal index (±10% by month) plus optional noise."""
    days = pd.bdate_range("2017-01-02", "2026-10-16")
    rng = np.random.default_rng(1)
    v = 80 * (1 + 0.1 * np.sin((days.month - 1) / 12 * 2 * np.pi)) + noise * rng.normal(
        size=len(days)
    )
    return pd.DataFrame({"index_date": days, "lean_hog_index_usd_per_cwt_carcass": v})


def test_seasonal_beats_no_change_on_a_seasonal_market():
    s = accuracy.summary(accuracy.backtest(_index()))
    assert list(s["months_ahead"]) == list(accuracy.HORIZONS)
    assert (s["better_than_no_change"] > 0.5).all()
    assert (s["miss"] < 2).all()  # near-perfect on a perfectly seasonal series


def test_no_future_data_leaks():
    ix = _index()
    bt = accuracy.backtest(ix)
    last_full = pd.Timestamp("2026-09-01")  # Oct 2026 is partial, so never a target
    assert (
        bt["made"] + pd.to_timedelta(bt["months_ahead"] * 31, unit="D")
    ).max() <= last_full + pd.Timedelta(days=31 * 9)
    targets = [
        m + pd.DateOffset(months=h) for m, h in zip(bt["made"], bt["months_ahead"], strict=True)
    ]
    assert max(targets) <= last_full


def test_band_lookup():
    s = accuracy.summary(accuracy.backtest(_index(noise=3)))
    assert accuracy.band_cwt(s, 5.3) == float(
        s.loc[s["months_ahead"] == 5, "within_8_in_10"].iloc[0]
    )
    assert accuracy.band_cwt(s, 20) == float(s["within_8_in_10"].iloc[-1])
    assert accuracy.band_cwt(accuracy.summary(pd.DataFrame()), 3) is None
