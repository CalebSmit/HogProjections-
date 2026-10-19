from datetime import date

import pytest

from hogproj.crush import Week, crush_table, sale_for
from tests.test_crush_parity import (
    CORN_BASIS,
    CORN_FUT,
    DDG,
    LH_BASIS,
    LH_FUT,
    SBM_FUT,
    TARGET_WT,
    USDA_WP,
    app_projection,
    workbook_column,
)


def test_crush_column_matches_the_workbook_formulas():
    # report 2026-09-13 + 1 day = placed 2026-09-14; +160 days = 2027-02-21 -> Apr contract
    week = Week(date(2026, 9, 13), USDA_WP, CORN_FUT, SBM_FUT, DDG, LH_FUT, LH_BASIS)
    t = crush_table(
        app_projection(), [week], placement_lag_days=1, days_to_market=160, sale_weight_lb=TARGET_WT
    )
    col = t["2026-09-13"]
    wb = workbook_column(hedged=False)  # weekly placements don't carry the group's hedges
    assert col["CME contract"] == "2027-04"
    assert col["Revenue $/pig"] == pytest.approx(wb["revenue"])
    assert col["Feed $/pig"] == pytest.approx(wb["feed"])
    assert col["Cost of production $/pig"] == pytest.approx(wb["cost"])
    assert col["Margin $/pig"] == pytest.approx(wb["margin"])
    assert col["Margin after debt service $/pig"] == pytest.approx(wb["after_debt"])


def test_cost_lines_add_up_and_weeks_differ():
    weeks = [
        Week(date(2026, 9, 13), 40, CORN_FUT, SBM_FUT, DDG, LH_FUT, LH_BASIS),
        Week(date(2026, 9, 20), 30, CORN_FUT, SBM_FUT, DDG, LH_FUT, LH_BASIS),
    ]
    t = crush_table(app_projection(), weeks)
    lines = [
        i
        for i in t.index
        if i.endswith("$/pig")
        and i
        not in (
            "Revenue $/pig",
            "Cost of production $/pig",
            "Margin $/pig",
            "Margin after debt service $/pig",
        )
    ]
    for c in t.columns:
        assert sum(t.loc[lines, c]) == pytest.approx(t.loc["Cost of production $/pig", c])
    gap = t.loc["Margin $/pig", "2026-09-20"] - t.loc["Margin $/pig", "2026-09-13"]
    assert gap == pytest.approx(10.0)  # $10 cheaper pig, same everything else


def test_cash_corn_series_ignores_location_basis():
    w = Week(date(2026, 9, 13), 40, 4.73, SBM_FUT, DDG, LH_FUT, LH_BASIS)
    fut = crush_table(app_projection(), [w], corn_is_cash=False)
    cash = crush_table(app_projection(), [w], corn_is_cash=True)
    assert fut.loc["Corn $/bu paid"].iloc[0] != cash.loc["Corn $/bu paid"].iloc[0]
    assert CORN_BASIS != 0


def test_sale_date_helper():
    assert sale_for(date(2026, 9, 13), 1, 160) == date(2027, 2, 21)


def test_value_on_and_report_dates():
    import pandas as pd

    from hogproj.crush import report_dates, value_on

    s = pd.Series([1.0, 2.0], pd.to_datetime(["2026-09-06", "2026-09-13"]))
    assert value_on(s, date(2026, 9, 12)) == 1.0
    assert value_on(s, date(2026, 9, 13)) == 2.0
    assert value_on(s, date(2026, 9, 1)) is None
    ds = report_dates(date(2026, 9, 13), weeks_back=3, weeks_forward=1)
    assert ds == [date(2026, 9, 20), date(2026, 9, 13), date(2026, 9, 6), date(2026, 8, 30)]


def test_build_weeks_uses_history_then_falls_back():
    import pandas as pd

    from hogproj.crush import build_weeks

    wean = pd.Series([35.0], pd.to_datetime(["2026-09-13"]))
    corn = pd.Series([4.10, 4.20], pd.to_datetime(["2026-09-11", "2026-09-14"]))
    hist = {"2027-04": pd.Series([79.0], pd.to_datetime(["2026-09-14"]))}
    weeks, notes = build_weeks(
        [date(2026, 9, 13), date(2026, 9, 6)],
        1,
        160,
        wean=wean,
        corn=corn,
        sbm=None,
        fallback_wean=99,
        fallback_corn=9.9,
        fallback_sbm=333,
        ddgs_usd_ton=180,
        hog_curve={"2027-04": 74.0},
        hog_contract_history=hist,
        basis_by_period={4: -2.5},
        today=date(2026, 10, 19),
    )
    newest, older = weeks
    assert (newest.wean_usd_hd, newest.corn_usd_bu, newest.sbm_usd_ton) == (35.0, 4.20, 333)
    assert newest.hog_futures_cwt == 79.0  # Apr history as of placement
    assert newest.hog_basis_cwt == -2.5  # sale Feb 21 -> period 4 (Feb 15-end)
    assert older.wean_usd_hd == 99  # no weaned pig history that early
    # placed Sep 7, sold Feb 14 -> Feb contract: no history, not on the curve -> copies Apr
    assert older.hog_futures_cwt == 74.0
    assert "2027-02 futures: none, copied from 2027-04" in notes
    assert "soybean meal: no history that early, today's price used" in notes
    assert "weaned pig price: no history that early, today's price used" in notes


def test_build_weeks_future_weeks_use_today_and_stale_prices_are_flagged():
    import pandas as pd

    from hogproj.crush import build_weeks

    corn = pd.Series([4.10], pd.to_datetime(["2026-09-01"]))
    weeks, notes = build_weeks(
        [date(2026, 10, 25), date(2026, 10, 11)],
        1,
        160,
        wean=None,
        corn=corn,
        sbm=None,
        fallback_wean=30,
        fallback_corn=4.50,
        fallback_sbm=300,
        ddgs_usd_ton=180,
        hog_curve={"2027-04": 74.0},
        hog_contract_history={"2027-04": pd.Series([90.0], pd.to_datetime(["2026-10-01"]))},
        basis_by_period={},
        today=date(2026, 10, 19),
    )
    future, past = weeks
    assert future.corn_usd_bu == 4.50  # today's price, not the stale Sep 1 value
    assert future.hog_futures_cwt == 74.0  # today's curve, not the Oct 1 history
    assert past.corn_usd_bu == 4.10 and past.hog_futures_cwt == 90.0
    assert "weeks placed after today use today's prices" in notes
    assert "corn: last value (Sep 01, 2026) carried forward" in notes


def test_current_report_date_keeps_weekday():
    from hogproj.crush import current_report_date

    assert current_report_date(date(2026, 9, 13), date(2026, 10, 19)) == date(2026, 10, 18)
    assert current_report_date(date(2026, 10, 18), date(2026, 10, 19)) == date(2026, 10, 18)
