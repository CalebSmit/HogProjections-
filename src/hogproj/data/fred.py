"""Bank prime loan rate from FRED (St. Louis Fed), keyless CSV: the base most ag operating
lines are priced from."""

import io
from typing import Literal

import httpx
import pandas as pd

from hogproj.config import CACHE_DIR, SAMPLE_DIR

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_FILE = "fred_prime_rate.csv"
Source = Literal["live", "cache", "sample"]


def parse(text: str) -> pd.DataFrame:
    """FRED CSV (date, DPRIME; '.' for missing days) -> date, prime_pct from 2015."""
    df = pd.read_csv(io.StringIO(text))
    df.columns = ["date", "prime_pct"]
    df["date"] = pd.to_datetime(df["date"])
    df["prime_pct"] = pd.to_numeric(df["prime_pct"], errors="coerce")
    return df.dropna()[lambda x: x["date"] >= "2015-01-01"].reset_index(drop=True)


def load(offline: bool) -> tuple[pd.DataFrame, Source, str]:
    cache = CACHE_DIR / FRED_FILE
    if not offline:
        try:
            resp = httpx.get(URL, params={"id": "DPRIME"}, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            df = parse(resp.text)
            if df.empty:
                raise ValueError("FRED returned no rows")
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", "Live from FRED."
        except (httpx.HTTPError, ValueError) as e:
            problem = f"Couldn't reach FRED ({type(e).__name__})."
    else:
        problem = "Offline mode."
    path = cache if cache.exists() else SAMPLE_DIR / FRED_FILE
    df = pd.read_csv(path, parse_dates=["date"])
    return df, "cache" if path == cache else "sample", f"{problem} Showing the saved rate."
