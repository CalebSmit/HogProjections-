"""Herd flow: how many pigs come out, and when."""

import plotly.graph_objects as go
import streamlit as st

from hogproj.herd import HerdInputs, lags_weeks, simulate

st.title("Herd flow")
st.caption(
    "Weekly projection from sows to market hogs. Defaults are US industry benchmarks; "
    "change them in the sidebar to match your farm."
)

d = HerdInputs()
with st.sidebar:
    st.header("Herd size")
    # Widget keys start with "herd_" so app.py keeps them when the user switches pages.
    sows_start = st.number_input(
        "Sows today", 0, 1_000_000, int(d.sows_start), step=50, key="herd_sows"
    )
    sows_change = st.number_input(
        "Change in sows (+/−)",
        -int(sows_start),
        1_000_000,
        0,
        step=50,
        key="herd_sows_change",
        help="Grow or shrink the herd to see when the change reaches market.",
    )
    change_week = st.number_input(
        "Change starts at week", 0, 260, d.change_week, key="herd_change_week"
    )
    weeks = st.slider("Projection length (weeks)", 52, 260, d.weeks, step=13, key="herd_weeks")

    with st.expander("Productivity"):
        litters = st.number_input(
            "Litters / sow / year", 1.0, 3.0, d.litters_per_sow_yr, 0.05, key="herd_litters"
        )
        born = st.number_input(
            "Born alive / litter", 5.0, 25.0, d.born_alive_per_litter, 0.1, key="herd_born"
        )
        pw_mort = st.number_input(
            "Pre-wean mortality %", 0.0, 60.0, d.prewean_mortality * 100, 0.5, key="herd_pw_mort"
        )
        w2f_mort = st.number_input(
            "Wean-to-market mortality %",
            0.0,
            60.0,
            d.wean_to_market_mortality * 100,
            0.5,
            key="herd_w2f_mort",
        )
    with st.expander("Timing"):
        gest = st.number_input("Gestation (days)", 100, 130, int(d.gestation_days), key="herd_gest")
        lact = st.number_input("Weaning age (days)", 14, 35, int(d.lactation_days), key="herd_lact")
        w2f = st.number_input(
            "Wean to market (days)", 100, 250, int(d.wean_to_market_days), key="herd_w2f"
        )
    with st.expander("Market hog"):
        wt = st.number_input(
            "Market weight (lb live)", 150, 400, int(d.weight_lb_live_market), key="herd_wt"
        )
        yld = st.number_input(
            "Carcass yield %", 60.0, 85.0, d.carcass_yield * 100, 0.5, key="herd_yield"
        )

inp = HerdInputs(
    sows_start=sows_start,
    sows_target=max(0, sows_start + sows_change),
    change_week=change_week,
    weeks=weeks,
    litters_per_sow_yr=litters,
    born_alive_per_litter=born,
    prewean_mortality=pw_mort / 100,
    wean_to_market_mortality=w2f_mort / 100,
    gestation_days=gest,
    lactation_days=lact,
    wean_to_market_days=w2f,
    weight_lb_live_market=wt,
    carcass_yield=yld / 100,
)
st.session_state["herd_inputs"] = inp  # the Costs & returns page projects these marketings
df = simulate(inp)
lag = lags_weeks(inp)

weaned_per_sow_yr = inp.litters_per_sow_yr * inp.born_alive_per_litter * (1 - inp.prewean_mortality)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Pigs weaned / sow / year", f"{weaned_per_sow_yr:.1f}")
c2.metric("Market hogs, first 52 weeks", f"{df['marketed_head'].head(52).sum():,.0f}")
c3.metric("Market hogs / week (end)", f"{df['marketed_head'].iloc[-1]:,.0f}")
c4.metric(
    "Breeding to market",
    f"{sum(lag.values())} weeks",
    help="Gestation + lactation + wean-to-market, rounded to whole weeks.",
)

fig = go.Figure()
fig.add_scatter(x=df["week"], y=df["weaned_head"], name="Weaned", mode="lines")
fig.add_scatter(x=df["week"], y=df["marketed_head"], name="Marketed", mode="lines")
fig.update_layout(
    title="Pigs per week",
    xaxis_title="Week",
    yaxis_title="Head",
    yaxis_rangemode="tozero",
    hovermode="x unified",
    margin={"t": 50, "b": 40},
)
st.plotly_chart(fig, use_container_width=True)

fig2 = go.Figure()
fig2.add_scatter(x=df["week"], y=df["growing_inventory_head"], name="Wean-to-market", mode="lines")
fig2.add_scatter(x=df["week"], y=df["suckling_inventory_head"], name="Nursing", mode="lines")
fig2.update_layout(
    title="Pigs on hand (end of week)",
    xaxis_title="Week",
    yaxis_title="Head",
    yaxis_rangemode="tozero",
    hovermode="x unified",
    margin={"t": 50, "b": 40},
)
st.plotly_chart(fig2, use_container_width=True)

with st.expander("Weekly table"):
    st.dataframe(df.round(1), hide_index=True, use_container_width=True)
    st.download_button("Download CSV", df.to_csv(index=False), "herd_flow.csv", "text/csv")
