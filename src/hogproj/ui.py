"""Streamlit helpers shared by the pages in views/. UI layer: may import streamlit and data."""

from typing import Literal

import pandas as pd
import streamlit as st

from hogproj.config import get_settings
from hogproj.data.ams import Source, load_hg201
from hogproj.finance import CostInputs
from hogproj.herd import HerdInputs
from hogproj.markets import lean_hog_index
from hogproj.outlook import Plan

GOOD, BAD, NEUTRAL, ACCENT = "#2e7d32", "#c62828", "#8a9a93", "#1f6f50"


def usd(x: float, decimals: int = 2) -> str:
    """-11.6 -> '-$11.60' (not '$-11.60'); -0.004 -> '$0.00' (no '-$0')."""
    x = round(x, decimals) + 0.0  # + 0.0 turns -0.0 into 0.0
    return f"{'-' if x < 0 else ''}${abs(x):,.{decimals}f}"


def usd_short(x: float) -> str:
    """Compact dollars for headlines: 1_234_567 -> '$1.23M', -869_092 -> '-$869k'."""
    a = abs(x)
    sign = "-" if x < 0 and round(a) else ""
    if a >= 1e6:
        return f"{sign}${a / 1e6:.2f}M"
    if a >= 1e4:
        return f"{sign}${a / 1e3:,.0f}k"
    return f"{sign}${a:,.0f}"


@st.cache_data(ttl=6 * 3600, show_spinner="Loading USDA hog prices…")
def _hg201(offline: bool) -> tuple[pd.DataFrame, Source, str]:
    return load_hg201(offline)


def hog_index() -> tuple[pd.DataFrame, Source, str]:
    """Lean Hog Index history (live, cached or sample) and a note on where it came from."""
    raw, source, note = _hg201(get_settings().offline)
    return lean_hog_index(raw), source, note


def latest_hog_index() -> float:
    idx, _, _ = hog_index()
    return round(float(idx["lean_hog_index_usd_per_cwt_carcass"].iloc[-1]), 2)


def current_plan() -> Plan:
    """The plan the user has set up on the Herd flow and Costs pages (defaults if unvisited)."""
    herd: HerdInputs = st.session_state.get("herd_inputs", HerdInputs())
    cost: CostInputs = st.session_state.get(
        "cost_inputs",
        CostInputs(
            lean_hog_usd_per_cwt_carcass=latest_hog_index(),
            weight_lb_live_market=herd.weight_lb_live_market,
            carcass_yield=herd.carcass_yield,
        ),
    )
    return Plan(herd=herd, cost=cost, seasonal=st.session_state.get("seasonal", True))


def data_notice(source: Source, note: str) -> None:
    if source == "live":
        st.caption(f"✅ {note}")
    else:
        st.warning(note, icon="📦")


def verdict(kind: Literal["good", "bad", "neutral"], headline: str, detail: str = "") -> None:
    """A large plain-English takeaway box. Text must be trusted (we build it from numbers)."""
    # HTML entity: shows "$" without Streamlit reading "$...$" as LaTeX math
    headline, detail = headline.replace("$", "&#36;"), detail.replace("$", "&#36;")
    color = {"good": GOOD, "bad": BAD, "neutral": NEUTRAL}[kind]
    tint = {"good": "#eef7ef", "bad": "#fdeeee", "neutral": "#f3f6f4"}[kind]
    st.markdown(
        f"""<div style="border-left:6px solid {color};background:{tint};border-radius:8px;
        padding:14px 18px;margin:4px 0 14px 0">
        <div style="font-size:1.25rem;font-weight:600;color:#1d2a24">{headline}</div>
        <div style="margin-top:4px;color:#3d4a44">{detail}</div></div>""",
        unsafe_allow_html=True,
    )
