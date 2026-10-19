"""Market prices: the CME Lean Hog Index rebuilt from USDA data, with seasonality."""

import calendar

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj.markets import seasonal_factors
from hogproj.ui import data_notice, hog_index, usd

st.title("Market prices")
st.caption(
    "The CME Lean Hog Index, rebuilt each day from USDA's free LM_HG201 slaughter report "
    "(producer-sold negotiated + formula hogs, two-day weighted average). In \\$/cwt carcass."
)

idx, source, note = hog_index()
data_notice(source, note)
dates = pd.to_datetime(idx["index_date"])
values = idx["lean_hog_index_usd_per_cwt_carcass"].to_numpy(dtype=float)
latest_date, latest = dates.iloc[-1], float(values[-1])


def value_days_ago(days: int) -> float | None:
    """Index on the last trading day at least `days` before the latest one."""
    mask = (dates <= latest_date - pd.Timedelta(days=days)).to_numpy()
    return float(values[mask][-1]) if mask.any() else None


week, month, year = value_days_ago(7), value_days_ago(30), value_days_ago(365)
c1, c2, c3, c4 = st.columns(4)
c1.metric(
    f"Lean Hog Index, {latest_date:%b %d}",
    usd(latest),
    None if week is None else f"{usd(latest - week)} vs a week ago",
)
c2.metric("30 days ago", "—" if month is None else usd(month))
c3.metric("1 year ago", "—" if year is None else usd(year))
c4.metric(
    "Live-weight equivalent",
    usd(latest * 0.75),
    help="Index × 0.75 carcass yield. Live and carcass prices differ by about a quarter.",
)

span = st.segmented_control("Show", ["6 months", "1 year", "All"], default="1 year")
days = {"6 months": 182, "1 year": 365}.get(span or "1 year")
view = idx if days is None else idx[(dates >= latest_date - pd.Timedelta(days=days)).to_numpy()]
fig = go.Figure(
    go.Scatter(
        x=view["index_date"],
        y=view["lean_hog_index_usd_per_cwt_carcass"],
        mode="lines",
        hovertemplate="%{x|%b %d, %Y}<br>$%{y:.2f}/cwt<extra></extra>",
    )
)
fig.update_layout(
    title="Lean Hog Index ($/cwt carcass)",
    margin={"t": 50, "b": 30},
    hovermode="x unified",
)
st.plotly_chart(fig, width="stretch")

left, right = st.columns(2)
with left:
    f = seasonal_factors(idx)
    st.subheader("Typical month vs. yearly average")
    if f.empty:
        st.info("Need at least one full calendar year of data.")
    else:
        bar = go.Figure(
            go.Bar(
                x=[calendar.month_abbr[m] for m in f["month"]],
                y=(f["factor"] - 1) * 100,
                marker_color=["#2e7d32" if v >= 1 else "#c62828" for v in f["factor"]],
                hovertemplate="%{x}: %{y:+.1f}%<extra></extra>",
            )
        )
        bar.update_layout(yaxis_title="% vs year average", margin={"t": 10, "b": 30})
        st.plotly_chart(bar, width="stretch")
        st.caption(
            f"Average of {int(f['years'].to_numpy().max())} full calendar year(s). "
            "Hogs usually sell highest in summer and lowest in winter."
        )
with right:
    st.subheader("Average carcass weight")
    wfig = go.Figure(
        go.Scatter(x=view["index_date"], y=view["avg_weight_lb_carcass"], mode="lines")
    )
    wfig.update_layout(yaxis_title="lb carcass", margin={"t": 10, "b": 30})
    st.plotly_chart(wfig, width="stretch")
    st.caption("Heavier hogs mean more pork; weights usually peak in winter.")

st.download_button(
    "Download index history (CSV)", idx.to_csv(index=False), "lean_hog_index.csv", "text/csv"
)
