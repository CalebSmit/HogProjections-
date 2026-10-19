"""Streamlit helpers shared by the pages in views/. UI layer: may import streamlit and data."""

import pandas as pd
import streamlit as st

from hogproj.config import get_settings
from hogproj.data.ams import Source, load_hg201
from hogproj.markets import lean_hog_index


def usd(x: float, decimals: int = 2) -> str:
    """-11.6 -> '-$11.60' (not '$-11.60'); -0.004 -> '$0.00' (no '-$0')."""
    x = round(x, decimals) + 0.0  # + 0.0 turns -0.0 into 0.0
    return f"{'-' if x < 0 else ''}${abs(x):,.{decimals}f}"


@st.cache_data(ttl=6 * 3600, show_spinner="Loading USDA hog prices…")
def _hg201(offline: bool) -> tuple[pd.DataFrame, Source, str]:
    return load_hg201(offline)


def hog_index() -> tuple[pd.DataFrame, Source, str]:
    """Lean Hog Index history (live, cached or sample) and a note on where it came from."""
    raw, source, note = _hg201(get_settings().offline)
    return lean_hog_index(raw), source, note


def data_notice(source: Source, note: str) -> None:
    if source == "live":
        st.caption(f"✅ {note}")
    else:
        st.warning(note, icon="📦")
