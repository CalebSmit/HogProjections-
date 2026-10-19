"""Market prices: the CME Lean Hog Index rebuilt from USDA data, with seasonality."""

import calendar

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj.markets import seasonal_factors
from hogproj.ui import (
    ACCENT,
    HISTORY,
    NEG,
    PAGE,
    POS,
    chart,
    chart_title,
    end_tag,
    hero,
    hog_index,
    kv_table,
    masthead,
    quote,
    rule,
    signed,
    source_note,
    tone_of,
    usd,
)

idx, source, note = hog_index()
dates = pd.to_datetime(idx["index_date"])
values = idx["lean_hog_index_usd_per_cwt_carcass"].to_numpy(dtype=float)
weights = idx["avg_weight_lb_carcass"].to_numpy(dtype=float)
heads = idx["head_count"].to_numpy(dtype=float)
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
move_30 = latest - month if month is not None else 0.0
last_year = values[(dates >= latest_date - pd.Timedelta(days=365)).to_numpy()]

masthead(
    f"Lean hogs at {usd(latest)}, {'up' if move_30 >= 0 else 'down'} {usd(abs(move_30))} in a "
    "month.",
    f"The index usually peaks in {calendar.month_name[peak]} and bottoms in "
    f"{calendar.month_name[low]}. A year ago it was {usd(year) if year else '—'}.",
    kicker="Market prices · CME Lean Hog Index",
)

st.space("small")
with hero():
    left, right = st.columns([1.9, 1], gap="large")
    with left:
        pct = move_30 / month if month else 0.0
        quote(
            "Lean Hog Index",
            usd(latest),
            "/cwt carcass",
            f"{signed(move_30)} ({pct:+.1%}) 30 days".replace("-", "−"),
            tone_of(move_30),
            f"Index for {latest_date:%b %d, %Y} · rebuilt from USDA AMS LM_HG201 · two-day "
            "weighted average",
        )
        st.space("small")
        span = st.segmented_control(
            "Range",
            ["3M", "6M", "1Y", "All"],
            default="1Y",
            key="mkt_span",
            label_visibility="collapsed",
        )
        days = {"3M": 91, "6M": 182, "1Y": 365}.get(span or "1Y")
        sel = (
            (dates >= latest_date - pd.Timedelta(days=days)).to_numpy()
            if days
            else (dates == dates).to_numpy()
        )
        vx, vy = dates[sel], values[sel]
        fig = go.Figure(
            go.Scatter(
                x=vx,
                y=vy,
                mode="lines",
                line={"color": HISTORY, "width": 2},
                fill="tozeroy",
                fillcolor="rgba(31,92,69,0.05)",
                hovertemplate="%{x|%b %d, %Y}: $%{y:.2f}<extra></extra>",
            )
        )
        if month is not None and days and days <= 365:
            fig.add_hline(y=month, line={"color": "#b9b2a3", "width": 1, "dash": "dot"})
            fig.add_annotation(
                x=0.5, xref="paper", y=month, text=f"30 days ago {usd(month)}",
                showarrow=False, xanchor="center", yanchor="bottom", bgcolor="white",
                font={"size": 10.5, "color": "#8f897c"},
            )  # fmt: skip
        end_tag(fig, vx.iloc[-1], latest, usd(latest), NEG if move_30 < 0 else POS)
        lo, hi = float(vy.min()), float(vy.max())
        fig.update_yaxes(range=[lo - (hi - lo) * 0.12, hi + (hi - lo) * 0.12], tickprefix="$")
        fig.update_xaxes(tickformat="%b %Y")
        fig.update_layout(showlegend=False, margin={"l": 4, "r": 64, "t": 8, "b": 4})
        chart(fig, 330)
    with right:
        st.markdown(
            '<div class="hp-quote-label" style="margin-bottom:6px">Key figures</div>',
            unsafe_allow_html=True,
        )
        kv_table(
            [
                ("Week ago", "—" if week is None else usd(week)),
                ("30 days ago", "—" if month is None else usd(month)),
                ("1 year ago", "—" if year is None else usd(year)),
                ("52-wk range", f"{usd(float(last_year.min()))} – {usd(float(last_year.max()))}"),
                ("Live equivalent", usd(latest * 0.75)),
                ("Carcass weight", f"{weights[-1]:.1f} lb"),
                ("Hogs in index", f"{heads[-1]:,.0f}"),
                (
                    "Seasonal high / low",
                    f"{calendar.month_abbr[peak]} / {calendar.month_abbr[low]}",
                ),
            ]
        )
    source_note(
        "USDA AMS Livestock Mandatory Reporting, LM_HG201 (producer-sold negotiated, negotiated "
        "formula and swine/pork market formula barrows and gilts)",
        "matched CME's published index to the cent on Oct 12, 2026",
    )

st.space("medium")
left, mid, right = st.columns([1.4, 0.06, 1])
with left:
    chart_title(
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
                marker={"color": [POS if v >= 1 else NEG for v in f["factor"]], "cornerradius": 3},
                hovertemplate="%{x}: %{y:+.1f}%<extra></extra>",
            )
        )
        bar.update_yaxes(ticksuffix="%", zeroline=True, zerolinecolor="#cfc8b9")
        bar.update_layout(hovermode="closest", bargap=0.38, showlegend=False)
        chart(bar, 270, on=PAGE)
        source_note("USDA AMS LM_HG201", "monthly average index ÷ that year's average")
with mid:
    st.markdown(
        '<div style="border-left:1px solid #e5e0d5;height:360px;margin:0 auto;width:1px"></div>',
        unsafe_allow_html=True,
    )
with right:
    chart_title(
        "Carcasses are heaviest in winter",
        "Average carcass weight, lb per head, barrows and gilts",
    )
    w = go.Figure(
        go.Scatter(
            x=vx,
            y=weights[sel],
            mode="lines",
            line={"color": ACCENT, "width": 1.6},
            hovertemplate="%{x|%b %d, %Y}: %{y:.1f} lb<extra></extra>",
        )
    )
    w.update_yaxes(ticksuffix=" lb")
    w.update_xaxes(tickformat="%b %Y")
    w.update_layout(showlegend=False)
    chart(w, 270, on=PAGE)
    source_note("USDA AMS LM_HG201", "heavier hogs mean more pork per head")

rule()
st.download_button(
    "Download index history",
    idx.to_csv(index=False),
    "lean_hog_index.csv",
    "text/csv",
    icon=":material/download:",
)
