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
from hogproj.data.weanpig import fetch_feeder_pig, lot_min_head, weekly_price

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

    if cached.exists():  # a failed refresh must not throw away good history
        s = _read_series(cached)
        return Loaded(
            s, fail + f"Using cached history ({s.index.min():%Y}–{s.index.max():%Y}).", False
        )
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


def load_wean_pig_prices(min_lot_head: int = 2400) -> Loaded:
    """Weekly USDA early-weaned prices: DataFrame date, cash_usd_hd, formula_usd_hd, cash_lot."""
    settings = get_settings()
    if settings.offline:
        return Loaded(pd.DataFrame(), "Offline mode: enter the weaned pig price by hand.", False)
    try:
        rows = fetch_feeder_pig(settings.usda_mmn_api_key)
    except FetchError as e:
        return Loaded(
            pd.DataFrame(),
            f"USDA weaned pig report not loaded ({e}). Using the price on screen.",
            False,
        )
    cash = weekly_price(rows, "cash", min_lot_head)
    formula = weekly_price(rows, "formula", min_lot_head)
    df = cash.rename(columns={"price_usd_hd": "cash_usd_hd", "lot": "cash_lot"})[
        ["date", "cash_usd_hd", "cash_lot"]
    ].merge(
        formula.rename(columns={"price_usd_hd": "formula_usd_hd"})[["date", "formula_usd_hd"]],
        on="date",
        how="outer",
    )
    lot = str(cash["lot"].iloc[-1]) if not cash.empty else "n/a"
    note = f"Live: USDA National Direct Feeder Pig Report (2810), early weaned. Cash lot: {lot}."
    if not cash.empty and cash["lot"].iloc[-1] and lot_min_head(lot) < min_lot_head:
        note += f" The report has no {min_lot_head:,}+ head bucket, so the largest lot is used."
    return Loaded(df.sort_values("date"), note, True)


def load_grain_futures() -> Loaded:
    """Front-month CBOT corn ($/bu) and soybean meal ($/ton) from Yahoo (ZC=F is in cents)."""
    if get_settings().offline:
        return Loaded({}, "Offline mode: enter corn and soybean meal futures by hand.", False)
    end = date.today()
    out: dict[str, float] = {}
    try:
        corn = fetch_yahoo_daily("ZC=F", end - timedelta(days=10), end)
        meal = fetch_yahoo_daily("ZM=F", end - timedelta(days=10), end)
    except FetchError as e:
        return Loaded({}, f"Grain futures not loaded ({e}); using the prices on screen.", False)
    if not corn.empty:
        out["corn_usd_bu"] = float(corn.iloc[-1]) / 100
    if not meal.empty:
        out["sbm_usd_ton"] = float(meal.iloc[-1])
    return Loaded(out, "Live: CBOT front-month corn and soybean meal (Yahoo, delayed).", bool(out))
