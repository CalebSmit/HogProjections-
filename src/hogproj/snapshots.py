"""What the app said before: one snapshot of the key numbers per day, kept in the local cache,
so This week can say what changed since last week and why.

The margin change is split into its drivers with the margin's own arithmetic:
    Δmargin = carcass cwt × Δhog price − Δpig price − corn lb / 56 × Δcorn + rest
"""

from datetime import date
from pathlib import Path

import pandas as pd

from hogproj.config import CACHE_DIR

FILE = "snapshots.csv"
FIELDS = ["index", "cutout", "weaned_pig", "corn", "hog_contract", "margin_today", "most_pay",
          "sow_margin", "on_feed_margin", "market_score", "cwt", "corn_lb"]  # fmt: skip


def _path(folder: Path | None = None) -> Path:
    return (folder or CACHE_DIR) / FILE


def record(day: date, values: dict[str, float], folder: Path | None = None) -> None:
    """Save today's numbers (replacing an earlier snapshot from the same day)."""
    path = _path(folder)
    old = pd.read_csv(path, parse_dates=["date"]) if path.exists() else pd.DataFrame()
    row = pd.DataFrame([{"date": pd.Timestamp(day), **{k: values.get(k) for k in FIELDS}}])
    df = pd.concat([f for f in (old, row) if not f.empty], ignore_index=True)
    df = df.drop_duplicates("date", keep="last").sort_values("date")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def previous(day: date, days: int = 7, folder: Path | None = None) -> pd.Series | None:
    """The latest snapshot at least `days` before `day` (within 21 days), if any."""
    path = _path(folder)
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["date"])
    t = pd.Timestamp(day)
    ok = df[(df["date"] <= t - pd.Timedelta(days=days)) & (df["date"] >= t - pd.Timedelta(days=21))]
    return None if ok.empty else ok.iloc[-1]


def explain(now: dict[str, float], before: pd.Series) -> list[tuple[str, float]]:
    """Margin change for a pig placed today, split into hog price, pig price, corn and the rest."""

    def num(k: str) -> float:
        return float(before[k]) if pd.notna(before.get(k)) else float("nan")

    hog = now["cwt"] * (now["hog_contract"] - num("hog_contract"))
    pig = -(now["weaned_pig"] - num("weaned_pig"))
    corn = -now["corn_lb"] / 56 * (now["corn"] - num("corn"))
    total = now["margin_today"] - num("margin_today")
    parts = [("Hog contract price", hog), ("Weaned pig price", pig), ("Corn", corn)]
    known = sum(v for _, v in parts if pd.notna(v))
    parts.append(("Other inputs", total - known))
    return [(k, v) for k, v in parts if pd.notna(v) and abs(v) >= 0.005]
