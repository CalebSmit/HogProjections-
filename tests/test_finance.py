import numpy as np
import pandas as pd
import pytest

from hogproj.config import ROOT
from hogproj.finance import (
    ISU_WEIGHT_LB_LIVE,
    CostInputs,
    breakeven,
    cost_table,
    cost_usd_per_head,
    margin_usd_per_head,
    sensitivity,
    weekly_returns,
)
from hogproj.herd import HerdInputs, simulate

ISU = pd.read_csv(ROOT / "tests" / "fixtures" / "isu_f2f_2026.csv", comment="#")


def isu_inputs(m: pd.Series) -> CostInputs:
    """CostInputs that carry one ISU month's $/head lines (prices of 1 make qty = $/head)."""
    return CostInputs(
        corn_usd_per_bu=1.0,
        corn_bu_per_head=m["corn"],
        sbm_usd_per_ton=2000.0,
        sbm_lb_per_head=m["sbm"],
        other_feed_usd_per_head=m["ddgs"] + m["complete_other"] + m["processing"],
        nonfeed_usd_per_head=m["nonfeed_total"],
        death_loss_usd_per_head=m["death_loss"],
        manure_credit_usd_per_head=m["manure_credit"],
        weight_lb_live_market=ISU_WEIGHT_LB_LIVE,
        lean_hog_usd_per_cwt_carcass=m["price_carcass"],
    )


@pytest.mark.parametrize("month", ISU["sale_month"].tolist())
def test_reproduces_isu_elr_month(month):
    # PLAN Phase 3: reconcile with ISU ELR within ±$2/head. ISU rounds each line to the cent,
    # so totals agree within a few cents and breakevens within ~$0.03/cwt.
    m = ISU.set_index("sale_month").loc[month]
    c = isu_inputs(m)
    lines = cost_usd_per_head(c)
    be = breakeven(c)
    assert lines["total"] == pytest.approx(m["total_cost"], abs=0.05)
    assert be["price_cwt_live"] == pytest.approx(m["breakeven_live"], abs=0.03)
    assert be["price_cwt_carcass"] == pytest.approx(m["breakeven_carcass"], abs=0.03)
    assert margin_usd_per_head(c) == pytest.approx(m["total_profit"], abs=0.10)


def test_defaults_are_isu_sep_2026_at_270_lb():
    m = ISU.set_index("sale_month").loc["2026-09"]
    c = CostInputs(corn_usd_per_bu=4.0, sbm_usd_per_ton=300, weight_lb_live_market=270)
    lines = cost_usd_per_head(c)
    # quantities were sized at ~$4.00 corn / $300 SBM, so feed lands close to ISU's
    assert lines["corn"] == pytest.approx(m["corn"], abs=0.5)
    assert lines["sbm"] == pytest.approx(m["sbm"], abs=0.2)
    assert lines["total"] == pytest.approx(m["total_cost"], abs=1.0)


def test_feed_scales_with_market_weight_and_nonfeed_does_not():
    light = cost_usd_per_head(CostInputs(weight_lb_live_market=270))
    heavy = cost_usd_per_head(CostInputs(weight_lb_live_market=297))
    for k in ["corn", "sbm", "other_feed"]:
        assert heavy[k] == pytest.approx(light[k] * 1.1)
    assert heavy["nonfeed"] == light["nonfeed"]
    assert heavy["death_loss"] == light["death_loss"]


def test_breakeven_live_vs_carcass_and_zero_margin():
    c = CostInputs()
    be = breakeven(c)
    assert be["price_cwt_live"] == pytest.approx(be["price_cwt_carcass"] * 0.75)
    assert be["price_cwt_carcass"] == pytest.approx(be["cost_usd_per_head"] / (283 * 0.75 / 100))
    at_be = c.model_copy(update={"lean_hog_usd_per_cwt_carcass": be["price_cwt_carcass"]})
    # at breakeven only the manure credit is left over (ISU convention)
    assert margin_usd_per_head(at_be) == pytest.approx(c.manure_credit_usd_per_head)


def test_cost_table_sums():
    t = cost_table(CostInputs())
    parts = t.iloc[:5]["usd_per_head"].sum()
    assert parts == pytest.approx(t.loc["Total cost", "usd_per_head"])
    assert t.loc["Net cost", "usd_per_head"] == pytest.approx(
        t.loc["Total cost", "usd_per_head"] + t.loc["Less manure credit", "usd_per_head"]
    )
    assert t.loc["Total cost", "share"] == pytest.approx(1)


def test_sensitivity_monotonic():
    c = CostInputs(corn_usd_per_bu=4.5)
    grid = sensitivity(c, np.array([70.0, 80, 90]), np.array([3.5, 4.5, 5.5]))
    assert grid.shape == (3, 3)
    assert (grid.diff(axis=1).iloc[:, 1:] > 0).all().all()  # higher hog price -> more margin
    assert (grid.diff(axis=0).iloc[1:] < 0).all().all()  # higher corn -> less margin
    assert grid.loc[4.5, 80.0] == pytest.approx(
        margin_usd_per_head(c.model_copy(update={"lean_hog_usd_per_cwt_carcass": 80}))
    )
    # $1/bu corn moves margin by corn bu/head x weight scale
    step = grid.loc[3.5, 80.0] - grid.loc[4.5, 80.0]
    assert step == pytest.approx(c.corn_bu_per_head * c.feed_scale)


def test_weekly_returns_tie_to_per_head_margin():
    c = CostInputs(lean_hog_usd_per_cwt_carcass=90)
    herd = simulate(HerdInputs(weeks=52))
    r = weekly_returns(herd, c)
    per_head = r["margin_usd"] / r["marketed_head"]
    assert per_head.to_numpy() == pytest.approx(margin_usd_per_head(c))
    assert r["cumulative_margin_usd"].iloc[-1] == pytest.approx(r["margin_usd"].sum())
