"""USDA ERS Livestock and Meat Domestic Data (keyless ZIP): monthly pork in cold storage.

Beginning-of-month frozen pork stocks, million pounds (from NASS Cold Storage, compiled by ERS).
ERS can change the /media/NNNN/ part of the URL when it republishes; on failure the app keeps
the cached or bundled copy.
"""

import io
import zipfile
from typing import Literal

import httpx
import pandas as pd

from hogproj.config import CACHE_DIR, SAMPLE_DIR
from hogproj.data.saved import newest

URL = "https://www.ers.usda.gov/media/5539/livestock-domestic-data-machine-readable-files.zip"
ERS_FILE = "ers_pork_cold_storage.csv"
Source = Literal["live", "cache", "sample"]


def parse(meat_statistics: pd.DataFrame) -> pd.DataFrame:
    """Meat-Statistics.csv -> month, pork_stocks_mlb (2010 on)."""
    p = meat_statistics[(meat_statistics["commodity_desc"] == "Pork")
                        & (meat_statistics["attribute_desc"] == "Cold storage")]  # fmt: skip
    df = pd.DataFrame(
        {"month": pd.to_datetime(
            {"year": p["year_id"].astype(int), "month": p["timeperiod_id"].astype(int), "day": 1}
         ).to_numpy(),
         "pork_stocks_mlb": pd.to_numeric(p["amount"], errors="coerce").to_numpy()}
    )  # fmt: skip
    df = df[df["month"] >= pd.Timestamp("2010-01-01")].dropna()
    return df.sort_values("month").reset_index(drop=True)


def fetch(client: httpx.Client | None = None) -> pd.DataFrame:
    with client or httpx.Client(timeout=90, follow_redirects=True) as c:
        resp = c.get(URL)
        resp.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    name = next(n for n in zf.namelist() if n.endswith("Meat-Statistics.csv"))
    return parse(pd.read_csv(zf.open(name)))


def load(offline: bool) -> tuple[pd.DataFrame, Source, str]:
    cache = CACHE_DIR / ERS_FILE
    if not offline:
        try:
            df = fetch()
            if df.empty:
                raise ValueError("no pork cold storage rows")
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", "Live from USDA ERS (cold storage)."
        except (httpx.HTTPError, ValueError, KeyError, StopIteration, zipfile.BadZipFile) as e:
            problem = f"Couldn't reach USDA ERS ({type(e).__name__})."
    else:
        problem = "Offline mode."
    path = newest(cache, SAMPLE_DIR / ERS_FILE)
    df = pd.read_csv(path, parse_dates=["month"])
    return df, "cache" if path == cache else "sample", f"{problem} Showing saved cold storage."
