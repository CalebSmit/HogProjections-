"""Wean-to-finish margin. Reference: a Pipestone-style wean pig crush workbook (Sep 2026)."""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from hogproj.crush import (
    MONTHS,
    CrushInputs,
    annual_summary,
    breakeven_hog,
    breakeven_pig,
    by_month,
    contract_expiry,
    contract_for,
    contract_label,
    contracts_needed,
    cost_table,
    margin_rank,
    margin_usd,
    month_average,
    placements,
)
from hogproj.data.feeder import merge, parse_report
from hogproj.data.nass import parse_corn

FIXTURES = Path(__file__).parent / "fixtures"

# Workbook column for pigs placed Sep 14, 2026: USDA $28.71 + $7 adder, sold into April hogs at
# $80.60 futures with a -$5.505 basis; margin -$12.39 before and -$16.79 after debt payments.
WORKBOOK = CrushInputs(
    pig_usd_per_head=28.71, adder_usd_per_head=7, basis_usd_per_cwt=-5.505,
    corn_usd_per_bu=4.88, sbm_usd_per_ton=350.2, ddgs_usd_per_ton=180.8,
    corn_lb=487, sbm_lb=85, ddgs_lb=92, other_feed_lb=32.26, other_feed_usd_per_lb=0.675,
    health_usd=5.17, facilities_labor_usd=27.52, mortality_usd=6, overhead_usd=2.45,
    freight_usd=7.18, interest_usd=3.37, other_usd=0.91, principal_usd=3.1, term_interest_usd=1.3,
)  # fmt: skip


def test_margin_matches_workbook_to_the_cent():
    assert margin_usd(WORKBOOK, 80.6) == pytest.approx(-16.79, abs=0.005)
    no_debt = WORKBOOK.model_copy(update={"principal_usd": 0, "term_interest_usd": 0})
    assert margin_usd(no_debt, 80.6) == pytest.approx(-12.39, abs=0.005)


def test_breakevens_are_consistent():
    c = WORKBOOK
    hog = breakeven_hog(c)
    assert margin_usd(c, hog) == pytest.approx(0, abs=1e-9)
    most = breakeven_pig(c, 80.6)
    assert margin_usd(c, 80.6, pig=most) == pytest.approx(0, abs=1e-9)
    assert most < c.pig_usd_per_head  # losing money, so the pig is worth less than paid


def test_cost_table_totals():
    t = cost_table(WORKBOOK)
    lines = t.drop(index="Total cost")
    usd = t["usd_per_head"].to_dict()
    assert lines["usd_per_head"].to_numpy().sum() == pytest.approx(usd["Total cost"])
    assert lines["share"].to_numpy().sum() == pytest.approx(1)
    assert usd["Weaned pig"] == pytest.approx(35.71)


@pytest.mark.parametrize(
    ("sold", "contract"),
    [
        (date(2026, 12, 6), (2026, 12)),
        (date(2026, 12, 14), (2026, 12)),  # expiry day itself
        (date(2026, 12, 20), (2027, 2)),
        (date(2027, 2, 21), (2027, 4)),
        (date(2027, 3, 1), (2027, 4)),
        (date(2027, 9, 1), (2027, 10)),
    ],
)
def test_contract_for_sale_date(sold, contract):
    assert contract_for(sold) == contract


def test_contract_expiry_is_tenth_business_day():
    assert contract_expiry(2026, 12) == date(2026, 12, 14)
    assert contract_expiry(2027, 2) == date(2027, 2, 12)
    assert contract_label((2027, 4)) == "Apr 2027"


def _index(start: str, end: str, price: float) -> pd.DataFrame:
    days = pd.bdate_range(start, end)
    return pd.DataFrame({"index_date": days, "lean_hog_index_usd_per_cwt_carcass": price})


def test_placements_split_sold_and_on_feed():
    pigs = pd.DataFrame(
        {"week_ending": pd.to_datetime(["2026-01-09", "2026-09-18"]),
         "cash_usd_per_head": [60.0, 28.71]}
    )  # fmt: skip
    idx = _index("2025-10-01", "2026-10-16", 90.0)
    c = WORKBOOK
    rows = placements(pigs, idx, c, {(2027, 4): 80.6})
    assert list(rows["status"]) == ["sold", "on feed"]
    sold = rows.iloc[0]
    assert sold["hog_usd_per_cwt"] == pytest.approx(90.0)
    assert sold["pig_usd"] == pytest.approx(67.0)
    on_feed = rows.iloc[1]
    assert on_feed["priced_on"] == "Apr 2027"  # placed Sep 14 + 160 days = Feb 21, after Feb expiry
    assert on_feed["margin_usd"] == pytest.approx(margin_usd(c, 80.6))


def test_placements_drop_rows_without_a_contract_price():
    pigs = pd.DataFrame(
        {"week_ending": pd.to_datetime(["2026-09-18"]), "cash_usd_per_head": [30.0]}
    )
    rows = placements(pigs, _index("2026-01-01", "2026-10-16", 90.0), WORKBOOK, {})
    assert rows.empty


def test_contracts_needed_covers_on_feed_and_today():
    pigs = pd.DataFrame({"week_ending": pd.to_datetime(["2026-06-05", "2026-09-18"])})
    got = contracts_needed(pigs, WORKBOOK, date(2026, 10, 19), date(2026, 10, 16))
    assert got == [(2026, 12), (2027, 4)]  # Nov 8 -> Dec; Feb 21 and Mar 28 -> Apr


def test_parse_feeder_report():
    rows = parse_report((FIXTURES / "ams_2810_2026-10-16.txt").read_text(encoding="utf-8"))
    this, last = rows.iloc[0], rows.iloc[1]
    assert this["week_ending"] == pd.Timestamp("2026-10-16")
    assert this["cash_usd_per_head"] == pytest.approx(20.08)
    assert (this["low_usd_per_head"], this["high_usd_per_head"]) == (10.0, 33.0)
    assert last["week_ending"] == pd.Timestamp("2026-10-09")
    assert last["cash_usd_per_head"] == pytest.approx(19.59)


def test_parse_feeder_report_rejects_other_text():
    with pytest.raises(ValueError):
        parse_report("National Daily Hog Report")


def test_merge_keeps_full_row_over_last_reported():
    full = pd.DataFrame({"week_ending": pd.to_datetime(["2026-10-09"]),
                         "cash_usd_per_head": [19.59],
                         "low_usd_per_head": [12.0], "high_usd_per_head": [30.0]})  # fmt: skip
    rows = parse_report((FIXTURES / "ams_2810_2026-10-16.txt").read_text(encoding="utf-8"))
    out = merge(full, rows)
    assert len(out) == 2
    assert out.iloc[0]["low_usd_per_head"] == 12.0


def test_parse_corn():
    df = parse_corn({"data": [
        {"year": "2026", "reference_period_desc": "AUG", "Value": "4.44"},
        {"year": "2026", "reference_period_desc": "MARKETING YEAR", "Value": "4.30"},
        {"year": "2026", "reference_period_desc": "JUL", "Value": "(NA)"},
    ]})  # fmt: skip
    assert list(df["month"]) == [pd.Timestamp("2026-08-01")]
    assert df["usd_per_bu"].iloc[0] == 4.44


# --- History ------------------------------------------------------------------------------------
def _history() -> pd.DataFrame:
    """Two years of weekly placements with a fixed pig price, sold into a known index."""
    weeks = pd.date_range("2024-01-05", "2025-06-27", freq="W-FRI")
    pigs = pd.DataFrame({"week_ending": weeks, "cash_usd_per_head": 40.0})
    days = pd.bdate_range("2024-01-01", "2026-01-30")
    price = 80 + 10 * np.sin(2 * np.pi * np.array([d.dayofyear for d in days]) / 365)
    idx = pd.DataFrame({"index_date": days, "lean_hog_index_usd_per_cwt_carcass": price})
    return placements(pigs, idx, CrushInputs(), {})


def test_worth_minus_paid_is_margin():
    rows = _history()
    assert len(rows) > 50
    diff = rows["worth_usd"] - rows["pig_usd"] - rows["margin_usd"]
    assert np.abs(diff.to_numpy()).max() < 1e-9


def test_margin_rank():
    hist = [-10.0, 0.0, 0.0, 10.0]
    assert margin_rank(-20, hist) == 0
    assert margin_rank(20, hist) == 100
    assert margin_rank(0, hist) == pytest.approx(50)  # one below, two ties counted half
    assert margin_rank(5, hist) == pytest.approx(75)
    assert np.isnan(margin_rank(1, []))


def test_by_month_matches_manual_pivot():
    rows = _history()
    grid = by_month(rows)
    assert list(grid.columns) == MONTHS
    sold = pd.DataFrame(rows[rows["status"] == "sold"])
    placed = pd.Series(pd.to_datetime(sold["placed"]))
    mar_2024 = sold[(placed.dt.year == 2024) & (placed.dt.month == 3)]
    assert grid.loc[2024, "Mar"] == pytest.approx(mar_2024["margin_usd"].mean())
    avg = month_average(rows)
    assert avg["Mar"] == pytest.approx(sold[placed.dt.month == 3]["margin_usd"].mean())


def test_annual_summary():
    rows = _history()
    s = annual_summary(rows).set_index("year")
    sold = rows[(rows["status"] == "sold") & (rows["placed"].dt.year == 2024)]
    assert s.loc[2024, "weeks"] == len(sold)
    assert s.loc[2024, "profitable"] == pytest.approx((sold["margin_usd"] > 0).mean())
    assert s.loc[2024, "worst_usd"] == pytest.approx(sold["margin_usd"].min())


# --- Corn off the futures curve ---------------------------------------------------------------
CURVE = {(2026, 12): 4.67, (2027, 3): 4.805, (2027, 5): 4.885, (2027, 7): 4.95}


@pytest.mark.parametrize(
    ("year", "month", "contract"),
    [(2026, 10, (2026, 12)), (2026, 12, (2026, 12)), (2027, 1, (2027, 3)),
     (2027, 4, (2027, 5)), (2027, 12, (2027, 12))],
)  # fmt: skip
def test_corn_contract_for_month(year, month, contract):
    from hogproj.crush import corn_contract_for

    assert corn_contract_for(year, month) == contract


def test_forward_corn_averages_months_on_feed_plus_basis():
    from hogproj.crush import forward_corn

    # Oct 2026 -> Mar 2027: Oct, Nov, Dec on Dec; Jan, Feb, Mar on Mar.
    got = forward_corn(pd.Timestamp("2026-10-19"), pd.Timestamp("2027-03-28"), CURVE, -0.43)
    assert got == pytest.approx((3 * 4.67 + 3 * 4.805) / 6 - 0.43)
    # Past the last listed contract: the last one.
    far = forward_corn(pd.Timestamp("2027-09-01"), pd.Timestamp("2027-10-01"), CURVE, 0.0)
    assert far == pytest.approx(4.95)


def test_on_feed_rows_use_the_curve():
    pigs = pd.DataFrame(
        {"week_ending": pd.to_datetime(["2026-09-18"]), "cash_usd_per_head": [30.0]}
    )
    idx = _index("2026-01-01", "2026-10-16", 90.0)
    rows = placements(pigs, idx, WORKBOOK, {(2027, 4): 80.0}, corn_curve=CURVE, corn_basis=-0.4)
    from hogproj.crush import forward_corn

    expect = forward_corn(rows["placed"].iloc[0], rows["sold"].iloc[0], CURVE, -0.4)
    assert rows["corn_usd_per_bu"].iloc[0] == pytest.approx(expect)


# --- Review fixes -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("year", "month", "expiry"),
    [(2026, 7, date(2026, 7, 15)),  # Jul 3 observed Independence Day
     (2027, 7, date(2027, 7, 15)),  # Jul 5 observed
     (2027, 2, date(2027, 2, 12)),  # Presidents Day (Feb 15) falls after the 10th business day
     (2026, 4, date(2026, 4, 15))],  # Good Friday Apr 3, 2026
)  # fmt: skip
def test_contract_expiry_skips_exchange_holidays(year, month, expiry):
    assert contract_expiry(year, month) == expiry


def test_exchange_holidays_observed_rules():
    from hogproj.crush import exchange_holidays

    h = exchange_holidays(2027)
    assert date(2027, 12, 24) in h  # Christmas on Saturday -> Friday
    assert date(2027, 3, 26) in h  # Good Friday
    assert date(2027, 10, 11) not in h  # Columbus Day: markets open
