"""The forward margin board: for each lean hog contract that pigs placed over the coming months
sell into, the margin per pig at today's contract prices, how it ranks against every placement
since 2020, what the user's hedge rule says, and how that rank has moved over recent weeks
(from a daily snapshot kept in the local cache). Pure apart from the snapshot file.
"""

from collections.abc import Callable
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from hogproj.book import HedgeRule, hedge_rule
from hogproj.config import CACHE_DIR
from hogproj.crush import margin_rank

FILE = "margin_board.csv"
LAGS = {"Today": 0, "1 wk ago": 7, "2 wk ago": 14, "4 wk ago": 28, "8 wk ago": 56}


def summarize(forward: pd.DataFrame, history: np.ndarray, rule: HedgeRule, cwt: float,
              hedged: dict[str, float] | None = None, today: date | None = None,
              band: Callable[[float], float | None] | None = None) -> pd.DataFrame:  # fmt: skip
    """One row per contract: placement window, hog price, average margin ($/pig and $/cwt
    carcass), rank vs history, hog:corn ratio and the rule's verdict."""
    if forward is None or forward.empty:
        return pd.DataFrame()
    hedged = hedged or {}
    today = today or date.today()
    rows = []
    for k, g in forward.groupby("contract", sort=False):
        m = float(g["margin_usd"].mean())
        rank = margin_rank(m, history)
        tone, why = hedge_rule(rank, rule.trigger, rule.target, hedged.get(str(k), 0.0), rule, m)
        hog = float(g["hog_usd_per_cwt"].iloc[0])
        corn = float(g["corn_usd_per_bu"].mean())
        rows.append({
            "contract": str(k), "placed_from": g["placed"].min(), "placed_to": g["placed"].max(),
            "weeks": len(g), "hog_usd_per_cwt": hog, "margin_usd": m,
            "margin_usd_per_cwt": m / cwt if cwt else np.nan, "rank": rank,
            "most_usd": float(g["most_usd"].mean()),
            "pig_expected_usd": float(g["pig_expected_usd"].mean()),
            "hog_corn_ratio": hog * 0.75 / corn if corn else np.nan,  # live price ÷ corn $/bu
            "rule_tone": tone, "rule_says": why,
            **_range(m, cwt, g, today, band),
        })  # fmt: skip
    return pd.DataFrame(rows)


def _range(m: float, cwt: float, g: pd.DataFrame, today: date,
           band: Callable[[float], float | None] | None) -> dict[str, float]:  # fmt: skip
    """Likely margin range: the hog price could land as far from today's contract price as the
    seasonal estimate missed 8 times in 10 at that distance (×carcass cwt)."""
    if band is None or "sold" not in g:
        return {"months_ahead": np.nan, "low_usd": np.nan, "high_usd": np.nan}
    months = (pd.to_datetime(g["sold"]).mean() - pd.Timestamp(today)).days / 30.4
    b = band(months)
    if b is None:
        return {"months_ahead": months, "low_usd": np.nan, "high_usd": np.nan}
    return {"months_ahead": months, "low_usd": m - b * cwt, "high_usd": m + b * cwt}


def _path(folder: Path | None) -> Path:
    return (folder or CACHE_DIR) / FILE


def record(day: date, board: pd.DataFrame, folder: Path | None = None) -> None:
    """Keep today's board (replacing an earlier one from the same day)."""
    if board.empty:
        return
    path = _path(folder)
    new = board[["contract", "margin_usd", "rank"]].assign(date=pd.Timestamp(day))
    old = pd.read_csv(path, parse_dates=["date"]) if path.exists() else pd.DataFrame()
    if not old.empty:
        old = old[old["date"] != pd.Timestamp(day)]
    df = pd.concat([f for f in (old, new) if not f.empty], ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.sort_values(["date", "contract"]).to_csv(path, index=False)


def trend(day: date, board: pd.DataFrame, folder: Path | None = None,
          tolerance_days: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:  # fmt: skip
    """(rank, margin) grids: contracts × LAGS, today's column from `board`, earlier columns from
    the nearest snapshot within `tolerance_days` before each lag (blank when none)."""
    contracts = list(board["contract"])
    rank = pd.DataFrame(index=contracts, columns=list(LAGS), dtype=float)
    margin = rank.copy()
    rank["Today"] = board.set_index("contract")["rank"]
    margin["Today"] = board.set_index("contract")["margin_usd"]
    path = _path(folder)
    if path.exists():
        snaps = pd.read_csv(path, parse_dates=["date"])
        for label, lag in LAGS.items():
            if lag == 0:
                continue
            t = pd.Timestamp(day) - pd.Timedelta(days=lag)
            ok = snaps[
                (snaps["date"] <= t) & (snaps["date"] >= t - pd.Timedelta(days=tolerance_days))
            ]
            if ok.empty:
                continue
            snap = ok[ok["date"] == ok["date"].max()].set_index("contract")
            rank[label] = snap["rank"].reindex(contracts)
            margin[label] = snap["margin_usd"].reindex(contracts)
    return rank, margin
