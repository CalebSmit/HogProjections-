"""Market data orchestration: cache -> live fetch -> bundled sample, with a note saying which.

Every loader returns (data, note). The UI shows the note, so the producer always knows whether
numbers are live, cached or sample.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from hogproj.basis import basis_from_contracts, daily_basis
from hogproj.config import SAMPLE_DIR, get_settings
from hogproj.data import barchart
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


def _download_hog_basis(years: int, index: pd.Series | None = None) -> pd.Series:
    # Yahoo's HE=F rolls at expiry (10th business day). daily_basis drops the days where that
    # differs from the contract the projection prices off (basis.in_roll_gap).
    end = date.today()
    start = end - timedelta(days=365 * years)
    if index is None or index.empty:
        rows = fetch_lm_hg201(start, end)
        check_index_coverage(rows)
        index = cme_index(rows)
    futures = fetch_yahoo_daily("HE=F", start, end)
    s = daily_basis(index, futures)
    if s.empty:
        raise FetchError("no overlapping index/futures dates")
    return s


def load_hog_basis_daily(years: int = 10, refresh: bool = False) -> Loaded:
    """Daily CME Lean Hog Index minus nearby futures, as far back as `years`.

    Order: the user's Barchart imports (index + per-contract futures, exact contract match),
    then the cache, then a live rebuild (Barchart or USDA index, Yahoo front month).
    """
    bc_index = barchart.load(barchart.Kind.CME_INDEX)
    bc_contracts = barchart.hog_contracts()
    if not bc_index.empty and bc_contracts:
        s = basis_from_contracts(bc_index, bc_contracts)
        if not s.empty:
            return Loaded(
                s,
                f"Your Barchart imports: CME Index − the exact lean hog contract for each date "
                f"({len(bc_contracts)} contracts, {s.index.min():%b %Y}–{s.index.max():%b %Y}).",
                False,
            )
    cached = cache_path(BASIS_FILE)
    if cached.exists() and not refresh:
        s = _read_series(cached)
        return Loaded(
            s, f"Cached hog basis history ({s.index.min():%Y}–{s.index.max():%Y}).", False
        )

    fail = "Offline mode. "
    if not get_settings().offline:
        try:
            s = _download_hog_basis(years, bc_index)
            _write_series(s, cached)
            source = "your Barchart CME Index" if not bc_index.empty else "USDA LM_HG201"
            return Loaded(
                s,
                f"Live: CME Lean Hog Index ({source}) minus HE front-month futures (Yahoo), "
                f"{s.index.min():%b %Y}–{s.index.max():%b %Y}.",
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
    bc = barchart.load(barchart.Kind.WEAN_PIG)
    bc_df = pd.DataFrame(
        {"date": bc.index, "cash_usd_hd": bc.to_numpy(), "cash_lot": "Barchart series"}
    )
    bc_df["formula_usd_hd"] = float("nan")
    reason = "Offline mode."
    if not settings.offline:
        try:
            rows = fetch_feeder_pig(settings.usda_mmn_api_key)
        except FetchError as e:
            reason = f"USDA report not loaded ({e})."
        else:
            return _usda_weekly(rows, min_lot_head)
    if not bc.empty:
        return Loaded(
            bc_df,
            f"{reason} Using your Barchart weaned pig series (latest {bc.index.max():%b %d, %Y}).",
            False,
        )
    return Loaded(pd.DataFrame(), f"{reason} Enter the weaned pig price by hand.", False)


def _usda_weekly(rows: pd.DataFrame, min_lot_head: int) -> Loaded:
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


def load_grain_history() -> Loaded:
    """Daily corn ($/bu) and soybean meal ($/ton) history for the weekly crush.

    Barchart imports win (and are flagged as possibly cash corn); otherwise ~1 year of Yahoo
    front-month futures. data = {"corn": Series, "sbm": Series, "corn_source": "barchart"|...}.
    """
    corn = barchart.load(barchart.Kind.CORN)
    sbm = barchart.load(barchart.Kind.SBM)
    corn_source = "barchart" if not corn.empty else "futures"
    sources = []
    if not corn.empty:
        sources.append("corn: your Barchart import")
    if not sbm.empty:
        sources.append("soybean meal: your Barchart import")
    if (corn.empty or sbm.empty) and not get_settings().offline:
        end = date.today()
        start = end - timedelta(days=400)
        try:
            if corn.empty:
                corn = fetch_yahoo_daily("ZC=F", start, end) / 100
                sources.append("corn: Yahoo front-month futures")
            if sbm.empty:
                sbm = fetch_yahoo_daily("ZM=F", start, end)
                sources.append("soybean meal: Yahoo front-month futures")
        except FetchError as e:
            sources.append(f"futures history not loaded ({e})")
    note = "; ".join(sources) if sources else "No corn/meal history: today's prices are used."
    return Loaded({"corn": corn, "sbm": sbm, "corn_source": corn_source}, note, False)
