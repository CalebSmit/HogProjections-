"""The app reproduces the owner's "Wean Pig Crush" workbook layout (Sheet5, one column).

The workbook's formulas are recomputed here by hand. All numbers are synthetic; real company
figures never go in the repo. See docs/research/crush-workbook-review.md.
"""

from datetime import date

import pytest

from hogproj.basis import basis_period
from hogproj.inputs import (
    BarnCostMode,
    FeedPhase,
    InterestMode,
    LaborCostMode,
    Location,
    MarketingCut,
    MortalityMode,
    Projection,
    WeanPigPriceSource,
)
from hogproj.model import project

# synthetic "settings" and ration (lb per pig), in the workbook's structure
USDA_WP, ADDER = 40.00, 5.00
CORN_FUT, CORN_BASIS, CORN_CARRY, CORN_HEDGE_PCT, CORN_HEDGED = 4.50, -0.10, 0.20, 25, 4.40
SBM_FUT, SBM_BASIS, SBM_HEDGE_PCT, SBM_HEDGED = 330.0, 10.0, 50, 320.0
DDG = 160.0
CORN_LB, DDG_LB, SBM_LB, OTHER_LB, OTHER_USD_LB = 480.0, 100.0, 90.0, 30.0, 0.60
HEALTH, BARN_LABOR, MORT, GA, FREIGHT, INTEREST, OTHER = 5.0, 26.0, 6.5, 2.0, 7.0, 3.0, 1.0
PRINCIPAL, TERM_INT = 3.0, 1.5
TARGET_WT, YIELD = 290.0, 0.75
LH_FUT, LH_BASIS, HOG_HEDGE_PCT, HOG_HEDGED = 80.0, -3.0, 40, 84.0
PLACED = date(2026, 9, 14)


def workbook_column() -> dict[str, float]:
    """The workbook's per-pig math, written the way its formulas are."""
    corn = ((CORN_FUT + CORN_BASIS + CORN_CARRY) * (1 - CORN_HEDGE_PCT / 100)) + (
        CORN_HEDGED * CORN_HEDGE_PCT / 100
    )
    sbm = ((SBM_FUT + SBM_BASIS) * (1 - SBM_HEDGE_PCT / 100)) + SBM_HEDGED * SBM_HEDGE_PCT / 100
    feed = corn / 56 * CORN_LB + sbm / 2000 * SBM_LB + DDG_LB * DDG / 2000 + OTHER_LB * OTHER_USD_LB
    hog_fut = LH_FUT * (1 - HOG_HEDGE_PCT / 100) + HOG_HEDGED * HOG_HEDGE_PCT / 100
    revenue = (hog_fut + LH_BASIS) * (TARGET_WT * YIELD / 100)
    cost = (USDA_WP + ADDER) + feed + HEALTH + BARN_LABOR + MORT + GA + FREIGHT + INTEREST + OTHER
    margin = revenue - cost
    return {
        "revenue": revenue,
        "feed": feed,
        "cost": cost,
        "margin": margin,
        "after_debt": margin - PRINCIPAL - TERM_INT,
    }


def app_projection() -> Projection:
    total = CORN_LB + DDG_LB + SBM_LB + OTHER_LB
    return Projection(
        head_placed=2400,
        placement_date=PLACED,
        mortality_mode=MortalityMode.USD_PER_PIG,
        mortality_cost_usd_hd=MORT,
        dead_feed_share=0,
        carcass_yield_pct=YIELD * 100,
        wean_pig_source=WeanPigPriceSource.USDA_CASH,
        wean_pig_usda_cash_usd_hd=USDA_WP,
        wean_pig_adder_usd_hd=ADDER,
        location=Location(
            name="Synthetic",
            corn_basis_usd_bu=CORN_BASIS,
            sbm_basis_usd_ton=SBM_BASIS,
            ddgs_usd_ton=DDG,
            barn_rent_usd_space_yr=0,
            labor_wage_usd_hr=0,
        ),
        corn_futures_usd_bu=CORN_FUT,
        corn_carry_usd_bu=CORN_CARRY,
        corn_hedged_pct=CORN_HEDGE_PCT,
        corn_hedged_usd_bu=CORN_HEDGED,
        sbm_futures_usd_ton=SBM_FUT,
        sbm_hedged_pct=SBM_HEDGE_PCT,
        sbm_hedged_usd_ton=SBM_HEDGED,
        feed_phases=[
            FeedPhase(
                name="Whole-group ration",
                feed_lb_per_pig=total,
                corn_pct=CORN_LB / total * 100,
                sbm_pct=SBM_LB / total * 100,
                ddgs_pct=DDG_LB / total * 100,
                other_usd_ton=OTHER_USD_LB * 2000,
            )
        ],
        barn_mode=BarnCostMode.PER_PIG_PLACED,
        barn_usd_pig_placed=BARN_LABOR,
        labor_mode=LaborCostMode.PER_PIG_PLACED,
        labor_usd_pig_placed=0,
        vet_med_usd_hd=HEALTH,
        trucking_usd_hd_sold=FREIGHT,
        ga_usd_hd=GA,
        other_usd_hd_sold=OTHER,
        interest_mode=InterestMode.USD_PER_PIG,
        interest_usd_hd=INTEREST,
        principal_usd_hd=PRINCIPAL,
        term_interest_usd_hd=TERM_INT,
        marketing=[
            MarketingCut(days_after_placement=160, pct_of_marketed=100, live_weight_lb=TARGET_WT)
        ],
        lean_hog_futures_cwt={"2027-04": LH_FUT},
        hog_basis_cwt_by_period={basis_period(date(2027, 2, 21)): LH_BASIS},
        hog_hedged_pct=HOG_HEDGE_PCT,
        hog_hedged_cwt=HOG_HEDGED,
        checkoff_pct=0,
    )


def test_app_matches_workbook_column():
    wb = workbook_column()
    s = project(app_projection()).summary
    assert s["revenue_usd_per_head_sold"] == pytest.approx(wb["revenue"])
    assert s["feed_cost_usd_per_head_sold"] == pytest.approx(wb["feed"])
    assert s["cost_usd_per_head_sold"] == pytest.approx(wb["cost"])
    assert s["net_usd_per_head_sold"] == pytest.approx(wb["margin"])
    assert s["net_after_debt_usd_per_head_sold"] == pytest.approx(wb["after_debt"])


def test_manual_wean_price_ignores_adder():
    p = app_projection().model_copy(
        update={"wean_pig_source": WeanPigPriceSource.MANUAL, "wean_pig_manual_usd_hd": 50.0}
    )
    assert p.wean_pig_usd_hd == 50.0
    assert app_projection().wean_pig_usd_hd == USDA_WP + ADDER


def test_percent_mortality_mode_has_no_dollar_line():
    p = app_projection().model_copy(
        update={"mortality_mode": MortalityMode.PCT_OF_HEAD, "mortality_pct": 5.0}
    )
    r = project(p)
    costs = r.costs.set_index("line")["total_usd"]
    assert costs["Mortality ($/pig)"] == 0
    assert r.summary["head_sold"] == pytest.approx(2400 * 0.95)
