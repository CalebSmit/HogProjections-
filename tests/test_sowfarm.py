"""Sow farm: cost per weaned pig (ISU farrow-to-wean, Sep 2026), margins, integrated system."""

import pandas as pd
import pytest

from hogproj.sowfarm import (
    ISU_SEP_2026,
    SowInputs,
    by_year,
    cost_lines,
    cost_per_weaned_pig,
    history,
    integrated,
    margin,
)


def test_defaults_reproduce_isu_farrow_to_wean_sep_2026():
    assert cost_per_weaned_pig(SowInputs()) == pytest.approx(
        ISU_SEP_2026["cost_per_weaned_pig"], abs=0.01
    )


def test_more_pigs_per_sow_lowers_cost_per_pig():
    s = SowInputs()
    better = s.model_copy(update={"weaned_per_sow_yr": 31.0})
    assert cost_per_weaned_pig(better) < cost_per_weaned_pig(s)
    per_sow = cost_per_weaned_pig(s) * s.weaned_per_sow_yr
    assert cost_per_weaned_pig(better) * 31.0 == pytest.approx(per_sow)  # per-sow cost unchanged


def test_corn_moves_cost_by_feed_share():
    s = SowInputs()
    up = cost_per_weaned_pig(s, corn=5.00) - cost_per_weaned_pig(s)
    assert up == pytest.approx(s.corn_lb_per_sow_yr * 1.00 / 56 / s.weaned_per_sow_yr)


def test_cost_lines_total():
    t = cost_lines(SowInputs())
    assert t.loc["Total", "usd_per_weaned_pig"] == pytest.approx(43.91, abs=0.01)
    assert t.drop(index="Total")["usd_per_sow_yr"].sum() == pytest.approx(
        t.loc["Total", "usd_per_sow_yr"]
    )


def test_margin_includes_adder():
    s = SowInputs(adder_usd_per_head=7.0)
    assert margin(s, 40.0) == pytest.approx(47.0 - cost_per_weaned_pig(s))


def _pigs() -> pd.DataFrame:
    return pd.DataFrame(
        {"week_ending": pd.to_datetime(["2026-01-09", "2026-02-13"]),
         "cash_usd_per_head": [50.0, 30.0]}
    )  # fmt: skip


def test_history_uses_monthly_corn():
    corn = pd.DataFrame({"month": pd.to_datetime(["2026-01-01"]), "usd_per_bu": [5.0]})
    h = history(_pigs(), SowInputs(), corn)
    assert h["corn_usd_per_bu"].tolist() == [5.0, 4.0]  # Feb not reported -> today's input
    assert h["margin_usd"].iloc[1] == pytest.approx(30.0 - 43.9111, abs=0.01)


def test_integrated_is_sum_of_parts_and_joins_on_placement_week():
    h = history(_pigs(), SowInputs())
    crush = pd.DataFrame(
        {"placed": pd.to_datetime(["2026-01-05", "2026-02-09", "2026-03-02"]),
         "status": ["sold", "on feed", "sold"], "margin_usd": [12.0, -5.0, 3.0]}
    )  # fmt: skip
    df = integrated(h, crush)
    assert len(df) == 1  # Feb placement still on feed; Mar has no USDA week in the sample
    row = df.iloc[0]
    assert row["integrated_usd"] == pytest.approx(row["margin_usd"] + 12.0)
    y = by_year(df).iloc[0]
    assert y["integrated_usd"] == pytest.approx(y["sow_usd"] + y["finish_usd"])
