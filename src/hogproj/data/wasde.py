"""USDA WASDE (World Agricultural Supply and Demand Estimates): quarterly U.S. pork production
and barrow/gilt price forecasts. Public text file, no key.

The barrow/gilt price is USDA's "national base, live equivalent, 51-52% lean" in $/cwt LIVE —
not the CME index, which is a carcass net price. Monthly report around the 10th-12th; the newest
available issue is used (this month's, else last month's).
"""

import re
from datetime import date
from typing import Literal

import httpx
import pandas as pd

from hogproj.config import CACHE_DIR, SAMPLE_DIR
from hogproj.data.saved import newest

URL = "https://www.usda.gov/oce/commodity/wasde/wasde{mmyy}.txt"
WASDE_FILE = "wasde_pork.csv"
COLUMNS = ["year", "quarter", "series", "value", "projected", "report"]
Source = Literal["live", "cache", "sample"]
_QUARTERS = {"I": 1, "II": 2, "III": 3, "IV": 4}


def _table(text: str, title: str) -> list[str]:
    start = text.index(title)
    body = re.split(r"={20,}", text[start:])
    # [title] rule [column heads] rule [rows] rule ...
    return body[2].splitlines() if len(body) > 2 else []


def _rows(lines: list[str], col: int, series: str, report: str) -> list[dict]:
    out, year = [], None
    for line in lines:
        t = line.split()
        if not t:
            continue
        if re.fullmatch(r"\d{4}", t[0]) and len(t) == 1:
            year = int(t[0])
            continue
        if year is None:
            continue
        q = t[0].rstrip("*")
        if q not in _QUARTERS or len(t) <= col:
            continue  # annual and SepProj./OctProj. rows: quarters only
        out.append({"year": year, "quarter": _QUARTERS[q], "series": series,
                    "value": float(t[col]), "projected": t[0].endswith("*"),
                    "report": report})  # fmt: skip
    return out


def parse(text: str) -> pd.DataFrame:
    """WASDE text -> quarterly pork production (million lb) and barrow/gilt price ($/cwt live)."""
    when = re.search(r"WASDE - \d+ - \d+\s+(\w+ \d{4})", text)
    if not when or "U.S. Quarterly Prices for Animal Products" not in text:
        raise ValueError("Not a WASDE report")
    report = when[1]
    prod = _table(text, "U.S. Quarterly Animal Product Production")
    price = _table(text, "U.S. Quarterly Prices for Animal Products")
    rows = _rows(prod, 2, "pork_production_mlb", report)
    rows += _rows(price, 2, "barrows_gilts_usd_cwt_live", report)
    if not rows:
        raise ValueError("No pork rows found")
    return pd.DataFrame(rows, columns=COLUMNS)


def fetch(today: date, client: httpx.Client | None = None) -> pd.DataFrame:
    with client or httpx.Client(timeout=60, follow_redirects=True) as c:
        y, m = today.year, today.month
        for _ in range(3):  # this month's issue may not be out yet
            resp = c.get(URL.format(mmyy=f"{m:02d}{y % 100:02d}"))
            if resp.status_code == 200 and "WASDE" in resp.text[:400]:
                return parse(resp.text)
            y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    raise ValueError("No recent WASDE issue found")


def load(offline: bool) -> tuple[pd.DataFrame, Source, str]:
    cache = CACHE_DIR / WASDE_FILE
    if not offline:
        try:
            df = fetch(date.today())
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", f"Live from USDA WASDE ({df['report'].iloc[0]})."
        except (httpx.HTTPError, ValueError) as e:
            problem = f"Couldn't reach USDA ({type(e).__name__})."
    else:
        problem = "Offline mode."
    path = newest(cache, SAMPLE_DIR / WASDE_FILE)
    df = pd.read_csv(path)
    return df, "cache" if path == cache else "sample", f"{problem} Showing saved WASDE."


# --- History: every past report we can reach, to judge how accurate the forecasts have been --
ESMIS = "https://esmis.nal.usda.gov/publication/world-agricultural-supply-and-demand-estimates"
HISTORY_FILE = "wasde_history.csv"


def fetch_history(client: httpx.Client | None = None) -> pd.DataFrame:
    """Every WASDE text file the USDA archive page lists (about the last year), parsed."""
    with client or httpx.Client(timeout=90, follow_redirects=True) as c:
        page = c.get(ESMIS).text
        links = sorted(set(re.findall(r"release-files/\d+/wasde\d{4}\.txt", page)))
        parts = []
        for link in links:
            resp = c.get(f"https://esmis.nal.usda.gov/sites/default/{link}")
            if resp.status_code == 200:
                try:
                    parts.append(parse(resp.text))
                except ValueError:
                    continue
    if not parts:
        raise ValueError("No WASDE reports found")
    return pd.concat(parts, ignore_index=True)


def load_history(offline: bool) -> tuple[pd.DataFrame, Source, str]:
    """Saved reports plus any new ones; the history only grows."""
    cache = CACHE_DIR / HISTORY_FILE
    path = newest(cache, SAMPLE_DIR / HISTORY_FILE)
    saved = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=COLUMNS)
    if not offline:
        try:
            new = fetch_history()
            df = pd.concat([f for f in (saved, new) if not f.empty], ignore_index=True)
            df = df.drop_duplicates(["report", "year", "quarter", "series"], keep="last")
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", f"{df['report'].nunique()} WASDE reports."
        except (httpx.HTTPError, ValueError) as e:
            problem = f"Couldn't reach USDA ({type(e).__name__})."
    else:
        problem = "Offline mode."
    return saved, "cache" if path == cache else "sample", f"{problem} Showing saved reports."
