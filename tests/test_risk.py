from datetime import date

import numpy as np
import pandas as pd
import pytest

from hogproj.data import ams
from hogproj.markets import lean_hog_index, seasonal_factors
from hogproj.outlook import Plan, project, summary, synced
from hogproj.risk import (
    HogDynamics,
    RiskInputs,
    distribution_summary,
    estimate_hog_dynamics,
    simulate_profit,
)

START = date(2026, 10, 19)
NO_SEASON = pd.DataFrame(columns=["month", "factor", "years"])


def inputs(weeks: int = 52):
    plan = synced(Plan(seasonal=False))
    r = project(plan, NO_SEASON, START).iloc[:weeks]
    return (
        plan,
        r,
        r["marketed_head"].to_numpy(),
        r["sold_lb_carcass"].to_numpy() / 100,
        r["hog_usd_per_cwt_carcass"].to_numpy(),
    )


def test_zero_volatility_matches_the_plain_projection():
    plan, r, head, cwt, price = inputs()
    out = simulate_profit(
        head, cwt, price, plan.cost, HogDynamics(sigma=0), RiskInputs(corn_vol_annual=0)
    )
    assert out["profit"] == pytest.approx(summary(r)["profit_usd"])


def test_seeded_and_reproducible():
    plan, _, head, cwt, price = inputs()
    a = simulate_profit(head, cwt, price, plan.cost, HogDynamics(), RiskInputs(seed=1))
    b = simulate_profit(head, cwt, price, plan.cost, HogDynamics(), RiskInputs(seed=1))
    c = simulate_profit(head, cwt, price, plan.cost, HogDynamics(), RiskInputs(seed=2))
    assert np.array_equal(a["profit"], b["profit"])
    assert not np.array_equal(a["profit"], c["profit"])


def test_floor_cuts_the_downside_and_costs_premium_in_good_years():
    plan, _, head, cwt, price = inputs()
    risk = RiskInputs(floor_usd_per_cwt_carcass=float(price[0]), premium_usd_per_cwt_carcass=2)
    out = simulate_profit(head, cwt, price, plan.cost, HogDynamics(), risk)
    plain, floored = (
        distribution_summary(out["profit"]),
        distribution_summary(out["profit_with_floor"]),
    )
    assert floored["p10"] > plain["p10"]
    # never worse than paying the premium on every cwt
    assert (out["profit_with_floor"] - out["profit"] >= -2 * cwt.sum() - 1e-6).all()


def test_estimated_dynamics_are_sensible(tmp_path, monkeypatch):
    monkeypatch.setattr(ams, "CACHE_DIR", tmp_path)
    df, _, _ = ams.load_hg201(offline=True)
    idx = lean_hog_index(df)
    dyn = estimate_hog_dynamics(idx, seasonal_factors(idx))
    assert dyn.weeks_used > 100
    assert 0.5 < dyn.phi < 1  # hog price surprises persist for weeks, then fade
    assert 0.01 < dyn.sigma < 0.10  # a few percent per week


def test_distribution_summary():
    s = distribution_summary(np.array([-2.0, -1, 1, 2, 3]))
    assert s["p_profit"] == pytest.approx(0.6)
    assert s["p50"] == pytest.approx(1)
