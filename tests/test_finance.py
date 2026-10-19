import numpy as np
import pytest

from hogproj.finance import (
    CostInputs,
    breakeven,
    cost_table,
    cost_usd_per_cwt_carcass,
    margin_usd_per_head,
    sensitivity,
    weekly_returns,
)
from hogproj.herd import HerdInputs, simulate


def test_reproduces_cih_margin_formula():
    # domain.md §2: margin $/cwt carcass = LeanHog - 5.3*Corn - 0.73*SBM/20 - 44
    c = CostInputs(corn_usd_per_bu=4.10, sbm_usd_per_ton=320, lean_hog_usd_per_cwt_carcass=92)
    expected_cwt = 92 - 5.3 * 4.10 - 0.73 * 320 / 20 - 44
    assert expected_cwt == pytest.approx(14.59)
    assert margin_usd_per_head(c) == pytest.approx(expected_cwt * c.weight_lb_carcass / 100)


def test_breakeven_live_vs_carcass():
    c = CostInputs(corn_usd_per_bu=4.50, sbm_usd_per_ton=300)
    be = breakeven(c)
    # ISU budget prices: 5.3*4.50 + 0.73*300/20 + 44 = 78.80 carcass
    assert be["price_cwt_carcass"] == pytest.approx(78.80)
    assert be["price_cwt_live"] == pytest.approx(78.80 * 0.75)
    assert be["cost_usd_per_head"] == pytest.approx(78.80 * 283 * 0.75 / 100)
    at_be = c.model_copy(update={"lean_hog_usd_per_cwt_carcass": be["price_cwt_carcass"]})
    assert margin_usd_per_head(at_be) == pytest.approx(0)


def test_cost_table_sums():
    t = cost_table(CostInputs())
    assert t.loc[["Corn", "Soybean meal", "Other (non-feed)"]].sum()["usd_per_cwt_carcass"] == (
        pytest.approx(t.loc["Total", "usd_per_cwt_carcass"])
    )
    assert t.loc["Total", "share"] == pytest.approx(1)


def test_sensitivity_monotonic():
    c = CostInputs(corn_usd_per_bu=4.5)
    grid = sensitivity(c, np.array([70.0, 80, 90]), np.array([3.5, 4.5, 5.5]))
    assert grid.shape == (3, 3)
    assert (grid.diff(axis=1).iloc[:, 1:] > 0).all().all()  # higher hog price -> more margin
    assert (grid.diff(axis=0).iloc[1:] < 0).all().all()  # higher corn -> less margin
    assert grid.loc[4.5, 80.0] == pytest.approx(
        margin_usd_per_head(c.model_copy(update={"lean_hog_usd_per_cwt_carcass": 80}))
    )


def test_weekly_returns_tie_to_per_head_margin():
    c = CostInputs(lean_hog_usd_per_cwt_carcass=90)
    herd = simulate(HerdInputs(weeks=52))
    r = weekly_returns(herd, c)
    per_head = r["margin_usd"] / r["marketed_head"]
    assert per_head.to_numpy() == pytest.approx(margin_usd_per_head(c))
    assert r["cumulative_margin_usd"].iloc[-1] == pytest.approx(r["margin_usd"].sum())
    assert r["cost_usd"].iloc[0] == pytest.approx(
        r["sold_lb_carcass"].iloc[0] / 100 * cost_usd_per_cwt_carcass(c)["total"]
    )
