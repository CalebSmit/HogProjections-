"""Market data orchestration: cache -> live fetch -> bundled sample, with a note saying which.

Every loader returns (data, note). The UI shows the note, so the producer always knows whether
numbers are live, cached or sample.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from hogproj.basis import daily_basis
from hogproj.config import SAMPLE_DIR, get_settings
from hogproj.data.http import FetchError, cache_path
from hogproj.data.leanhog import (
    check_index_coverage,
    cme_index,
    fetch_futures_curve,
    fetch_lm_hg201,
    fetch_yahoo_daily,
)

BASIS_FILE = "hog_basis_daily.csv"


@dataclass(frozen=True)
class Loaded:
    data: pd.Series | pd.DataFrame | dict
    note: str
    live: bool


def _read_series(path: Path) -> pd.Series:
    df = pd.read_csv(path, parse_dates=["date"])
    return pd.Series(
        df["basis_cwt"].to_numpy(), index=pd.DatetimeIndex(df["date"]), name="basis_cwt"
    )


def _write_series(s: pd.Series, path: Path) -> None:
    pd.DataFrame({"date": s.index, "basis_cwt": s.to_numpy()}).to_csv(path, index=False)


def _download_hog_basis(years: int) -> pd.Series:
    # Yahoo's HE=F rolls at expiry (10th business day), which matches the contract the
    # projection uses for a sale on that day to within a day or two (basis.lean_hog_contract_for).
    end = date.today()
    start = end - timedelta(days=365 * years)
    rows = fetch_lm_hg201(start, end)
    check_index_coverage(rows)
    index = cme_index(rows)
    futures = fetch_yahoo_daily("HE=F", start, end)
    s = daily_basis(index, futures)
    if s.empty:
        raise FetchError("no overlapping index/futures dates")
    return s


def load_hog_basis_daily(years: int = 10, refresh: bool = False) -> Loaded:
    """Daily CME Lean Hog Index minus front-month futures, as far back as `years`."""
    cached = cache_path(BASIS_FILE)
    if cached.exists() and not refresh:
        s = _read_series(cached)
        return Loaded(
            s, f"Cached hog basis history ({s.index.min():%Y}–{s.index.max():%Y}).", False
        )

    fail = "Offline mode. "
    if not get_settings().offline:
        try:
            s = _download_hog_basis(years)
            _write_series(s, cached)
            return Loaded(
                s,
                f"Live: CME Lean Hog Index rebuilt from USDA LM_HG201 minus HE front-month "
                f"futures, {s.index.min():%b %Y}–{s.index.max():%b %Y}.",
                True,
            )
        except FetchError as e:
            fail = f"Live download failed ({e}). "

    sample = SAMPLE_DIR / BASIS_FILE
    if sample.exists():
        s = _read_series(sample)
        return Loaded(s, fail + "Using bundled sample basis history.", False)
    return Loaded(
        pd.Series(dtype="float64", name="basis_cwt"),
        fail + "No basis history available: basis set to 0 until you refresh or enter it by hand.",
        False,
    )


def load_hog_futures_curve(codes: list[str]) -> Loaded:
    """Latest lean hog settles per contract; returns only the contracts found."""
    if get_settings().offline:
        return Loaded({}, "Offline mode: enter lean hog futures by hand.", False)
    curve = fetch_futures_curve(codes)
    if not curve:
        return Loaded({}, "Could not download lean hog futures; using the prices on screen.", False)
    missing = [c for c in codes if c not in curve]
    note = "Live lean hog futures (Yahoo Finance, delayed)."
    if missing:
        note += f" Not found: {', '.join(missing)}. Enter those by hand."
    return Loaded(curve, note, True)
