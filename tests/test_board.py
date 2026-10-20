"""Forward margin board: summary by contract, daily snapshots and the rank trend."""

from datetime import date

import numpy as np
import pandas as pd

from hogproj import board
from hogproj.book import HedgeRule


def _forward() -> pd.DataFrame:
    placed = pd.date_range("2026-10-20", periods=6, freq="7D")
    return pd.DataFrame({
        "placed": placed, "sold": placed + pd.Timedelta(days=160),
        "contract": ["Apr 2027"] * 3 + ["Jun 2027"] * 3,
        "hog_usd_per_cwt": [70.0] * 3 + [90.0] * 3, "pig_expected_usd": 20.0,
        "corn_usd_per_bu": 4.0, "margin_usd": [-10.0, -12.0, -14.0, 18.0, 20.0, 22.0],
        "most_usd": 10.0,
    })  # fmt: skip


HISTORY = np.arange(-50.0, 50.0)  # 100 past placements, -50 .. 49


def test_summary_by_contract_with_rank_and_rule():
    b = board.summarize(_forward(), HISTORY, HedgeRule("rank", 60, 0.5), cwt=2.15)
    apr, jun = b.iloc[0], b.iloc[1]
    assert apr["contract"] == "Apr 2027" and apr["margin_usd"] == -12 and apr["weeks"] == 3
    assert jun["rank"] == 70.5  # 70 below, 1 tie
    assert jun["rule_tone"] == "caution" and apr["rule_tone"] == "neutral"
    assert abs(jun["hog_corn_ratio"] - 90 * 0.75 / 4) < 1e-9
    assert abs(jun["margin_usd_per_cwt"] - 20 / 2.15) < 1e-9
    by_margin = board.summarize(_forward(), HISTORY, HedgeRule("margin", min_margin=25), 2.15)
    assert set(by_margin["rule_tone"]) == {"neutral"}


def test_snapshots_build_the_trend(tmp_path):
    rule = HedgeRule()
    today = board.summarize(_forward(), HISTORY, rule, 2.15)
    two_weeks_ago = today.assign(rank=[10.0, 40.0], margin_usd=[-40.0, -10.0])
    board.record(date(2026, 10, 6), two_weeks_ago, tmp_path)
    board.record(date(2026, 10, 20), today, tmp_path)
    board.record(date(2026, 10, 20), today, tmp_path)  # same day replaces, not duplicates
    assert len(pd.read_csv(tmp_path / board.FILE)) == 4
    ranks, margins = board.trend(date(2026, 10, 20), today, tmp_path)
    assert ranks.loc["Jun 2027", "2 wk ago"] == 40 and margins.loc["Apr 2027", "2 wk ago"] == -40
    assert ranks["1 wk ago"].isna().all()  # no snapshot near Oct 13


def test_empty_forward():
    assert board.summarize(pd.DataFrame(), HISTORY, HedgeRule(), 2.15).empty


def test_likely_range_uses_months_to_sale():
    b = board.summarize(_forward(), HISTORY, HedgeRule(), cwt=2.0, today=date(2026, 10, 20),
                        band=lambda months: 10.0 if months > 4 else 5.0)  # fmt: skip
    jun = b.iloc[1]
    assert jun["months_ahead"] > 4
    assert jun["low_usd"] == 20 - 20 and jun["high_usd"] == 20 + 20
