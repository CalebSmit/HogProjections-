"""Market prices: the CME Lean Hog Index rebuilt from USDA data, with seasonality."""

import calendar

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj.markets import seasonal_factors
from hogproj.ui import (
    INK,
    NEG,
    POS,
    SERIES,
    card,
    chart,
    delta,
    footer_note,
    hog_index,
    insight,
    page_header,
    section,
    signed,
    usd,
)

right = page_header(
    "Market prices",
    "CME Lean Hog Index rebuilt daily from USDA's LM_HG201 slaughter report.",
    eyebrow="Markets",
)

idx, source, note = hog_index()
dates = pd.to_datetime(idx["index_date"])
values = idx["lean_hog_index_usd_per_cwt_carcass"].to_numpy(dtype=float)
latest_date, latest = dates.iloc[-1], float(values[-1])


def value_days_ago(days: int) -> float | None:
    """Index on the last trading day at least `days` before the latest one."""
    mask = (dates <= latest_date - pd.Timedelta(days=days)).to_numpy()
    return float(values[mask][-1]) if mask.any() else None


week, month, year = value_days_ago(7), value_days_ago(30), value_days_ago(365)
f = seasonal_factors(idx)
n_years = int(f["years"].to_numpy().max()) if not f.empty else 0
peak = int(f.loc[f["factor"].idxmax(), "month"]) if not f.empty else 7
low = int(f.loc[f["factor"].idxmin(), "month"]) if not f.empty else 1
this_month = float(dict(zip(f["month"], f["factor"], strict=True)).get(latest_date.month, 1.0))

move_30 = latest - month if month is not None else 0.0
insight(
    "good" if move_30 >= 0 else "bad",
    "Rising" if move_30 >= 0 else "Falling",
    f"Lean Hog Index at {usd(latest)}/cwt, {signed(move_30)} over 30 days.",
    [
        ("A year ago", "—" if year is None else f"{usd(year)}/cwt"),
        ("Live-weight equivalent", f"{usd(latest * 0.75)}/cwt"),
        ("Seasonal high", calendar.month_name[peak]),
        ("Seasonal low", calendar.month_name[low]),
    ],
)

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    f"Index, {latest_date:%b %d}",
    usd(latest),
    None if week is None else delta(latest - week, suffix=" vs a week ago"),
    chart_data=values[-63:].round(2).tolist(),
    chart_type="area",
    height="stretch",
)
c2.metric("30 days ago", "—" if month is None else usd(month), height="stretch")
c3.metric("1 year ago", "—" if year is None else usd(year), height="stretch")
c4.metric(
    "This month vs. yearly average",
    f"{this_month - 1:+.0%}",
    help="Typical seasonal level for this calendar month.",
    height="stretch",
)
st.space("small")

with card("history"):
    head_l, head_r = st.columns([3, 1], vertical_alignment="center")
    with head_l:
        section("Lean Hog Index", "$/cwt carcass, two-day weighted average")
    with head_r:
        span = st.segmented_control(
            "Range",
            ["6M", "1Y", "All"],
            default="1Y",
            key="mkt_span",
            label_visibility="collapsed",
        )
    days = {"6M": 182, "1Y": 365}.get(span or "1Y")
    view = idx if days is None else idx[(dates >= latest_date - pd.Timedelta(days=days)).to_numpy()]
    fig = go.Figure(
        go.Scatter(
            x=view["index_date"],
            y=view["lean_hog_index_usd_per_cwt_carcass"],
            mode="lines",
            line={"color": SERIES[0], "width": 2},
            fill="tozeroy",
            fillcolor="rgba(42,120,214,0.06)",
            hovertemplate="%{x|%b %d, %Y}: $%{y:.2f}<extra></extra>",
        )
    )
    v = view["lean_hog_index_usd_per_cwt_carcass"]
    lo, hi = float(v.to_numpy().min()), float(v.to_numpy().max())
    fig.update_yaxes(range=[lo - (hi - lo) * 0.12, hi + (hi - lo) * 0.12], tickprefix="$")
    fig.update_xaxes(tickformat="%b %Y")
    fig.update_layout(showlegend=False)
    chart(fig, 330)

left, right_col = st.columns(2, gap="medium")
with left, card("season"):
    section(
        f"Hogs usually peak in {calendar.month_name[peak]} and bottom in "
        f"{calendar.month_name[low]}",
        f"Typical month vs. its year's average · {n_years} full years of data",
    )
    if f.empty:
        st.info("Needs at least one full calendar year of data.")
    else:
        bar = go.Figure(
            go.Bar(
                x=[calendar.month_abbr[m] for m in f["month"]],
                y=(f["factor"] - 1) * 100,
                marker={
                    "color": [POS if v >= 1 else NEG for v in f["factor"]],
                    "cornerradius": 3,
                },
                hovertemplate="%{x}: %{y:+.1f}%<extra></extra>",
            )
        )
        bar.update_yaxes(ticksuffix="%", zeroline=True, zerolinecolor="#cfcfc8")
        bar.update_layout(hovermode="closest", bargap=0.35, showlegend=False)
        chart(bar, 280)
with right_col, card("weight"):
    section("Average carcass weight", "lb per head, barrows and gilts · heavier in winter")
    w = go.Figure(
        go.Scatter(
            x=view["index_date"],
            y=view["avg_weight_lb_carcass"],
            mode="lines",
            line={"color": INK, "width": 1.5},
            hovertemplate="%{x|%b %d, %Y}: %{y:.1f} lb<extra></extra>",
        )
    )
    w.update_yaxes(ticksuffix=" lb")
    w.update_xaxes(tickformat="%b %Y")
    w.update_layout(showlegend=False)
    chart(w, 280)

st.download_button(
    "Download index history",
    idx.to_csv(index=False),
    "lean_hog_index.csv",
    "text/csv",
    icon=":material/download:",
)
footer_note(
    f"{note} The index uses producer-sold negotiated, negotiated formula and swine/pork market "
    "formula barrows and gilts; it matched CME's published value to the cent on Oct 12, 2026."
)
