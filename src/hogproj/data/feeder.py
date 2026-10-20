"""USDA weaned pig prices: National Direct Feeder Pig Report (AMS_2810, formerly NW_LS255).

The series is the weekly cash total composite for early weaned pigs, 10-12 lb, $/head delivered:
the price wean-to-finish margins start from. USDA posts the current report as a public PDF (no
key needed) with this week and the last reported week. History comes from the bundled sample
(weekly, Oct 2020 on) plus every week fetched since, kept in the local cache.
"""

import io
import re
from datetime import datetime
from typing import Literal

import httpx
import pandas as pd

from hogproj.config import CACHE_DIR, SAMPLE_DIR

REPORT_URL = "https://www.ams.usda.gov/mnreports/ams_2810.pdf"
FEEDER_FILE = "usda_weaned_pig_prices.csv"
COLUMNS = ["week_ending", "cash_usd_per_head", "low_usd_per_head", "high_usd_per_head"]

Source = Literal["live", "cache", "sample"]

_NUM = r"([\d,]+(?:\.\d+)?)"


def _f(s: str) -> float:
    return float(s.replace(",", ""))


def parse_report(text: str) -> pd.DataFrame:
    """Report text -> rows for this week and the last reported week (cash composite only).

    Layout (one value per line once extracted): "PIGS EARLY WEANED - 10 to 12 lb" ...
    "Cash Current" ... "Total Composite", head, "lo - hi", wtd avg, "DEL", last wtd avg, ...
    """
    flat = " ".join(line.strip() for line in text.splitlines() if line.strip())
    when = re.search(
        r"National Direct Feeder Pig Report\s+\w{3}\s+(\w{3})\s+(\d+),\s+(\d{4})", flat
    )
    last = re.search(r"Last Reported \( (\d+/\d+/\d{4}) \)", flat)
    section = flat.split("PIGS EARLY WEANED - 10 to 12 lb", 1)
    if not when or len(section) < 2:
        raise ValueError("Not a National Direct Feeder Pig Report")
    cash = section[1].split("Cash Current", 1)[-1].split("Formula Current", 1)[0]
    m = re.search(rf"Total Composite {_NUM} {_NUM} - {_NUM} {_NUM} DEL(?: {_NUM})?", cash)
    if not m:
        raise ValueError("Couldn't find the early weaned cash composite")
    week = datetime.strptime(" ".join(when.groups()), "%b %d %Y")
    rows = [
        {"week_ending": week, "cash_usd_per_head": _f(m[4]), "low_usd_per_head": _f(m[2]),
         "high_usd_per_head": _f(m[3])}
    ]  # fmt: skip
    if last and m[5]:
        rows.append(
            {"week_ending": datetime.strptime(last[1], "%m/%d/%Y"),
             "cash_usd_per_head": _f(m[5]), "low_usd_per_head": None, "high_usd_per_head": None}
        )  # fmt: skip
    return pd.DataFrame(rows, columns=COLUMNS)


def fetch(client: httpx.Client | None = None) -> pd.DataFrame:
    from pypdf import PdfReader  # imported here: only needed when going online

    with client or httpx.Client(timeout=60, follow_redirects=True) as c:
        resp = c.get(REPORT_URL)
        resp.raise_for_status()
    pages = PdfReader(io.BytesIO(resp.content)).pages
    return parse_report("\n".join(p.extract_text() for p in pages))


def _read(path) -> pd.DataFrame:  # noqa: ANN001 - Path
    return pd.read_csv(path, parse_dates=["week_ending"])


def merge(history: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """History plus new weeks; a newer report's figure replaces an older one for the same week
    unless the newer one lacks the range (the 'last reported' column has no low/high)."""
    both = pd.concat([f for f in (history, new) if not f.empty], ignore_index=True)
    both["week_ending"] = pd.to_datetime(both["week_ending"])
    for col in COLUMNS[1:]:
        both[col] = pd.to_numeric(both[col], errors="coerce")
    both["_has_range"] = both["low_usd_per_head"].notna()
    both = both.sort_values(["week_ending", "_has_range"]).drop_duplicates(
        "week_ending", keep="last"
    )
    return both.drop(columns="_has_range").sort_values("week_ending").reset_index(drop=True)


def load(offline: bool) -> tuple[pd.DataFrame, Source, str]:
    """Return (weekly prices, source, note). Never raises for network problems."""
    cache = CACHE_DIR / FEEDER_FILE
    history = merge(_read(SAMPLE_DIR / FEEDER_FILE), _read(cache) if cache.exists() else
                    pd.DataFrame(columns=COLUMNS))  # fmt: skip
    if not offline:
        try:
            df = merge(history, fetch())
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", "Live from USDA AMS National Direct Feeder Pig Report."
        except Exception as e:  # network, PDF or layout problems all fall back to saved data
            problem = f"Couldn't reach USDA ({type(e).__name__})."
    else:
        problem = "Offline mode."
    last = pd.Timestamp(str(history["week_ending"].max()))
    source: Source = "cache" if cache.exists() else "sample"
    return history, source, f"{problem} Showing saved prices through {last:%b %d, %Y}."
