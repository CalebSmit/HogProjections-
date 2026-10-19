"""Design system + shared page helpers for views/. UI layer: may import streamlit and data.

Tokens here mirror .streamlit/config.toml and docs/DESIGN.md. Pages should build from these
components (page_header, insight, card, section, chart, kpi formatting) rather than styling
things one by one; that consistency is most of what makes the app look finished.
"""

import html
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Literal

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from hogproj.config import ROOT, get_settings
from hogproj.data.ams import Source, load_hg201
from hogproj.finance import CostInputs
from hogproj.herd import HerdInputs
from hogproj.markets import lean_hog_index
from hogproj.outlook import Plan

# --- Tokens ---------------------------------------------------------------------------------
FONT = "Inter, 'Segoe UI Variable Text', 'Segoe UI', system-ui, -apple-system, Arial, sans-serif"
INK = "#16181d"  # primary text
INK_2 = "#4d535e"  # secondary text
MUTED = "#8b909a"  # labels, axes
LINE = "#e3e3de"  # hairline borders
GRID = "#efefeb"  # chart gridlines
SURFACE = "#ffffff"  # cards
PAGE = "#f6f6f4"  # app background
ACCENT = "#1f4e8c"  # brand / interactive
POS = "#178a6a"  # profit (validated vs NEG for colour-vision deficiency, ΔE 8.1)
NEG = "#c8453a"  # loss
CAUTION = "#b7791f"
REFERENCE = "#5b616e"  # breakeven / reference lines
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # categorical slots 1-3 (validated all-pairs)
BASELINE_SERIES = "#3a3f47"  # "current plan" when compared with scenarios
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#1c5cab"]
DIVERGING = [[0.0, NEG], [0.5, "#f1f0ec"], [1.0, POS]]  # loss <-> neutral <-> profit

# Back-compat aliases used by older page code.
GOOD, BAD, NEUTRAL = POS, NEG, MUTED

Tone = Literal["good", "bad", "neutral", "caution"]
_TONE = {
    "good": (POS, "#e7f4ef", "#11704f"),
    "bad": (NEG, "#fbecea", "#a8352b"),
    "neutral": (MUTED, "#f1f1ee", INK_2),
    "caution": (CAUTION, "#fbf3e4", "#8a5a12"),
}

pio.templates["hogproj"] = go.layout.Template(
    layout=go.Layout(
        font={"family": FONT, "size": 12, "color": INK_2},
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        separators=".,",
        colorway=SERIES,
        margin={"l": 4, "r": 8, "t": 8, "b": 4},
        hovermode="x unified",
        hoverlabel={
            "bgcolor": SURFACE,
            "bordercolor": LINE,
            "font": {"family": FONT, "size": 12, "color": INK},
        },
        legend={
            "orientation": "h",
            "x": 0,
            "xanchor": "left",
            "y": 1.02,
            "yanchor": "bottom",
            "font": {"size": 11.5, "color": INK_2},
            "bgcolor": "rgba(0,0,0,0)",
            "itemwidth": 30,
        },
        xaxis={
            "showgrid": False,
            "zeroline": False,
            "showline": True,
            "linecolor": "#d6d6d0",
            "ticks": "outside",
            "tickcolor": "#d6d6d0",
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
        bargap=0.28,
    )
)

_CSS = f"""
<style>
:root {{ --hp-ink:{INK}; --hp-ink2:{INK_2}; --hp-muted:{MUTED}; --hp-line:{LINE};
         --hp-surface:{SURFACE}; --hp-accent:{ACCENT}; --hp-pos:{POS}; --hp-neg:{NEG};
         --hp-shadow: 0 1px 2px rgba(16,24,40,.04), 0 1px 1px rgba(16,24,40,.02); }}
html, body, .stApp {{ -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
         font-feature-settings: "cv11", "ss01", "ss03"; }}
[data-testid="stDecoration"] {{ display: none; }}
header[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"] {{ padding-top: 2.4rem; padding-bottom: 5rem;
         max-width: 1360px; }}
h1 {{ letter-spacing: -0.022em; line-height: 1.15 !important; padding: 0 !important; }}
h2, h3, h4 {{ letter-spacing: -0.012em; }}
[data-testid="stHeadingWithActionElements"] [data-testid="stHeaderActionElements"] {{
         display: none; }}
p, li {{ line-height: 1.55; }}

/* KPI cards (st.metric) */
[data-testid="stMetric"] {{ background: var(--hp-surface); border: 1px solid var(--hp-line);
         border-radius: 12px; padding: 16px 18px 15px; box-shadow: var(--hp-shadow);
         height: 100%; }}
[data-testid="stMetricLabel"] p {{ font-size: 12.5px !important; font-weight: 500;
         color: var(--hp-muted); letter-spacing: .005em; }}
[data-testid="stMetricValue"] {{ letter-spacing: -0.025em; color: var(--hp-ink);
         line-height: 1.2; padding-top: 2px; }}
[data-testid="stMetricDelta"] {{ font-size: 12px; font-weight: 500; }}
[data-testid="stMetricDelta"] > div {{ font-size: 12px; }}

/* Cards: st.container(key="card_*") */
[class*="st-key-card_"] {{ background: var(--hp-surface); border: 1px solid var(--hp-line);
         border-radius: 12px; padding: 18px 20px 14px; box-shadow: var(--hp-shadow); }}
[class*="st-key-card_"] [data-testid="stPlotlyChart"] {{ margin-top: -2px; }}

/* Sidebar */
[data-testid="stSidebarHeader"] {{ padding-top: 1.4rem; padding-bottom: .6rem; }}
[data-testid="stNavSectionHeader"] {{ text-transform: uppercase; font-size: 10.5px !important;
         letter-spacing: .08em; color: var(--hp-muted) !important; font-weight: 600;
         margin-top: .9rem; }}
[data-testid="stSidebarNavLink"] {{ border-radius: 8px; padding-top: .3rem;
         padding-bottom: .3rem; }}
[data-testid="stSidebarNavLink"] span {{ font-size: 13.5px; }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: #eef2f8; }}
[data-testid="stSidebarNavLink"][aria-current="page"] span {{ color: var(--hp-accent);
         font-weight: 600; }}
[data-testid="stSidebarUserContent"] h2 {{ font-size: 11px !important; text-transform: uppercase;
         letter-spacing: .08em; color: var(--hp-muted); font-weight: 600;
         padding-top: .4rem !important; }}
[data-testid="stSidebarUserContent"] label p {{ font-size: 13px; color: var(--hp-ink2); }}

/* Expanders, inputs, tables */
[data-testid="stExpander"] details {{ border-radius: 12px; background: var(--hp-surface);
         border-color: var(--hp-line); }}
[data-testid="stExpander"] summary p {{ font-weight: 500; }}
[data-testid="stDataFrame"] {{ border-radius: 10px; }}
[data-testid="stCaptionContainer"] p {{ color: var(--hp-muted); font-size: 12.5px; }}
[data-testid="stDownloadButton"] button, [data-testid="stBaseButton-secondary"] {{
         font-weight: 500; box-shadow: var(--hp-shadow); }}

/* Custom components */
.hp-eyebrow {{ font-size: 11px; font-weight: 600; letter-spacing: .09em; text-transform: uppercase;
         color: var(--hp-muted); margin-bottom: 2px; }}
.hp-sub {{ color: var(--hp-ink2); font-size: 14px; margin: 4px 0 2px; max-width: 760px; }}
.hp-meta {{ display: flex; justify-content: flex-end; gap: 8px; align-items: center;
         flex-wrap: wrap; }}
.hp-chip {{ display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 500;
         padding: 3px 10px 3px 8px; border-radius: 999px; border: 1px solid var(--hp-line);
         background: var(--hp-surface); color: var(--hp-ink2); white-space: nowrap; }}
.hp-dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}
.hp-insight {{ background: var(--hp-surface); border: 1px solid var(--hp-line); border-radius: 14px;
         padding: 18px 22px 18px; box-shadow: var(--hp-shadow); margin: 6px 0 16px; }}
.hp-insight-head {{ font-size: 19px; font-weight: 600; color: var(--hp-ink);
         letter-spacing: -0.015em; margin: 10px 0 4px; line-height: 1.35; }}
.hp-facts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
         gap: 6px 24px; margin-top: 12px; padding-top: 12px; border-top: 1px solid #efefeb; }}
.hp-fact-k {{ font-size: 12px; color: var(--hp-muted); }}
.hp-fact-v {{ font-size: 15px; font-weight: 600; color: var(--hp-ink); letter-spacing: -0.01em;
         font-variant-numeric: tabular-nums; }}
.hp-note {{ color: var(--hp-ink2); font-size: 13px; margin-top: 10px; }}
.hp-section {{ font-size: 14.5px; font-weight: 600; color: var(--hp-ink); letter-spacing: -0.01em;
         margin: 0; }}
.hp-section-sub {{ font-size: 12.5px; color: var(--hp-muted); margin: 2px 0 6px; }}
.hp-pos {{ color: #11704f; }} .hp-neg {{ color: #a8352b; }}
.hp-foot {{ font-size: 11.5px; color: var(--hp-muted); line-height: 1.5; }}
</style>
"""


def setup_page() -> None:
    """Call once per run from app.py: logo, global styles."""
    assets = ROOT / "assets"
    st.logo(str(assets / "logo.svg"), icon_image=str(assets / "mark.svg"), size="large")
    st.markdown(_CSS, unsafe_allow_html=True)


# --- Formatting -----------------------------------------------------------------------------
MINUS = "−"  # true minus sign: same width as "+", reads as finance typesetting


def usd(x: float, decimals: int = 2) -> str:
    """-11.6 -> '−$11.60' (not '$-11.60'); -0.004 -> '$0.00' (no '−$0')."""
    x = round(x, decimals) + 0.0  # + 0.0 turns -0.0 into 0.0
    return f"{MINUS if x < 0 else ''}${abs(x):,.{decimals}f}"


def usd_short(x: float) -> str:
    """Compact dollars for headlines: 1_234_567 -> '$1.23M', -869_092 -> '-$869k'."""
    a = abs(x)
    sign = MINUS if x < 0 and round(a) else ""
    if a >= 1e6:
        return f"{sign}${a / 1e6:.2f}M"
    if a >= 1e4:
        return f"{sign}${a / 1e3:,.0f}k"
    return f"{sign}${a:,.0f}"


def signed(x: float, fmt=usd) -> str:
    """Explicit sign for changes: +$1.50 / -$1.50."""
    s = fmt(x)
    return s if s.startswith(MINUS) or s.lstrip("$0.,") == "" else f"+{s}"


def delta(x: float, fmt=usd, suffix: str = "") -> str:
    """st.metric delta text. Streamlit picks the arrow from a leading ASCII '-', so use that
    (not the typographic minus) here: delta(-3.1, suffix=' this week') -> '-$3.10 this week'."""
    s = fmt(abs(x))
    return f"{'-' if round(x, 2) < 0 else '+'}{s}{suffix}"


def _safe(text: str) -> str:
    """Escape HTML and keep "$" from being read as LaTeX by Streamlit's markdown."""
    return html.escape(text).replace("$", "&#36;")


# --- Data access ----------------------------------------------------------------------------
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


# --- Components -----------------------------------------------------------------------------
def chip(label: str, tone: Tone = "neutral", title: str = "") -> str:
    dot, _, _ = _TONE[tone]
    t = f' title="{_safe(title)}"' if title else ""
    return (
        f'<span class="hp-chip"{t}><span class="hp-dot" style="background:{dot}"></span>'
        f"{_safe(label)}</span>"
    )


def data_chip() -> str:
    """'Live USDA data · Oct 19' or 'Saved data through …', for page headers."""
    idx, source, note = hog_index()
    last = pd.Timestamp(idx["index_date"].iloc[-1])
    if source == "live":
        return chip(f"Live USDA data · index {last:%b %d}", "good", note)
    return chip(f"Saved data through {last:%b %d, %Y}", "caution", note)


def page_header(
    title: str, subtitle: str = "", eyebrow: str = "", meta: Sequence[str] = ()
) -> DeltaGenerator:
    """Eyebrow, title, subtitle on the left; status chips on the right.

    Returns the right-hand column so a page can add an action (e.g. a download button).
    """
    left, right = st.columns([3, 1.25], vertical_alignment="bottom")
    with left:
        if eyebrow:
            st.markdown(f'<div class="hp-eyebrow">{_safe(eyebrow)}</div>', unsafe_allow_html=True)
        st.title(title)
        if subtitle:
            st.markdown(f'<div class="hp-sub">{_safe(subtitle)}</div>', unsafe_allow_html=True)
    with right:
        chips = [data_chip(), *meta]
        st.markdown(f'<div class="hp-meta">{"".join(chips)}</div>', unsafe_allow_html=True)
    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
    return right


def insight(
    tone: Tone,
    status: str,
    headline: str,
    facts: Sequence[tuple[str, str]] = (),
    note: str = "",
) -> None:
    """The page's takeaway: a status chip, one-sentence headline, a row of key figures."""
    fact_html = "".join(
        f'<div><div class="hp-fact-k">{_safe(k)}</div><div class="hp-fact-v">{_safe(v)}</div></div>'
        for k, v in facts
    )
    st.markdown(
        f"""<div class="hp-insight">{chip(status, tone)}
        <div class="hp-insight-head">{_safe(headline)}</div>
        {f'<div class="hp-facts">{fact_html}</div>' if facts else ""}
        {f'<div class="hp-note">{_safe(note)}</div>' if note else ""}</div>""",
        unsafe_allow_html=True,
    )


def verdict(kind: Tone, headline: str, detail: str = "") -> None:
    """Older takeaway API; kept for pages not yet moved to `insight`."""
    insight(kind, {"good": "On track", "bad": "Attention", "neutral": "Note",
                   "caution": "Watch"}[kind], headline, note=detail)  # fmt: skip


def card(key: str) -> DeltaGenerator:
    """A white panel. `key` must be unique on the page."""
    return st.container(key=f"card_{key}")


def section(title: str, caption: str = "") -> None:
    st.markdown(
        f'<div class="hp-section">{_safe(title)}</div>'
        + (f'<div class="hp-section-sub">{_safe(caption)}</div>' if caption else ""),
        unsafe_allow_html=True,
    )


def chart(fig: go.Figure, height: int = 300) -> None:
    """Render a Plotly figure in the house style (no Streamlit theme, no toolbar)."""
    # Explicit colours: Streamlit's renderer otherwise paints the plot area with the theme's
    # secondary background, which shows as a grey box inside white cards.
    fig.update_layout(
        template="hogproj", height=height, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE
    )

    # d3 formats negatives with a true minus ("−$10"); a "$" tickprefix would give "$-10".
    def money_ticks(ax) -> None:  # noqa: ANN001 - plotly axis object
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


def footer_note(text: str) -> None:
    st.markdown(f'<div class="hp-foot">{_safe(text)}</div>', unsafe_allow_html=True)


def as_of() -> str:
    return f"{date.today():%b %d, %Y}"


def asset(name: str) -> Path:
    return ROOT / "assets" / name


def data_notice(source: Source, note: str) -> None:
    """Older API: data status now lives in the page header chip. Warn only when not live."""
    if source != "live":
        st.caption(note)


def table(
    header: Sequence[str], rows: Sequence[Sequence[str]], emphasis_col: int | None = None
) -> None:
    """A clean comparison table: label column left, figures right-aligned in tabular digits.

    All cells are escaped. `emphasis_col` (0-based, excluding the label column) is shaded.
    """

    def cell(text: str, i: int, head: bool = False) -> str:
        tag = "th" if head else "td"
        align = "left" if i == 0 else "right"
        shade = "background:#f7f8fb;" if emphasis_col is not None and i == emphasis_col + 1 else ""
        weight = "font-weight:600;" if head else ("color:#4d535e;" if i == 0 else "")
        return (
            f'<{tag} style="text-align:{align};{shade}{weight}padding:9px 14px;'
            f'border-bottom:1px solid #efefeb">{_safe(text)}</{tag}>'
        )

    head_html = "".join(cell(h, i, True) for i, h in enumerate(header))
    body_html = "".join(
        "<tr>" + "".join(cell(c, i) for i, c in enumerate(r)) + "</tr>" for r in rows
    )
    st.markdown(
        '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;'
        "font-size:13.5px;font-variant-numeric:tabular-nums;color:#16181d;"
        'border:none"><thead style="color:#8b909a;font-size:12px">'
        f"<tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table></div>",
        unsafe_allow_html=True,
    )
