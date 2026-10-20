"""Design system + shared page helpers for views/. UI layer: may import streamlit and data.

Direction "Field Report" (docs/DESIGN.md): an advisor's analysis, not generic software.
Warm paper page, serif headlines that state the finding, one field-green accent, numbers in a
quote-style hero and a hairline stat strip, charts labelled directly with a source line.
Tokens here mirror .streamlit/config.toml; keep them in sync.
"""

import html
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from hogproj.config import ROOT, get_settings
from hogproj.crush import (
    Contract,
    CrushInputs,
    contract_for,
    contracts_needed,
    corn_contract_for,
    forward_corn,
    model_contract_prices,
    placements,
)
from hogproj.data import feed, lmr, wasde
from hogproj.data.ams import Source, load_hg201
from hogproj.data.feeder import load as feeder_load
from hogproj.data.nass import load as nass_load
from hogproj.data.nass import load_corn
from hogproj.finance import CostInputs
from hogproj.herd import HerdInputs
from hogproj.markets import lean_hog_index, seasonal_factors
from hogproj.outlook import Plan
from hogproj.sowfarm import SowInputs

# --- Tokens ---------------------------------------------------------------------------------
# IBM Plex Sans for UI and figures + Source Serif 4 for headlines (not the default Inter).
SANS = (
    "'IBM Plex Sans', 'Segoe UI Variable Text', 'Segoe UI', system-ui, -apple-system, Arial, "
    "sans-serif"
)
SERIF = "'Source Serif 4', 'Source Serif Pro', Georgia, 'Times New Roman', serif"
FONT = SANS
PAGE = "#f7f5f0"  # warm paper
SURFACE = "#ffffff"  # panels
INK = "#1d2520"  # primary text (green-black)
INK_2 = "#4b554e"  # secondary text
MUTED = "#7c847e"  # labels, axes
LINE = "#e5e0d5"  # hairline rules and borders
GRID = "#ece8de"  # chart gridlines
ACCENT = "#1f5c45"  # field green: interaction, the headline series
ACCENT_TINT = "#e7efe9"
POS = "#178a6a"  # profit (validated vs NEG for colour-vision deficiency, ΔE 8.1)
NEG = "#c8453a"  # loss
CAUTION = "#b07a1f"
REFERENCE = "#857f73"  # breakeven / reference lines
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # categorical slots 1-3 (validated all-pairs)
BASELINE_SERIES = INK  # "current plan" when compared with scenarios
HISTORY = "#3a423d"  # actual (observed) series next to a projection
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#1c5cab"]
DIVERGING = [[0.0, NEG], [0.5, "#f3f1ec"], [1.0, POS]]  # loss <-> neutral <-> profit

GOOD, BAD, NEUTRAL = POS, NEG, MUTED  # back-compat aliases

Tone = Literal["good", "bad", "neutral", "caution"]
_TONE = {
    "good": (POS, "#e6f3ee", "#11704f"),
    "bad": (NEG, "#faebe8", "#a8352b"),
    "neutral": (MUTED, "#f0eee8", INK_2),
    "caution": (CAUTION, "#f8f0e0", "#8a5a12"),
}
TONE_TEXT = {k: v[2] for k, v in _TONE.items()}

pio.templates["hogproj"] = go.layout.Template(
    layout=go.Layout(
        font={"family": SANS, "size": 12, "color": INK_2},
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        separators=".,",
        colorway=[ACCENT, *SERIES],
        margin={"l": 4, "r": 8, "t": 8, "b": 4},
        hovermode="x unified",
        hoverlabel={
            "bgcolor": SURFACE,
            "bordercolor": LINE,
            "font": {"family": SANS, "size": 12, "color": INK},
        },
        legend={
            "orientation": "h",
            "x": 0,
            "xanchor": "left",
            "y": 1.02,
            "yanchor": "bottom",
            "font": {"size": 11.5, "color": INK_2},
            "bgcolor": "rgba(0,0,0,0)",
        },
        xaxis={
            "showgrid": False,
            "zeroline": False,
            "showline": True,
            "linecolor": "#d9d3c6",
            "ticks": "outside",
            "tickcolor": "#d9d3c6",
            "ticklen": 4,
            "tickfont": {"size": 11, "color": MUTED},
            "title": {"font": {"size": 11, "color": MUTED}, "standoff": 8},
            "automargin": True,
        },
        yaxis={
            "gridcolor": GRID,
            "gridwidth": 1,
            "zeroline": False,
            "showline": False,
            "ticks": "",
            "tickfont": {"size": 11, "color": MUTED},
            "title": {"font": {"size": 11, "color": MUTED}, "standoff": 8},
            "automargin": True,
        },
        bargap=0.3,
    )
)

_FONTS = (
    "https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;8..60,600"
    "&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap"
)

_CSS = f"""
<style>
@import url('{_FONTS}');
:root {{ --ink:{INK}; --ink2:{INK_2}; --muted:{MUTED}; --line:{LINE}; --surface:{SURFACE};
         --accent:{ACCENT}; --accent-tint:{ACCENT_TINT}; --pos:{POS}; --neg:{NEG};
         --serif:{SERIF}; }}
html, body, .stApp {{ -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }}
[data-testid="stDecoration"] {{ display: none; }}
header[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"] {{ padding-top: 2.6rem; padding-bottom: 5rem;
         max-width: 1320px; }}
h1 {{ font-family: var(--serif) !important; font-weight: 600 !important; letter-spacing: -0.012em;
         line-height: 1.18 !important; padding: 0 !important; color: var(--ink); }}
h2, h3, h4 {{ letter-spacing: -0.01em; }}
[data-testid="stHeaderActionElements"] {{ display: none; }}
p, li {{ line-height: 1.55; }}

/* Native KPI cards (pages not yet on stat_strip) */
[data-testid="stMetric"] {{ background: var(--surface); border: 1px solid var(--line);
         border-radius: 8px; padding: 15px 18px 14px; height: 100%; }}
[data-testid="stMetricLabel"] p {{ font-size: 11px !important; font-weight: 600;
         text-transform: uppercase; letter-spacing: .07em; color: var(--muted); }}
[data-testid="stMetricValue"] {{ letter-spacing: -0.02em; color: var(--ink); line-height: 1.2; }}
[data-testid="stMetricDelta"] {{ font-size: 12px; font-weight: 500; }}

/* Panels: st.container(key="card_*") */
[class*="st-key-card_"] {{ background: var(--surface); border: 1px solid var(--line);
         border-radius: 8px; padding: 20px 22px 14px; }}
[class*="st-key-hero"] {{ background: var(--surface); border: 1px solid var(--line);
         border-radius: 8px; padding: 26px 30px 18px; }}

/* Sidebar: navigation only */
[data-testid="stSidebar"] {{ border-right: 1px solid var(--line); }}
[data-testid="stSidebarHeader"] {{ padding-top: 1.5rem; padding-bottom: .5rem; }}
[data-testid="stNavSectionHeader"] {{ text-transform: uppercase; font-size: 10.5px !important;
         letter-spacing: .09em; color: var(--muted) !important; font-weight: 600;
         margin-top: 1rem; }}
[data-testid="stSidebarNavLink"] {{ border-radius: 7px; padding-top: .32rem;
         padding-bottom: .32rem; }}
[data-testid="stSidebarNavLink"] span {{ font-size: 14.5px; color: var(--ink2); }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: var(--accent-tint); }}
[data-testid="stSidebarNavLink"][aria-current="page"] span {{ color: var(--accent);
         font-weight: 600; }}
[data-testid="stSidebarUserContent"] h2 {{ font-size: 10.5px !important;
         text-transform: uppercase; letter-spacing: .09em; color: var(--muted);
         font-weight: 600; padding-top: .4rem !important; }}

/* Assumption bar: popovers styled as chips */
[class*="st-key-assume"] [data-testid="stPopover"] button {{ background: var(--surface);
         border: 1px solid var(--line); border-radius: 6px; padding: 4px 12px;
         box-shadow: none; }}
[class*="st-key-assume"] [data-testid="stPopover"] button p {{ font-size: 13.5px;
         color: var(--ink2); white-space: nowrap; }}
[class*="st-key-assume"] [data-testid="stPopover"] button:hover {{ border-color: #cfc8b9; }}

/* Compact file uploader in the sidebar (no "200MB per file" dropzone text) */
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {{ padding: 6px;
         background: transparent; border: 1px dashed var(--line); }}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] {{ display: none; }}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {{ width: 100%; }}

/* Expanders, tables, captions, buttons */
[data-testid="stExpander"] details {{ border-radius: 10px; background: transparent;
         border-color: var(--line); }}
[data-testid="stExpander"] summary p {{ font-weight: 500; color: var(--ink2); }}
[data-testid="stCaptionContainer"] p {{ color: var(--muted); font-size: 12px; }}
[data-testid="stDownloadButton"] button, [data-testid="stBaseButton-secondary"] {{
         font-weight: 500; }}

/* Typography components */
.hp-kicker {{ font-size: 14px; font-weight: 600; color: var(--accent); margin-bottom: 4px; }}
.hp-dek {{ color: var(--ink2); font-size: 17px; line-height: 1.5; margin: 8px 0 0;
         max-width: 860px; }}
.hp-meta {{ display: flex; justify-content: flex-end; gap: 8px; align-items: center;
         flex-wrap: wrap; }}
.hp-chip {{ display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 500;
         padding: 3px 10px 3px 8px; border-radius: 6px; border: 1px solid var(--line);
         background: var(--surface); color: var(--ink2); white-space: nowrap; }}
.hp-dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}
.hp-title {{ font-family: var(--serif); font-size: 21px; font-weight: 600; color: var(--ink);
         letter-spacing: -0.005em; line-height: 1.3; margin: 0; }}
.hp-title-sub {{ font-size: 13.5px; color: var(--muted); margin: 3px 0 8px; }}
.hp-source {{ font-size: 12.5px; color: var(--muted); line-height: 1.5; margin: 2px 0 0; }}
.hp-source b {{ color: var(--ink2); font-weight: 600; }}
.hp-rule {{ border: 0; border-top: 1px solid var(--line); margin: 30px 0 26px; }}
.hp-foot {{ font-size: 12.5px; color: var(--muted); line-height: 1.6; }}
.hp-footer {{ border-top: 1px solid var(--line); margin-top: 48px; padding-top: 14px;
         display: flex; justify-content: space-between; gap: 24px; flex-wrap: wrap;
         font-size: 12.5px; color: var(--muted); }}

/* Quote hero */
.hp-quote-label {{ font-size: 14px; font-weight: 600; color: var(--ink2); }}
.hp-quote {{ display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; margin-top: 4px; }}
.hp-quote-value {{ font-size: 50px; font-weight: 600; letter-spacing: -0.02em; color: var(--ink);
         line-height: 1.05; white-space: nowrap; }}
.hp-quote-unit {{ font-size: 16px; color: var(--muted); font-weight: 500; white-space: nowrap; }}
.hp-quote-change {{ font-size: 19px; font-weight: 600; white-space: nowrap; }}
.hp-quote-sub {{ font-size: 13.5px; color: var(--muted); margin-top: 6px; }}

/* Stat strip: one row split by hairlines */
.hp-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
         border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);
         margin: 22px 0 6px; overflow: hidden; }}
.hp-stat {{ padding: 14px 18px 13px; border-left: 1px solid var(--line); margin-left: -1px; }}
.hp-stat-k {{ font-size: 11px; font-weight: 600; letter-spacing: .07em; color: var(--muted);
         text-transform: uppercase; white-space: nowrap; overflow: hidden;
         text-overflow: ellipsis; }}
.hp-stat-v {{ font-size: 23px; font-weight: 600; color: var(--ink); letter-spacing: -0.015em;
         margin-top: 3px; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.hp-stat-d {{ font-size: 13px; font-weight: 500; margin-top: 1px; }}

/* Key-value table */
.hp-kv {{ width: 100%; border-collapse: collapse; font-size: 14.5px; border: 0 !important;
         font-variant-numeric: tabular-nums; margin: 0; }}
.hp-kv tr, .hp-kv td {{ border: 0 !important; background: transparent !important; }}
.hp-kv td {{ padding: 9px 0 !important; border-bottom: 1px solid var(--line) !important; }}
.hp-kv td:first-child {{ color: var(--ink2); white-space: nowrap; }}
.hp-kv td:last-child {{ text-align: right; color: var(--ink); font-weight: 600;
         white-space: nowrap; padding-left: 16px !important; }}

.hp-table, .hp-table tr, .hp-table th, .hp-table td {{ border-left: 0 !important;
         border-right: 0 !important; border-top: 0 !important; background: transparent; }}
.hp-table {{ border: 0 !important; }}

/* Legacy insight card (pages not yet migrated) */
/* Vertical dividers between side-by-side columns: columns stack on phones, so hide them. */
.hp-vrule {{ border-left: 1px solid var(--line); width: 1px; margin: 0 auto; }}
@media (max-width: 640px) {{ .hp-vrule {{ display: none; }} }}
.hp-signals {{ display: flex; flex-direction: column; }}
.hp-signal {{ display: grid; grid-template-columns: 14px 1fr; gap: 8px; padding: 10px 0;
  border-bottom: 1px solid var(--line); }}
.hp-signal:last-child {{ border-bottom: none; }}
.hp-signal-k {{ font-weight: 600; font-size: 14px; color: var(--ink); }}
.hp-signal-v {{ font-weight: 500; color: var(--ink2); font-variant-numeric: tabular-nums;
  margin-left: 4px; white-space: nowrap; }}
.hp-signal-d {{ font-size: 13.5px; color: var(--ink2); line-height: 1.45; margin-top: 1px; }}
.hp-insight {{ background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
         padding: 18px 22px; margin: 6px 0 16px; }}
.hp-insight-head {{ font-family: var(--serif); font-size: 21px; font-weight: 600;
         color: var(--ink); margin: 10px 0 4px; line-height: 1.3; }}
.hp-facts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
         gap: 6px 24px; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--line); }}
.hp-fact-k {{ font-size: 11px; color: var(--muted); text-transform: uppercase;
         letter-spacing: .06em; font-weight: 600; }}
.hp-fact-v {{ font-size: 15px; font-weight: 600; color: var(--ink);
         font-variant-numeric: tabular-nums; }}
.hp-note {{ color: var(--ink2); font-size: 13px; margin-top: 10px; }}
.hp-eyebrow {{ font-size: 11px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase;
         color: var(--accent); margin-bottom: 4px; }}
.hp-sub {{ color: var(--ink2); font-size: 15px; margin: 6px 0 2px; max-width: 760px; }}
.hp-section {{ font-family: var(--serif); font-size: 18px; font-weight: 600; color: var(--ink);
         margin: 0; }}
.hp-section-sub {{ font-size: 12.5px; color: var(--muted); margin: 3px 0 8px; }}
</style>
"""


def setup_page() -> None:
    """Call once per run from app.py: logo, global styles."""
    assets = ROOT / "assets"
    st.logo(str(assets / "logo.svg"), icon_image=str(assets / "mark.svg"), size="large")
    st.markdown(_CSS, unsafe_allow_html=True)


# --- Formatting -----------------------------------------------------------------------------
MINUS = "−⁠"  # true minus + word joiner, so "−$863k" never breaks after the sign


def usd(x: float, decimals: int = 2) -> str:
    """-11.6 -> '−$11.60' (not '$-11.60'); -0.004 -> '$0.00' (no '−$0')."""
    x = round(x, decimals) + 0.0  # + 0.0 turns -0.0 into 0.0
    return f"{MINUS if x < 0 else ''}${abs(x):,.{decimals}f}"


def usd_short(x: float) -> str:
    """Compact dollars for headlines: 1_234_567 -> '$1.23M', -869_092 -> '−$869k'."""
    a = abs(x)
    sign = MINUS if x < 0 and round(a) else ""
    if a >= 1e6:
        return f"{sign}${a / 1e6:.2f}M"
    if a >= 1e4:
        return f"{sign}${a / 1e3:,.0f}k"
    return f"{sign}${a:,.0f}"


def signed(x: float, fmt=usd) -> str:
    """Explicit sign for changes: +$1.50 / −$1.50."""
    s = fmt(x)
    return s if s.startswith(MINUS) or s.lstrip("$0.,") == "" else f"+{s}"


def delta(x: float, fmt=usd, suffix: str = "") -> str:
    """st.metric delta text. Streamlit picks the arrow from a leading ASCII '-', so use that
    (not the typographic minus) here: delta(-3.1, suffix=' this week') -> '-$3.10 this week'."""
    s = fmt(abs(x))
    return f"{'-' if round(x, 2) < 0 else '+'}{s}{suffix}"


def tone_of(x: float) -> Tone:
    return "good" if x > 0 else "bad" if x < 0 else "neutral"


def _safe(text: str) -> str:
    """Escape HTML and keep "$" from being read as LaTeX by Streamlit's markdown."""
    return html.escape(text).replace("$", "&#36;")


def md(text: str) -> str:
    """Escape "$" for Streamlit widget labels (markdown), so "$5 · $300" isn't read as LaTeX."""
    return text.replace("$", r"\$")


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


# --- Data access ----------------------------------------------------------------------------
@st.cache_data(ttl=6 * 3600, show_spinner="Loading USDA hog prices…")
def _hg201(offline: bool) -> tuple[pd.DataFrame, Source, str]:
    return load_hg201(offline)


def hog_index() -> tuple[pd.DataFrame, Source, str]:
    """Lean Hog Index history (live, cached or sample) and a note on where it came from."""
    raw, source, note = _hg201(get_settings().offline)
    return lean_hog_index(raw), source, note


@st.cache_data(ttl=6 * 3600, show_spinner="Loading USDA Hogs and Pigs…")
def _nass(offline: bool) -> tuple[pd.DataFrame, str, str]:
    # The key is read here rather than passed in, so it never becomes part of a cache key.
    return nass_load(get_settings().nass_api_key.strip(), offline)


def nass_data() -> tuple[pd.DataFrame, str, str]:
    """Quarterly Hogs and Pigs data (live, cached or sample) and a note on where it came from."""
    return _nass(get_settings().offline)


@st.cache_data(ttl=6 * 3600, show_spinner="Loading USDA pork cutout…")
def _cutout(offline: bool) -> tuple[pd.DataFrame, str, str]:
    return lmr.load(lmr.CUTOUT, offline)


@st.cache_data(ttl=6 * 3600, show_spinner="Loading USDA WASDE…")
def _wasde(offline: bool) -> tuple[pd.DataFrame, str, str]:
    return wasde.load(offline)


def wasde_data() -> tuple[pd.DataFrame, str, str]:
    """USDA WASDE quarterly pork production and barrow/gilt price forecasts."""
    return _wasde(get_settings().offline)


def wasde_now() -> dict | None:
    """USDA's outlook for the next two quarters (see hogmarket.wasde_outlook)."""
    from hogproj.hogmarket import wasde_outlook

    return wasde_outlook(wasde_data()[0], pd.Timestamp(date.today()))


def pork_cutout() -> tuple[pd.DataFrame, str, str]:
    """Daily pork cutout and primal values (LM_PK602) and where they came from."""
    return _cutout(get_settings().offline)


def hog_market() -> pd.DataFrame:
    """Daily index, cutout, packer spread, producer-sold head and carcass weight."""
    from hogproj.hogmarket import daily

    raw, _, _ = _hg201(get_settings().offline)
    cut, _, _ = pork_cutout()
    return daily(raw, lean_hog_index(raw), cut)


def signal_list(items: Sequence[tuple[str, str, str, Tone, str]]) -> None:
    """Market signals: (name, value, one-sentence read, tone, rule shown on hover)."""
    rows = "".join(
        f'<div class="hp-signal" title="Rule: {_safe(rule)}">'
        f'<span class="hp-dot" style="background:{_TONE[t][0]};margin-top:7px"></span>'
        f'<div><div class="hp-signal-k">{_safe(k)} <span class="hp-signal-v">{_safe(v)}</span>'
        f'</div><div class="hp-signal-d">{_safe(d)}</div></div></div>'
        for k, v, d, t, rule in items
    )
    _html(f'<div class="hp-signals">{rows}</div>')


@st.cache_data(ttl=6 * 3600, show_spinner="Loading USDA weaned pig prices…")
def _feeder(offline: bool) -> tuple[pd.DataFrame, str, str]:
    return feeder_load(offline)


def weaned_pigs() -> tuple[pd.DataFrame, str, str]:
    """Weekly USDA early weaned pig prices (live, cached or sample) and where they came from."""
    return _feeder(get_settings().offline)


@st.cache_data(ttl=6 * 3600, show_spinner="Loading USDA corn prices…")
def _corn(offline: bool) -> tuple[pd.DataFrame, str, str]:
    return load_corn(get_settings().nass_api_key.strip(), offline)


def iowa_corn() -> tuple[pd.DataFrame, str, str]:
    """Monthly Iowa corn price received (NASS) and where it came from."""
    return _corn(get_settings().offline)


@st.cache_data(ttl=6 * 3600, show_spinner="Loading USDA feed prices…")
def _feed(offline: bool) -> tuple[pd.DataFrame, str, str]:
    return feed.load(offline)


def feed_prices() -> tuple[pd.DataFrame, str, str]:
    """Iowa cash corn, soybean meal, DDGS and CBOT corn (long format) and where they came from."""
    return _feed(get_settings().offline)


_FEED_FALLBACK = {
    "corn_cash_iowa": CostInputs().corn_usd_per_bu,
    "sbm_iowa": CostInputs().sbm_usd_per_ton,
    "ddgs_iowa": CrushInputs().ddgs_usd_per_ton,
}
FEED_LABEL = {
    "corn_cash_iowa": "Iowa average cash corn (USDA AMS 2850)",
    "sbm_iowa": "Iowa soybean meal 46.5-48% (USDA AMS 3511)",
    "ddgs_iowa": "Iowa DDGS (USDA AMS 3511)",
}


def feed_default(item: str) -> float:
    """Latest USDA price for a feed item, else the model default. Rounded to the input step."""
    got = feed.latest(feed_prices()[0], item)
    if got is None:
        return _FEED_FALLBACK[item]
    return round(got[0], 2) if item == "corn_cash_iowa" else float(round(got[0]))


def feed_help(item: str) -> str:
    got = feed.latest(feed_prices()[0], item)
    if got is None:
        return "No USDA price saved yet; this is the model default."
    return f"Starts at {FEED_LABEL[item]}, {got[1]:%b %d, %Y}. Use your own bid if you have one."


def corn_curve() -> tuple[dict[Contract, float], pd.Timestamp | None]:
    """CBOT corn settlements by contract from the latest Iowa grain report ($/bu)."""
    fd = feed_prices()[0]
    fut = fd[fd["item"].astype(str).str.startswith("corn_futures_")]
    if fut.empty:
        return {}, None
    day = pd.Timestamp(str(fut["date"].max()))
    latest = fut[pd.to_datetime(fut["date"]) == day]
    curve = {}
    for item, v in zip(latest["item"], latest["value"], strict=True):
        _, _, y, m = str(item).split("_")
        curve[(int(y), int(m))] = float(v)
    return curve, day


def latest_weaned_pig() -> float:
    pigs, _, _ = weaned_pigs()
    return round(float(pigs["cash_usd_per_head"].iloc[-1]), 2)


def latest_hog_index() -> float:
    idx, _, _ = hog_index()
    return round(float(idx["lean_hog_index_usd_per_cwt_carcass"].iloc[-1]), 2)


# Widget key -> (model field, scale). Percent inputs are stored as % and the model wants 0-1.
HERD_KEYS = {
    "herd_sows": ("sows_start", 1),
    "herd_change_week": ("change_week", 1),
    "herd_weeks": ("weeks", 1),
    "herd_litters": ("litters_per_sow_yr", 1),
    "herd_born": ("born_alive_per_litter", 1),
    "herd_pw_mort": ("prewean_mortality", 0.01),
    "herd_w2f_mort": ("wean_to_market_mortality", 0.01),
    "herd_gest": ("gestation_days", 1),
    "herd_lact": ("lactation_days", 1),
    "herd_w2f": ("wean_to_market_days", 1),
    "herd_wt": ("weight_lb_live_market", 1),
    "herd_yield": ("carcass_yield", 0.01),
}
COST_KEYS = {
    "cost_corn": "corn_usd_per_bu",
    "cost_sbm": "sbm_usd_per_ton",
    "cost_hog": "lean_hog_usd_per_cwt_carcass",
    "cost_corn_bu": "corn_bu_per_head",
    "cost_sbm_lb": "sbm_lb_per_head",
    "cost_other_feed": "other_feed_usd_per_head",
    "cost_nonfeed": "nonfeed_usd_per_head",
    "cost_death": "death_loss_usd_per_head",
    "cost_manure": "manure_credit_usd_per_head",
}
# Wean-to-finish widget key -> (CrushInputs field, scale). Corn and SBM prices are shared
# with Costs & returns (cost_corn, cost_sbm) so every page uses the same feed prices.
W2F_KEYS = {
    "w2f_pig": ("pig_usd_per_head", 1),
    "w2f_adder": ("adder_usd_per_head", 1),
    "w2f_days": ("days_on_feed", 1),
    "w2f_wt": ("weight_lb_live", 1),
    "w2f_yield": ("carcass_yield", 0.01),
    "w2f_basis": ("basis_usd_per_cwt", 1),
    "cost_corn": ("corn_usd_per_bu", 1),
    "cost_sbm": ("sbm_usd_per_ton", 1),
    "w2f_ddgs": ("ddgs_usd_per_ton", 1),
    "w2f_corn_lb": ("corn_lb", 1),
    "w2f_sbm_lb": ("sbm_lb", 1),
    "w2f_ddgs_lb": ("ddgs_lb", 1),
    "w2f_other_lb": ("other_feed_lb", 1),
    "w2f_other_price": ("other_feed_usd_per_lb", 1),
    "w2f_health": ("health_usd", 1),
    "w2f_barn": ("facilities_labor_usd", 1),
    "w2f_mort": ("mortality_usd", 1),
    "w2f_overhead": ("overhead_usd", 1),
    "w2f_freight": ("freight_usd", 1),
    "w2f_interest": ("interest_usd", 1),
    "w2f_other": ("other_usd", 1),
    "w2f_principal": ("principal_usd", 1),
    "w2f_term_int": ("term_interest_usd", 1),
}
SAVED_PREFIXES = ("herd_", "cost_", "scn_", "risk_", "mkt_", "w2f_", "sow_")
DERIVED_KEYS = ("herd_inputs", "cost_inputs")


def herd_from_state() -> HerdInputs:
    """HerdInputs from the saved widget values (defaults for anything not set yet)."""
    ss = st.session_state
    upd: dict[str, float | int] = {}
    for key, (field, scale) in HERD_KEYS.items():
        if key in ss:
            v = ss[key] * scale
            upd[field] = int(v) if field in ("change_week", "weeks") else float(v)
    herd = HerdInputs().model_copy(update=upd)
    change = float(ss.get("herd_sows_change", 0) or 0)
    return herd.model_copy(update={"sows_target": max(0.0, herd.sows_start + change)})


def cost_from_state(herd: HerdInputs) -> CostInputs:
    """CostInputs from the saved widget values; hog price defaults to the latest index."""
    ss = st.session_state
    upd: dict[str, float] = {"lean_hog_usd_per_cwt_carcass": latest_hog_index(),
                             "corn_usd_per_bu": feed_default("corn_cash_iowa"),
                             "sbm_usd_per_ton": feed_default("sbm_iowa")}  # fmt: skip
    upd.update({field: float(ss[key]) for key, field in COST_KEYS.items() if key in ss})
    upd.update(weight_lb_live_market=herd.weight_lb_live_market, carcass_yield=herd.carcass_yield)
    return CostInputs().model_copy(update=upd)


def crush_from_state() -> CrushInputs:
    """Wean-to-finish inputs from saved widget values; the pig price defaults to USDA's latest
    and corn/SBM to the shared Costs & returns prices."""
    ss = st.session_state
    upd: dict[str, float | int] = {"pig_usd_per_head": latest_weaned_pig(),
                                   "corn_usd_per_bu": feed_default("corn_cash_iowa"),
                                   "sbm_usd_per_ton": feed_default("sbm_iowa"),
                                   "ddgs_usd_per_ton": feed_default("ddgs_iowa")}  # fmt: skip
    for key, (field, scale) in W2F_KEYS.items():
        if key in ss and ss[key] is not None:
            v = ss[key] * scale
            upd[field] = int(v) if field == "days_on_feed" else float(v)
    return CrushInputs().model_copy(update=upd)


SOW_KEYS = {
    "sow_adder": "adder_usd_per_head",
    "sow_corn_lb": "corn_lb_per_sow_yr",
    "sow_sbm_lb": "sbm_lb_per_sow_yr",
    "sow_other": "other_feed_usd_per_sow_yr",
    "sow_nonfeed": "nonfeed_usd_per_sow_yr",
    "cost_corn": "corn_usd_per_bu",
    "cost_sbm": "sbm_usd_per_ton",
}


def sow_from_state() -> SowInputs:
    """Sow farm inputs: productivity from Herd flow, feed prices shared with every page."""
    ss = st.session_state
    h = herd_from_state()
    upd: dict[str, float] = {
        "weaned_per_sow_yr": h.litters_per_sow_yr * h.born_alive_per_litter
        * (1 - h.prewean_mortality),
        "corn_usd_per_bu": feed_default("corn_cash_iowa"),
        "sbm_usd_per_ton": feed_default("sbm_iowa"),
    }  # fmt: skip
    upd.update({f: float(ss[k]) for k, f in SOW_KEYS.items() if ss.get(k) is not None})
    return SowInputs().model_copy(update=upd)


def lh_key(k: Contract) -> str:
    """Widget key for a lean hog contract price, e.g. w2f_lh_2027_04."""
    return f"w2f_lh_{k[0]}_{k[1]:02d}"


@dataclass
class CrushBook:
    """Everything the wean-to-finish pages share: inputs, contract prices and placements."""

    c: CrushInputs
    contracts: list[Contract]
    model: dict[Contract, float]  # seasonal estimate per contract
    futures: dict[Contract, float]  # the user's price where entered, else the estimate
    user_set: list[Contract]  # contracts the user has priced
    this_contract: Contract  # the contract a pig placed today sells into
    hog: float  # its price
    index_now: float
    rows: pd.DataFrame  # crush.placements for every USDA week
    corn_mode: str = "Today's cash"  # or "Futures curve"
    corn_cash: float = 0.0  # the corn input (cash)
    corn_basis: float = 0.0  # cash − nearby CBOT futures, when the curve is used


def crush_book() -> CrushBook:
    ss = st.session_state
    c = crush_from_state()
    idx, _, _ = hog_index()
    pigs, _, _ = weaned_pigs()
    corn, _, _ = iowa_corn()
    today = date.today()
    index_now = float(idx["lean_hog_index_usd_per_cwt_carcass"].iloc[-1])
    last_index = date.fromisoformat(str(idx["index_date"].iloc[-1])[:10])
    contracts = contracts_needed(pigs.tail(40), c, today, last_index)
    model = model_contract_prices(contracts, today, index_now, seasonal_factors(idx))
    futures = {
        k: float(model[k] if ss.get(lh_key(k)) is None else ss[lh_key(k)]) for k in contracts
    }
    user_set = [k for k in contracts if futures[k] != model[k]]
    this = contract_for(today + timedelta(days=c.days_on_feed))
    # Corn for pigs on feed: the CBOT curve over their months on feed plus your basis (the
    # workbook's approach), or today's cash for every month.
    curve, _ = corn_curve()
    mode = ss.get("w2f_corn_mode") or "Futures curve"
    cash, basis = c.corn_usd_per_bu, 0.0
    if mode == "Futures curve" and curve:
        nearby = curve[min(k for k in curve if k >= corn_contract_for(today.year, today.month))]
        basis = cash - nearby
        start = pd.Timestamp(today)
        c = c.model_copy(update={"corn_usd_per_bu": forward_corn(
            start, start + pd.Timedelta(days=c.days_on_feed), curve, basis)})  # fmt: skip
        rows = placements(pigs, idx, c, futures, corn, corn_curve=curve, corn_basis=basis)
    else:
        mode = "Today's cash"
        rows = placements(pigs, idx, c, futures, corn)
    return CrushBook(c=c, contracts=contracts, model=model, futures=futures, user_set=user_set,
                     this_contract=this, hog=futures.get(this, index_now), index_now=index_now,
                     rows=rows, corn_mode=mode, corn_cash=cash, corn_basis=basis)  # fmt: skip


def current_plan() -> Plan:
    """The plan from every input the user has set on any page (defaults where unset)."""
    herd = herd_from_state()
    seasonal = (st.session_state.get("cost_price_path") or "Seasonal") != "Flat"
    return Plan(herd=herd, cost=cost_from_state(herd), seasonal=seasonal)


def uses_benchmarks() -> bool:
    """True while herd and cost inputs are still the built-in benchmarks (hog price aside)."""
    p = current_plan()
    default = CostInputs(
        lean_hog_usd_per_cwt_carcass=p.cost.lean_hog_usd_per_cwt_carcass,
        corn_usd_per_bu=feed_default("corn_cash_iowa"),
        sbm_usd_per_ton=feed_default("sbm_iowa"),
        weight_lb_live_market=p.herd.weight_lb_live_market,
        carcass_yield=p.herd.carcass_yield,
    )
    return p.herd == HerdInputs() and p.cost == default


def saved_inputs() -> dict[str, object]:
    """Inputs worth saving to a file: plain widget values only."""
    ss = st.session_state
    return {
        str(k): ss[k]
        for k in ss
        if str(k).startswith(SAVED_PREFIXES)
        and str(k) not in DERIVED_KEYS
        and isinstance(ss[k], (int, float, str, bool))
    }


# --- Components -----------------------------------------------------------------------------
def chip(label: str, tone: Tone = "neutral", title: str = "") -> str:
    dot, _, _ = _TONE[tone]
    t = f' title="{_safe(title)}"' if title else ""
    return (
        f'<span class="hp-chip"{t}><span class="hp-dot" style="background:{dot}"></span>'
        f"{_safe(label)}</span>"
    )


def data_chip() -> str:
    """'Live USDA data · index Oct 15' or 'Saved data through …', for page headers."""
    idx, source, note = hog_index()
    last = pd.Timestamp(idx["index_date"].iloc[-1])
    if source == "live":
        return chip(f"Live USDA data · index {last:%b %d}", "good", note)
    return chip(f"Saved data through {last:%b %d, %Y}", "caution", note)


def masthead(
    title: str, dek: str = "", kicker: str = "", meta: Sequence[str] = ()
) -> DeltaGenerator:
    """Editorial page head: kicker, serif headline (ideally the finding), dek, status on the
    right. Returns the right-hand column for an action button."""
    left, right = st.columns([3.2, 1], vertical_alignment="top")
    with left:
        if kicker:
            _html(f'<div class="hp-kicker">{_safe(kicker)}</div>')
        st.title(title.replace("$", r"\$"))  # "$...$" would render as LaTeX math
        if dek:
            _html(f'<div class="hp-dek">{_safe(dek)}</div>')
    with right:
        _html(f'<div class="hp-meta" style="margin-top:2px">{"".join([data_chip(), *meta])}</div>')
    _html('<div style="height:18px"></div>')
    return right


def page_header(
    title: str, subtitle: str = "", eyebrow: str = "", meta: Sequence[str] = ()
) -> DeltaGenerator:
    """Older name for `masthead`."""
    return masthead(title, subtitle, eyebrow, meta)


def quote(label: str, value: str, unit: str = "", change: str = "", tone: Tone = "neutral",
          sub: str = "") -> None:  # fmt: skip
    """Market-quote style hero number: label, big value + unit, coloured change, context line."""
    ch = (
        f'<span class="hp-quote-change" style="color:{TONE_TEXT[tone]}">{_safe(change)}</span>'
        if change
        else ""
    )
    _html(
        f'<div class="hp-quote-label">{_safe(label)}</div>'
        f'<div class="hp-quote"><span class="hp-quote-value">{_safe(value)}</span>'
        f'<span class="hp-quote-unit">{_safe(unit)}</span>{ch}</div>'
        + (f'<div class="hp-quote-sub">{_safe(sub)}</div>' if sub else "")
    )


def stat_strip(items: Sequence[tuple[str, str, str, Tone]]) -> None:
    """One row of figures split by hairlines: (label, value, note, tone of the note)."""
    cells = "".join(
        f'<div class="hp-stat"><div class="hp-stat-k">{_safe(k)}</div>'
        f'<div class="hp-stat-v">{_safe(v)}</div>'
        f'<div class="hp-stat-d" style="color:{TONE_TEXT[t]}">{_safe(d) or "&nbsp;"}</div></div>'
        for k, v, d, t in items
    )
    _html(f'<div class="hp-strip">{cells}</div>')


def chart_title(finding: str, sub: str = "") -> None:
    """Serif headline that states what the chart shows, with units/scope underneath."""
    _html(
        f'<div class="hp-title">{_safe(finding)}</div>'
        + (f'<div class="hp-title-sub">{_safe(sub)}</div>' if sub else "")
    )


def source_note(source: str, note: str = "") -> None:
    _html(
        f'<div class="hp-source"><b>Source:</b> {_safe(source)}'
        + (f" &nbsp;·&nbsp; <b>Note:</b> {_safe(note)}" if note else "")
        + "</div>"
    )


def rule() -> None:
    _html('<hr class="hp-rule">')


def kv_table(rows: Sequence[tuple[str, str]]) -> None:
    body = "".join(f"<tr><td>{_safe(k)}</td><td>{_safe(v)}</td></tr>" for k, v in rows)
    _html(f'<table class="hp-kv">{body}</table>')


def insight(
    tone: Tone,
    status: str,
    headline: str,
    facts: Sequence[tuple[str, str]] = (),
    note: str = "",
) -> None:
    """Takeaway card: status chip, one-sentence serif headline, a row of key facts."""
    fact_html = "".join(
        f'<div><div class="hp-fact-k">{_safe(k)}</div><div class="hp-fact-v">{_safe(v)}</div></div>'
        for k, v in facts
    )
    _html(
        f"""<div class="hp-insight">{chip(status, tone)}
        <div class="hp-insight-head">{_safe(headline)}</div>
        {f'<div class="hp-facts">{fact_html}</div>' if facts else ""}
        {f'<div class="hp-note">{_safe(note)}</div>' if note else ""}</div>"""
    )


def verdict(kind: Tone, headline: str, detail: str = "") -> None:
    """Older takeaway API; kept for pages not yet moved to `insight`."""
    insight(kind, {"good": "On track", "bad": "Attention", "neutral": "Note",
                   "caution": "Watch"}[kind], headline, note=detail)  # fmt: skip


def card(key: str) -> DeltaGenerator:
    """A white panel. `key` must be unique on the page."""
    return st.container(key=f"card_{key}")


def hero(key: str = "main") -> DeltaGenerator:
    """The page's one dominant panel."""
    return st.container(key=f"hero_{key}")


def section(title: str, caption: str = "") -> None:
    chart_title(title, caption)


def assumption_bar(key: str) -> DeltaGenerator:
    """Container whose popovers render as chips (see CSS `st-key-assume`)."""
    return st.container(key=f"assume_{key}", horizontal=True, gap="small")


def chart(fig: go.Figure, height: int = 300, on: str = SURFACE) -> None:
    """Render a Plotly figure in the house style (no Streamlit theme, no toolbar).

    `on` is the background the chart sits on: SURFACE inside panels, PAGE when unboxed.
    """
    fig.update_layout(template="hogproj", height=height, paper_bgcolor=on, plot_bgcolor=on)

    def money_ticks(ax) -> None:  # noqa: ANN001 - plotly axis object
        # d3 formats negatives with a true minus ("−$10"); a "$" tickprefix would give "$-10".
        if ax.tickprefix == "$":
            ax.update(tickprefix=None, tickformat=ax.tickformat or "$,.0f")

    fig.for_each_xaxis(money_ticks)
    fig.for_each_yaxis(money_ticks)
    st.plotly_chart(
        fig,
        theme=None,
        width="stretch",
        config={"displayModeBar": False, "displaylogo": False, "responsive": True},
    )


# --- Chart annotations ----------------------------------------------------------------------
def end_tag(fig: go.Figure, x: object, y: float, text: str, color: str) -> None:
    """Solid value tag just right of a series' last point (ERS / market-terminal style)."""
    fig.add_annotation(
        x=x,
        y=y,
        text=f"<b>{text}</b>",
        showarrow=False,
        xanchor="left",
        xshift=8,
        font={"size": 11, "color": "white", "family": SANS},
        bgcolor=color,
        borderpad=3,
    )


def ref_line(
    fig: go.Figure, y: float, label: str, color: str = REFERENCE, side: str = "right"
) -> None:
    """Dotted reference line (breakeven, floor) with its label at one edge."""
    fig.add_hline(y=y, line={"color": color, "width": 1.25, "dash": "dot"})
    fig.add_annotation(
        x=1 if side == "right" else 0,
        xref="paper",
        y=y,
        text=label,
        showarrow=False,
        xanchor=side,
        yanchor="bottom",
        font={"size": 11, "color": color, "family": SANS},
    )


def projection_band(fig: go.Figure, x0: object, x1: object, label: str = "PROJECTION") -> None:
    """Shade the forecast window and label it, so actuals and projections never blur."""
    fig.add_vrect(x0=x0, x1=x1, fillcolor="#f4f1ea", opacity=1, line_width=0, layer="below")
    fig.add_annotation(
        x=x0,
        y=1,
        yref="paper",
        text=label,
        showarrow=False,
        xanchor="left",
        yanchor="top",
        xshift=8,
        yshift=-4,
        font={"size": 10, "color": MUTED, "family": SANS},
    )


# --- Misc -----------------------------------------------------------------------------------
def table(
    header: Sequence[str], rows: Sequence[Sequence[str]], emphasis_col: int | None = None
) -> None:
    """A clean comparison table: label column left, figures right-aligned in tabular digits.

    All cells are escaped. `emphasis_col` (0-based, excluding the label column) is shaded.
    """

    def cell(text: str, i: int, head: bool = False) -> str:
        tag = "th" if head else "td"
        align = "left;white-space:nowrap" if i == 0 else "right"
        shade = "background:#faf8f3;" if emphasis_col is not None and i == emphasis_col + 1 else ""
        weight = "font-weight:600;" if head else (f"color:{INK_2};" if i == 0 else "")
        return (
            f'<{tag} style="text-align:{align};{shade}{weight}padding:9px 14px;'
            f'border-bottom:1px solid {LINE}">{_safe(text)}</{tag}>'
        )

    head_html = "".join(cell(h, i, True) for i, h in enumerate(header))
    body_html = "".join(
        "<tr>" + "".join(cell(c, i) for i, c in enumerate(r)) + "</tr>" for r in rows
    )
    _html(
        '<div style="overflow-x:auto"><table class="hp-table" style="width:100%;'
        "border-collapse:collapse;"
        f"font-size:13.5px;font-variant-numeric:tabular-nums;color:{INK};"
        f'border:none"><thead style="color:{MUTED};font-size:11px;text-transform:uppercase;'
        f'letter-spacing:.06em"><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table></div>'
    )


def page_footer() -> None:
    """Who prepared it, when, and from what: the credibility line every page ends with."""
    who = get_settings().prepared_by.strip()
    left = (f"Prepared by {_safe(who)} · " if who else "Prepared ") + f"{date.today():%B %d, %Y}"
    _html(
        f'<div class="hp-footer"><span>{left}</span>'
        "<span>Data: USDA AMS (LMR, feeder pig, Iowa grain &amp; feedstuffs) · USDA NASS · "
        "Iowa State University Estimated Livestock Returns · "
        "Projections, not financial advice</span></div>"
    )


def data_status() -> list[tuple[str, str, str]]:
    """(source, latest date, live/saved) for every dataset the app reads."""
    out: list[tuple[str, str, str]] = []

    def add(name: str, when: object, source: str) -> None:
        ts = pd.Timestamp(str(when))
        out.append((name, f"{ts:%b %d, %Y}", "live" if source == "live" else "saved"))

    idx, s1, _ = hog_index()
    add("Lean Hog Index", idx["index_date"].max(), s1)
    cut, s2, _ = pork_cutout()
    add("Pork cutout", cut["date"].max(), s2)
    pigs, s3, _ = weaned_pigs()
    add("Weaned pigs", pigs["week_ending"].max(), s3)
    fd, s4, _ = feed_prices()
    for item, label in (("corn_cash_iowa", "Iowa cash corn"), ("sbm_iowa", "Soybean meal")):
        got = feed.latest(fd, item)
        if got:
            add(label, got[1], s4)
    nd, s5, _ = nass_data()
    if not nd.empty:
        inv = nd[(nd["series"] == "all_hogs") & (nd["kind"] == "actual")]
        add("Hogs and Pigs", inv["period_start"].max(), s5)
    return out


def footer_note(text: str) -> None:
    _html(f'<div class="hp-foot">{_safe(text)}</div>')


def as_of() -> str:
    return f"{date.today():%b %d, %Y}"


def asset(name: str) -> Path:
    return ROOT / "assets" / name


def data_notice(source: Source, note: str) -> None:
    """Older API: data status now lives in the page header chip. Warn only when not live."""
    if source != "live":
        st.caption(note)
