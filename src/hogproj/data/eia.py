"""U.S. Energy Information Administration weekly fuel prices (public Excel files, no key):
diesel for trucking, propane for heating barns. Propane is surveyed in the heating season
(October to March) only, so it has gaps by design.
"""

import io
from typing import Literal

import httpx
import pandas as pd

from hogproj.config import CACHE_DIR, SAMPLE_DIR

BASE = "https://www.eia.gov/dnav/pet/hist_xls"
SERIES = {  # name -> (file, label)
    "diesel_us": ("EMD_EPD2D_PTE_NUS_DPGw.xls", "U.S. on-highway diesel"),
    "propane_mn": ("W_EPLLPA_PRS_SMN_DPGw.xls", "Minnesota residential propane"),
    "propane_ia": ("W_EPLLPA_PRS_SIA_DPGw.xls", "Iowa residential propane"),
}
EIA_FILE = "eia_fuel_prices.csv"
Source = Literal["live", "cache", "sample"]


def parse(content: bytes, name: str) -> pd.DataFrame:
    """EIA history workbook ('Data 1': date, $/gal) -> date, series, usd_per_gal."""
    df = pd.read_excel(io.BytesIO(content), sheet_name="Data 1", header=2)
    df = df.iloc[:, :2].dropna()
    df.columns = ["date", "usd_per_gal"]
    df["date"] = pd.to_datetime(df["date"])
    df["series"] = name
    return df[df["date"] >= pd.Timestamp("2015-01-01")][["date", "series", "usd_per_gal"]]


def fetch(client: httpx.Client | None = None) -> pd.DataFrame:
    parts = []
    with client or httpx.Client(timeout=60, follow_redirects=True) as c:
        for name, (file, _) in SERIES.items():
            resp = c.get(f"{BASE}/{file}")
            if resp.status_code == 200:
                parts.append(parse(resp.content, name))
    if not parts:
        raise ValueError("No EIA series reached")
    return pd.concat(parts, ignore_index=True)


def load(offline: bool) -> tuple[pd.DataFrame, Source, str]:
    cache = CACHE_DIR / EIA_FILE
    if not offline:
        try:
            df = fetch()
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", "Live from the U.S. Energy Information Administration."
        except Exception as e:  # network or file layout change: keep the saved copy
            problem = f"Couldn't reach EIA ({type(e).__name__})."
    else:
        problem = "Offline mode."
    path = cache if cache.exists() else SAMPLE_DIR / EIA_FILE
    df = pd.read_csv(path, parse_dates=["date"])
    return df, "cache" if path == cache else "sample", f"{problem} Showing saved prices."
