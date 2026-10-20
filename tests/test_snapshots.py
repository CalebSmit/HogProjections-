"""Snapshots of what the app said, and the since-last-week explanation."""

from datetime import date

import pytest

from hogproj import snapshots as sn

BASE = {"index": 76.0, "cutout": 83.0, "weaned_pig": 19.5, "corn": 4.30, "hog_contract": 72.0,
        "margin_today": -5.0, "most_pay": 14.0, "sow_margin": -25.0, "on_feed_margin": -40.0,
        "market_score": 0, "cwt": 2.175, "corn_lb": 500}  # fmt: skip


def test_record_keeps_one_snapshot_per_day(tmp_path):
    sn.record(date(2026, 10, 13), BASE, tmp_path)
    sn.record(date(2026, 10, 13), {**BASE, "index": 77.0}, tmp_path)  # same day: replaced
    sn.record(date(2026, 10, 20), {**BASE, "index": 73.0}, tmp_path)
    prev = sn.previous(date(2026, 10, 20), folder=tmp_path)
    assert prev is not None and prev["index"] == 77.0
    assert sn.previous(date(2026, 10, 15), folder=tmp_path) is None  # nothing a week before


def test_previous_ignores_stale_snapshots(tmp_path):
    sn.record(date(2026, 9, 1), BASE, tmp_path)
    assert sn.previous(date(2026, 10, 20), folder=tmp_path) is None  # > 21 days old


def test_explain_splits_the_margin_change(tmp_path):
    sn.record(date(2026, 10, 13), BASE, tmp_path)
    before = sn.previous(date(2026, 10, 20), folder=tmp_path)
    assert before is not None
    now = {**BASE, "hog_contract": 70.0, "weaned_pig": 20.5, "corn": 4.20}
    hog, pig, corn = 2.175 * -2.0, -1.0, -500 / 56 * -0.10
    now["margin_today"] = BASE["margin_today"] + hog + pig + corn + 0.25  # 0.25 from elsewhere
    parts = dict(sn.explain(now, before))
    assert parts["Hog contract price"] == pytest.approx(hog)
    assert parts["Weaned pig price"] == pytest.approx(pig)
    assert parts["Corn"] == pytest.approx(corn)
    assert parts["Other inputs"] == pytest.approx(0.25)
