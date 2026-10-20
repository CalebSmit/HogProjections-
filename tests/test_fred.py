"""FRED prime rate and the operating interest estimate."""

import pytest

from hogproj.crush import CrushInputs, cost_usd, operating_interest
from hogproj.data import fred


def test_parse_skips_missing_days_and_old_years():
    text = "observation_date,DPRIME\n2014-12-31,3.25\n2026-10-12,.\n2026-10-13,7.00\n"
    df = fred.parse(text)
    assert list(df["prime_pct"]) == [7.0]


def test_offline_load_has_a_rate():
    df, source, _ = fred.load(offline=True)
    assert source in ("cache", "sample") and df["prime_pct"].between(2, 15).all()


def test_operating_interest_finances_pig_and_half_the_rest():
    c = CrushInputs(pig_usd_per_head=40, days_on_feed=146)
    rest = cost_usd(c) - 40 - c.interest_usd
    assert operating_interest(c, 0.08) == pytest.approx((40 + rest / 2) * 0.08 * 0.4)
    assert operating_interest(c, 0.0) == 0
