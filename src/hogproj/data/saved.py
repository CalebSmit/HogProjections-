"""Which saved copy to read when the live source can't be reached: the local cache or the
sample bundled with the app (refreshed weekly on GitHub). The newer data wins, so an old cache
on one machine never hides a newer sample that arrived with `git pull`."""

from pathlib import Path

import pandas as pd

DATE_COLUMNS = ("slaughter_date", "date", "week_ending", "month", "sale_month", "period_start",
                "report")  # fmt: skip


def latest(path: Path) -> pd.Timestamp | None:
    """Newest date in a saved CSV (None if unreadable or undated)."""
    try:
        cols = pd.read_csv(path, nrows=0).columns
        col = next((c for c in DATE_COLUMNS if c in cols), None)
        if col is None:
            return None
        d = pd.to_datetime(pd.read_csv(path, usecols=[col])[col], errors="coerce", format="mixed")
        top = d.max()
        return None if pd.isna(top) else pd.Timestamp(top)
    except (OSError, ValueError, pd.errors.EmptyDataError):
        return None


def newest(cache: Path, sample: Path) -> Path:
    """The cache, unless the bundled sample has later data (or the cache is missing)."""
    if not cache.exists():
        return sample
    if not sample.exists():
        return cache
    c, s = latest(cache), latest(sample)
    return sample if c is None or (s is not None and s > c) else cache
