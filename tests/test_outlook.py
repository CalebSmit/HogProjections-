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
