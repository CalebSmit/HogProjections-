"""Saved copies: the newer of the local cache and the bundled sample wins."""

from datetime import date

import pandas as pd

from hogproj.data.saved import latest, newest
from hogproj.freshness import is_current


def _csv(path, last):
    pd.DataFrame({"date": ["2026-01-05", last], "v": [1, 2]}).to_csv(path, index=False)
    return path


def test_newer_sample_beats_old_cache(tmp_path):
    cache = _csv(tmp_path / "cache.csv", "2026-09-01")
    sample = _csv(tmp_path / "sample.csv", "2026-10-19")
    assert newest(cache, sample) == sample
    assert latest(sample) == pd.Timestamp("2026-10-19")


def test_cache_wins_when_newer_or_only_copy(tmp_path):
    cache = _csv(tmp_path / "cache.csv", "2026-10-20")
    sample = _csv(tmp_path / "sample.csv", "2026-10-19")
    assert newest(cache, sample) == cache
    assert newest(cache, tmp_path / "missing.csv") == cache
    assert newest(tmp_path / "missing.csv", sample) == sample


def test_month_and_report_columns(tmp_path):
    p = tmp_path / "w.csv"
    pd.DataFrame({"report": ["September 2026", "October 2026"]}).to_csv(p, index=False)
    assert latest(p) == pd.Timestamp("2026-10-01")


def test_is_current_uses_each_sources_limit():
    assert is_current("Inspected slaughter", "2026-10-16", date(2026, 10, 20))
    assert not is_current("Inspected slaughter", "2026-10-01", date(2026, 10, 20))
