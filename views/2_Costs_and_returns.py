"""Cost of production, breakeven and projected returns."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from hogproj.finance import (
    CostInputs,
    breakeven,
    cost_table,
    margin_usd_per_head,
    sensitivity,
    weekly_returns,
)
from hogproj.herd import HerdInputs, simulate

st.title("Costs & returns")
st.caption(
    "Farrow-to-finish cost of production using the CIH Hog Margin Watch rule of thumb: "
    "per 100 lb carcass, 5.3 bu corn + 73 lb soybean meal + \\$44 of other costs. "
    "Hog prices are **\\$/cwt carcass** (the Lean Hog basis) unless marked *live*."
)


def usd(x: float, decimals: int = 2) -> str:
    """-11.6 -> '-$11.60' (not '$-11.60')."""
    return f"{'-' if x < 0 else ''}${abs(x):,.{decimals}f}"


herd_inp: HerdInputs = st.session_state.get("herd_inputs", HerdInputs())
d = CostInputs()
with st.sidebar:
    st.header("Prices")
    # Widget keys start with "cost_" so app.py keeps them when the user switches pages.
    corn = st.number_input("Corn ($/bu)", 0.0, 20.0, d.corn_usd_per_bu, 0.05, key="cost_corn")
    sbm = st.number_input(
        "Soybean meal ($/ton)", 0.0, 1000.0, d.sbm_usd_per_ton, 5.0, key="cost_sbm"
    )
    hog = st.number_input(
        "Lean hog price ($/cwt carcass)",
        0.0,
        200.0,
        d.lean_hog_usd_per_cwt_carcass,
        0.5,
        key="cost_hog",
        help="Default: CME Lean Hog Index on Oct 12, 2026. Dec 2026 futures were near 67.",
    )
    with st.expander("Ration & non-feed costs"):
        corn_bu = st.number_input(
            "Corn (bu / cwt carcass)", 0.0, 15.0, d.corn_bu_per_cwt_carcass, key="cost_corn_bu"
        )
        sbm_lb = st.number_input(
            "SBM (lb / cwt carcass)", 0.0, 300.0, d.sbm_lb_per_cwt_carcass, key="cost_sbm_lb"
        )
        other = st.number_input(
            "Other costs ($ / cwt carcass)",
            0.0,
            200.0,
            d.other_usd_per_cwt_carcass,
            1.0,
            key="cost_other",
            help="Labor, vet, utilities, interest, facilities, breeding herd.",
        )
    st.caption(
        f"Market hog: {herd_inp.weight_lb_live_market:.0f} lb live × "
        f"{herd_inp.carcass_yield:.0%} yield (set on the Herd flow page)."
    )

c = CostInputs(
    corn_usd_per_bu=corn,
    sbm_usd_per_ton=sbm,
    lean_hog_usd_per_cwt_carcass=hog,
    corn_bu_per_cwt_carcass=corn_bu,
    sbm_lb_per_cwt_carcass=sbm_lb,
    other_usd_per_cwt_carcass=other,
    weight_lb_live_market=herd_inp.weight_lb_live_market,
    carcass_yield=herd_inp.carcass_yield,
)
be = breakeven(c)
m = margin_usd_per_head(c)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Breakeven ($/cwt carcass)", f"${be['price_cwt_carcass']:.2f}")
k2.metric("Breakeven ($/cwt live)", f"${be['price_cwt_live']:.2f}")
k3.metric("Cost per head", f"${be['cost_usd_per_head']:.2f}")
k4.metric(
    "Margin per head",
    usd(m),
    delta=f"{usd(hog - be['price_cwt_carcass'])}/cwt vs breakeven",
)

left, right = st.columns([2, 3])
with left:
    st.subheader("Cost breakdown")
    t = cost_table(c)
    st.dataframe(
        t.style.format(
            {"usd_per_cwt_carcass": "${:.2f}", "usd_per_head": "${:.2f}", "share": "{:.0%}"}
        ),
        column_config={
            "usd_per_cwt_carcass": "$/cwt carcass",
            "usd_per_head": "$/head",
            "share": "Share",
        },
        use_container_width=True,
    )
with right:
    st.subheader("Margin per head: hog price vs corn price")
    hogs = np.linspace(hog - 20, hog + 20, 9).clip(min=0)
    corns = np.linspace(corn - 1.5, corn + 1.5, 7).clip(min=0)
    grid = sensitivity(c, hogs, corns)
    lim = float(np.abs(grid.to_numpy()).max()) or 1.0
    heat = go.Figure(
        go.Heatmap(
            z=grid.to_numpy(),
            x=[f"${h:.0f}" for h in grid.columns],
            y=[f"${v:.2f}" for v in grid.index],
            colorscale="RdYlGn",
            zmin=-lim,
            zmax=lim,
            text=[[usd(v, 0) for v in row] for row in grid.to_numpy()],
            texttemplate="%{text}",
            hovertemplate="Hog %{x}/cwt, corn %{y}/bu<br>Margin %{text}/head<extra></extra>",
        )
    )
    heat.update_layout(
        xaxis_title="Lean hog ($/cwt carcass)",
        yaxis_title="Corn ($/bu)",
        margin={"t": 10, "b": 40},
    )
    st.plotly_chart(heat, use_container_width=True)

st.subheader("Projected returns")
herd = simulate(herd_inp)
r = weekly_returns(herd, c)
change = herd_inp.sows_target - herd_inp.sows_start
herd_note = f"{herd_inp.sows_start:,.0f} sows" + (
    f", {change:+,.0f} from week {herd_inp.change_week}" if change else ""
)
st.caption(
    f"Marketings from the Herd flow page ({herd_note}), at a flat hog price. "
    "Costs are booked when the pigs are sold."
)
g1, g2 = st.columns(2)
weekly = go.Figure(
    go.Bar(
        x=r["week"],
        y=r["margin_usd"],
        marker_color=np.where(r["margin_usd"] >= 0, "#2e7d32", "#c62828"),
        hovertemplate="Week %{x}<br>%{y:$,.0f}<extra></extra>",
    )
)
weekly.update_layout(
    title="Margin each week", xaxis_title="Week", yaxis_title="$", margin={"t": 50, "b": 40}
)
g1.plotly_chart(weekly, use_container_width=True)
cum = go.Figure(
    go.Scatter(
        x=r["week"],
        y=r["cumulative_margin_usd"],
        mode="lines",
        fill="tozeroy",
        hovertemplate="Week %{x}<br>%{y:$,.0f}<extra></extra>",
    )
)
cum.update_layout(
    title="Cumulative margin", xaxis_title="Week", yaxis_title="$", margin={"t": 50, "b": 40}
)
g2.plotly_chart(cum, use_container_width=True)
y1 = {k: float(r[k].to_numpy()[:52].sum()) for k in ["revenue_usd", "cost_usd", "margin_usd"]}
s1, s2, s3 = st.columns(3)
s1.metric("Revenue, first 52 weeks", usd(y1["revenue_usd"], 0))
s2.metric("Costs, first 52 weeks", usd(y1["cost_usd"], 0))
s3.metric("Margin, first 52 weeks", usd(y1["margin_usd"], 0))
with st.expander("Weekly table"):
    st.dataframe(r.round(2), hide_index=True, use_container_width=True)
    st.download_button("Download CSV", r.to_csv(index=False), "returns.csv", "text/csv")
