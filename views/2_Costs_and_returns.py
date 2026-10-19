"""Cost of production, breakeven and projected returns."""

from datetime import date

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
from hogproj.markets import seasonal_factors, seasonal_price_path
from hogproj.ui import hog_index, usd

st.title("Costs & returns")
st.caption(
    "Farrow-to-finish cost per pig sold, laid out like Iowa State University's monthly "
    "Estimated Livestock Returns (defaults: ISU's September 2026 budget). "
    "Hog prices are **\\$/cwt carcass** (the Lean Hog basis) unless marked *live*."
)


herd_inp: HerdInputs = st.session_state.get("herd_inputs", HerdInputs())
d = CostInputs()
idx, idx_source, _ = hog_index()
latest_index = round(float(idx["lean_hog_index_usd_per_cwt_carcass"].iloc[-1]), 2)
latest_date = idx["index_date"].iloc[-1]
with st.sidebar:
    st.header("Prices")
    # Widget keys start with "cost_" so app.py keeps them when the user switches pages.
    corn = st.number_input(
        "Corn ($/bu)",
        0.0,
        20.0,
        d.corn_usd_per_bu,
        0.05,
        key="cost_corn",
        help="Default is Dec 2026 futures (early Oct). Use your local cash bid: Iowa cash "
        "corn usually trades 20-40 cents under futures.",
    )
    sbm = st.number_input(
        "Soybean meal ($/ton)", 0.0, 1000.0, d.sbm_usd_per_ton, 5.0, key="cost_sbm"
    )
    hog = st.number_input(
        "Lean hog price ($/cwt carcass)",
        0.0,
        200.0,
        latest_index,
        0.5,
        key="cost_hog",
        help=f"Starts at the Lean Hog Index for {latest_date:%b %d, %Y} "
        f"({'live' if idx_source == 'live' else 'saved'} USDA data; see Market prices).",
    )
    with st.expander("Costs per pig sold"):
        st.caption("Feed amounts are for a 270 lb pig and scale with your market weight.")
        corn_bu = st.number_input(
            "Corn (bu / pig)", 0.0, 30.0, d.corn_bu_per_head, 0.1, key="cost_corn_bu"
        )
        sbm_lb = st.number_input(
            "Soybean meal (lb / pig)", 0.0, 400.0, d.sbm_lb_per_head, 1.0, key="cost_sbm_lb"
        )
        other_feed = st.number_input(
            "Other feed ($ / pig)",
            0.0,
            200.0,
            d.other_feed_usd_per_head,
            1.0,
            key="cost_other_feed",
            help="DDGS, complete feeds, minerals and feed processing.",
        )
        nonfeed = st.number_input(
            "Non-feed costs ($ / pig)",
            0.0,
            300.0,
            d.nonfeed_usd_per_head,
            1.0,
            key="cost_nonfeed",
            help="Labor, vet, utilities, breeding herd, trucking, interest, buildings.",
        )
        death = st.number_input(
            "Death loss ($ / pig)", 0.0, 100.0, d.death_loss_usd_per_head, 0.5, key="cost_death"
        )
        manure = st.number_input(
            "Manure credit ($ / pig)",
            0.0,
            50.0,
            d.manure_credit_usd_per_head,
            0.5,
            key="cost_manure",
            help="Fertilizer value of the manure. Set to 0 if you don't use or sell it.",
        )
    st.caption(
        f"Market hog: {herd_inp.weight_lb_live_market:.0f} lb live × "
        f"{herd_inp.carcass_yield:.0%} yield (set on the Herd flow page)."
    )

c = CostInputs(
    corn_usd_per_bu=corn,
    sbm_usd_per_ton=sbm,
    lean_hog_usd_per_cwt_carcass=hog,
    corn_bu_per_head=corn_bu,
    sbm_lb_per_head=sbm_lb,
    other_feed_usd_per_head=other_feed,
    nonfeed_usd_per_head=nonfeed,
    death_loss_usd_per_head=death,
    manure_credit_usd_per_head=manure,
    weight_lb_live_market=herd_inp.weight_lb_live_market,
    carcass_yield=herd_inp.carcass_yield,
)
be = breakeven(c)
m = margin_usd_per_head(c)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Breakeven ($/cwt carcass)", usd(be["price_cwt_carcass"]))
k2.metric("Breakeven ($/cwt live)", usd(be["price_cwt_live"]))
k3.metric("Cost per pig", usd(be["cost_usd_per_head"]), help="Before the manure credit, like ISU.")
k4.metric(
    "Profit per pig",
    usd(m),
    delta=f"{usd(hog - be['price_cwt_carcass'])}/cwt vs breakeven",
)

left, right = st.columns([2, 3])
with left:
    st.subheader("Cost breakdown")
    t = cost_table(c)
    st.dataframe(
        t.style.format({"usd_per_cwt_carcass": usd, "usd_per_head": usd, "share": "{:.0%}"}),
        column_config={
            "usd_per_head": "$/pig",
            "usd_per_cwt_carcass": "$/cwt carcass",
            "share": "Share of cost",
        },
        use_container_width=True,
    )
    st.caption(
        "Other feed: DDGS, complete feeds, minerals, processing. Non-feed: labor, vet, "
        "utilities, breeding herd, trucking, interest, buildings."
    )
with right:
    st.subheader("Profit per pig: hog price vs corn price")
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
            hovertemplate="Hog %{x}/cwt, corn %{y}/bu<br>Profit %{text}/pig<extra></extra>",
        )
    )
    heat.update_layout(
        xaxis_title="Lean hog ($/cwt carcass)",
        yaxis_title="Corn ($/bu)",
        margin={"t": 10, "b": 40},
    )
    st.plotly_chart(heat, use_container_width=True)

st.subheader("Projected returns")
path_choice = st.radio(
    "Hog price over the projection",
    ["Seasonal", "Flat"],
    horizontal=True,
    key="cost_price_path",
    help="Seasonal starts at your hog price and follows the typical monthly pattern in USDA "
    "data (see Market prices). Flat keeps today's price for every week.",
)
herd = simulate(herd_inp)
path = (
    seasonal_price_path(date.today(), len(herd), hog, seasonal_factors(idx))
    if path_choice == "Seasonal"
    else None
)
r = weekly_returns(herd, c, path)
change = herd_inp.sows_target - herd_inp.sows_start
herd_note = f"{herd_inp.sows_start:,.0f} sows" + (
    f", {change:+,.0f} from week {herd_inp.change_week}" if change else ""
)
st.caption(
    f"Marketings from the Herd flow page ({herd_note}); week 0 is this week. "
    "Costs are booked when the pigs are sold."
)
g0, g1, g2 = st.columns(3)
price_fig = go.Figure(
    go.Scatter(
        x=r["week"],
        y=r["hog_usd_per_cwt_carcass"],
        mode="lines",
        hovertemplate="Week %{x}<br>$%{y:.2f}/cwt<extra></extra>",
    )
)
price_fig.add_hline(
    y=be["price_cwt_carcass"],
    line_dash="dot",
    line_color="#c62828",
    annotation_text="breakeven",
    annotation_position="top left",
)
price_fig.update_layout(
    title="Hog price used ($/cwt carcass)", xaxis_title="Week", margin={"t": 50, "b": 40}
)
g0.plotly_chart(price_fig, use_container_width=True)
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
