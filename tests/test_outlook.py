from datetime import date

import pandas as pd
import pytest

from hogproj.finance import CostInputs, margin_usd_per_head
from hogproj.herd import HerdInputs
from hogproj.outlook import Plan, drivers, headline, monthly, project, summary, synced

START = date(2026, 10, 19)
NO_SEASON = pd.DataFrame(columns=["month", "factor", "years"])


def flat_plan(**cost) -> Plan:
    return Plan(herd=HerdInputs(), cost=CostInputs(**cost), seasonal=False)


def test_flat_summary_ties_to_per_pig_margin():
    plan = flat_plan(lean_hog_usd_per_cwt_carcass=90)
    s = summary(project(plan, NO_SEASON, START))
    assert s["pigs_sold"] == pytest.approx(52 * 511.2, rel=1e-3)
    assert s["profit_usd_per_head"] == pytest.approx(margin_usd_per_head(synced(plan).cost))
    assert s["avg_price_cwt_carcass"] == pytest.approx(90)


def test_project_dates_start_today_weekly():
    r = project(flat_plan(), NO_SEASON, START)
    assert r["date"].iloc[0] == pd.Timestamp(START)
    assert (r["date"].diff().dropna() == pd.Timedelta(days=7)).all()


def test_monthly_rollup_sums_match():
    r = project(flat_plan(), NO_SEASON, START)
    m = monthly(r, months=120)
    assert m["profit_usd"].sum() == pytest.approx(r["margin_usd"].sum())
    assert m["month"].iloc[0] == pd.Timestamp("2026-10-01")


def test_drivers_directions_and_hog_price_size():
    plan = flat_plan()
    d = drivers(plan, NO_SEASON, START).set_index("driver")
    pigs = summary(project(plan, NO_SEASON, START))["pigs_sold"]
    cwt_per_pig = plan.cost.cwt_carcass
    assert d.loc["Hog price", "high_usd"] == pytest.approx(5 * cwt_per_pig * pigs)
    assert d.loc["Hog price", "low_usd"] == pytest.approx(-5 * cwt_per_pig * pigs)
    assert d.loc["Corn", "high_usd"] < 0 < d.loc["Corn", "low_usd"]
    assert d.loc["Non-feed cost", "high_usd"] == pytest.approx(-10 * pigs)
    assert d.loc["Pigs weaned / sow / yr", "high_usd"] != 0
    assert list(d["swing_usd"]) == sorted(d["swing_usd"], reverse=True)


def test_weaned_change_adds_one_pig_per_sow():
    plan = flat_plan()
    h = plan.herd
    from hogproj.outlook import _with_weaned_change

    more = _with_weaned_change(h, 1)
    weaned = lambda x: x.litters_per_sow_yr * x.born_alive_per_litter * (1 - x.prewean_mortality)  # noqa: E731
    assert weaned(more) - weaned(h) == pytest.approx(1)


def test_headline_gap():
    plan = flat_plan(lean_hog_usd_per_cwt_carcass=80)
    hl = headline(plan)
    assert hl["gap_cwt_carcass"] == pytest.approx(80 - hl["breakeven_cwt_carcass"])


def test_more_productive_sows_raise_profit():
    d = drivers(flat_plan(), NO_SEASON, START).set_index("driver")
    assert (
        d.loc["Pigs weaned / sow / yr", "high_usd"] > 0 > d.loc["Pigs weaned / sow / yr", "low_usd"]
    )


def test_default_herd_matches_cost_reference_productivity():
    from hogproj.herd import pigs_sold_per_sow_yr

    assert pigs_sold_per_sow_yr(HerdInputs()) == pytest.approx(
        CostInputs().ref_pigs_sold_per_sow_yr, abs=0.01
    )


def test_apply_zero_adjustment_is_identity():
    from hogproj.outlook import Adjustments, apply

    plan = flat_plan()
    assert apply(plan, Adjustments()) == plan


def test_compare_current_first_and_hog_price_delta():
    from hogproj.outlook import Adjustments, compare

    plan = flat_plan()
    table, cum = compare(
        plan, [Adjustments(name="Hogs +$10", hog_usd_per_cwt=10)], NO_SEASON, START, 52
    )
    assert list(table["scenario"]) == ["Current plan", "Hogs +$10"]
    pigs = table.loc[0, "pigs_sold"]
    assert table.loc[1, "profit_vs_current_usd"] == pytest.approx(10 * plan.cost.cwt_carcass * pigs)
    assert table.loc[0, "profit_vs_current_usd"] == 0
    assert len(cum) == 52
    assert cum["Hogs +$10"].iloc[-1] == pytest.approx(table.loc[1, "profit_usd"])


def test_expansion_shows_up_after_lags():
    from hogproj.outlook import Adjustments, compare

    table, cum = compare(
        flat_plan(), [Adjustments(name="Grow", sows_pct=20)], NO_SEASON, START, 104
    )
    # no extra pigs until bred sows farrow and grow out (~41 weeks)
    first_year = (cum["Grow"] - cum["Current plan"]).iloc[:40]
    assert first_year.abs().max() == pytest.approx(0, abs=1e-6)
    assert table.loc[1, "pigs_sold"] > table.loc[0, "pigs_sold"]


def test_monthly_per_pig_flat_price_is_level_and_partial_flagged():
    m = monthly(project(flat_plan(), NO_SEASON, START), months=12)
    # identical economics every week -> identical profit per pig every month
    assert m["profit_usd_per_head"].nunique() == 1 or (
        m["profit_usd_per_head"].max() - m["profit_usd_per_head"].min() < 1e-6
    )
    assert bool(m["partial"].iloc[0])  # starts Oct 19
    assert not m["partial"].iloc[1:].any()


def test_headline_profit_can_be_positive_just_below_breakeven():
    plan = flat_plan()
    be = headline(plan)["breakeven_cwt_carcass"]
    hl = headline(flat_plan(lean_hog_usd_per_cwt_carcass=be - 1.5))
    assert hl["gap_cwt_carcass"] < 0 < hl["profit_usd_per_head"]  # manure credit band
