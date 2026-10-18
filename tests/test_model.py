from datetime import date
from typing import Any

import pandas as pd
import pytest

from hogproj.basis import (
    average_basis_by_period,
    basis_by_year_period,
    basis_period,
    daily_basis,
    lean_hog_contract_for,
    period_label,
)
from hogproj.inputs import FeedPhase, Location, MarketingCut, Projection
from hogproj.model import project


def make(**overrides) -> Projection:
    base: dict[str, Any] = dict(
        head_placed=1000,
        placement_date=date(2026, 1, 1),
        mortality_pct=10.0,
        dead_feed_share=0.0,
        carcass_yield_pct=75.0,
        wean_pig_usda_cash_usd_hd=40.0,
        location=Location(
            name="Test",
            corn_basis_usd_bu=-0.50,
            sbm_basis_usd_ton=20.0,
            ddgs_usd_ton=150.0,
            barn_rent_usd_space_yr=36.5,
            labor_wage_usd_hr=20.0,
        ),
        corn_futures_usd_bu=4.50,
        sbm_futures_usd_ton=280.0,
        feed_phases=[
            FeedPhase(
                name="All",
                feed_lb_per_pig=560,
                corn_pct=50,
                sbm_pct=20,
                ddgs_pct=20,
                other_usd_ton=500,
            )
        ],
        barn_downtime_days=50,  # 150-day closeout + 50 = 200 barn days
        labor_hr_per_pig=0.1,
        marketing=[MarketingCut(days_after_placement=150, pct_of_marketed=100, live_weight_lb=300)],
        lean_hog_futures_cwt={"2026-06": 100.0},
        hog_basis_cwt_by_period={10: -2.0},
        checkoff_pct=0.0,
    )
    base.update(overrides)
    return Projection(**base)


def test_contract_mapping():
    # ISU B2-41 convention: days 1-14 of a contract month use it, the 15th on uses the next
    assert lean_hog_contract_for(date(2027, 1, 15)) == "2027-02"
    assert lean_hog_contract_for(date(2027, 2, 14)) == "2027-02"
    assert lean_hog_contract_for(date(2027, 2, 15)) == "2027-04"
    assert lean_hog_contract_for(date(2027, 3, 1)) == "2027-04"
    assert lean_hog_contract_for(date(2027, 5, 30)) == "2027-06"
    assert lean_hog_contract_for(date(2027, 8, 20)) == "2027-10"
    assert lean_hog_contract_for(date(2027, 9, 9)) == "2027-10"
    assert lean_hog_contract_for(date(2027, 11, 2)) == "2027-12"
    assert lean_hog_contract_for(date(2027, 12, 20)) == "2028-02"


def test_basis_periods():
    assert basis_period(date(2027, 1, 1)) == 1
    assert basis_period(date(2027, 1, 15)) == 2
    assert basis_period(date(2027, 12, 31)) == 24
    assert period_label(3) == "Feb 1-14"
    assert period_label(24) == "Dec 15-end"


def test_hand_calculated_group():
    # 900 sold; sale 2026-05-31 -> Jun contract 100 + "May 15-end" basis -2 = 98/cwt carcass
    r = project(make())
    s = r.summary
    assert s["head_sold"] == pytest.approx(900)
    assert r.marketing.loc[0, "contract"] == "2026-06"
    revenue = 900 * 225 / 100 * 98
    assert s["gross_revenue_usd"] == pytest.approx(revenue)

    # feed: 900 pigs x 560 lb = 252 tons
    tons = 252.0
    corn = tons * 2000 * 0.5 / 56 * 4.00
    sbm = tons * 0.2 * 300
    ddgs = tons * 0.2 * 150
    other = tons * 0.1 * 500
    feed = corn + sbm + ddgs + other
    costs = r.costs.set_index("line")["total_usd"]
    assert costs["Feed"] == pytest.approx(feed)
    assert costs["Weaned pigs"] == pytest.approx(40_000)
    assert costs["Barn / facilities"] == pytest.approx(1000 * 36.5 * 200 / 365)
    assert costs["Labor"] == pytest.approx(1000 * 0.1 * 20)
    assert s["net_usd"] == pytest.approx(revenue - costs.sum())
    # breakeven reproduces zero net
    assert s["breakeven_cwt_carcass"] * 900 * 2.25 == pytest.approx(costs.sum())


def test_checkoff_in_breakeven():
    r = project(make(checkoff_pct=0.35))
    s = r.summary
    be = s["breakeven_cwt_carcass"]
    rev_at_be = be * s["carcass_cwt_sold"]
    other_costs = s["total_cost_usd"] - s["gross_revenue_usd"] * 0.0035
    assert rev_at_be * (1 - 0.0035) == pytest.approx(other_costs)


def test_marketing_must_sum_to_100():
    with pytest.raises(ValueError):
        make(
            marketing=[
                MarketingCut(days_after_placement=150, pct_of_marketed=90, live_weight_lb=280)
            ]
        )


def test_missing_futures_contract_is_explicit():
    with pytest.raises(KeyError):
        project(make(lean_hog_futures_cwt={"2026-07": 100.0}))


def test_basis_average_across_years():
    dates = pd.to_datetime(["2024-06-03", "2024-06-04", "2025-06-02", "2025-07-01"])
    index = pd.Series([100.0, 102.0, 90.0, 95.0], index=dates)
    fut = pd.Series([104.0, 104.0, 91.0, 95.0], index=dates)
    table = basis_by_year_period(daily_basis(index, fut))
    jun_early = 11
    assert table.loc[2024, jun_early] == pytest.approx(-3.0)
    assert table.loc[2025, jun_early] == pytest.approx(-1.0)
    avg = average_basis_by_period(table)
    assert avg[jun_early] == pytest.approx(-2.0)
    assert avg[13] == pytest.approx(0.0)  # Jul 1-14
    assert avg[1] == 0.0  # no data
    assert average_basis_by_period(table, years=[2025])[jun_early] == pytest.approx(-1.0)


def test_roll_gap_days_dropped_from_basis():
    from hogproj.basis import in_roll_gap, lean_hog_expiry

    assert lean_hog_expiry(2026, 12) == date(2026, 12, 14)  # Dec26 expires Mon Dec 14
    assert lean_hog_expiry(2026, 8) == date(2026, 8, 14)
    assert lean_hog_expiry(2027, 2) == date(2027, 2, 12)
    assert not in_roll_gap(date(2027, 2, 12))
    assert in_roll_gap(date(2027, 2, 13))  # after expiry, still priced off Feb
    assert not in_roll_gap(date(2027, 2, 15))  # priced off Apr, front month is Apr
    assert not in_roll_gap(date(2027, 3, 13))  # not a contract month

    dates = pd.to_datetime(["2027-02-12", "2027-02-13", "2027-02-16"])
    s = daily_basis(pd.Series([90.0, 90.0, 90.0], dates), pd.Series([89.0, 99.0, 95.0], dates))
    assert [str(d)[5:10] for d in s.index] == ["02-12", "02-16"]
