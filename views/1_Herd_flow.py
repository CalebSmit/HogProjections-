"""Herd flow: how many pigs come out, and when."""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj.herd import HerdInputs, lags_weeks, pigs_sold_per_sow_yr, simulate
from hogproj.ui import SERIES, card, chart, insight, page_header, section

page_header(
    "Herd flow",
    "Pigs weaned and sold each week, and when a herd change reaches market.",
    eyebrow="Your operation",
)

d = HerdInputs()
with st.sidebar:
    st.header("Herd")
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

df["date"] = pd.Timestamp(date.today()) + pd.to_timedelta(df["week"] * 7, unit="D")
weaned_per_sow_yr = inp.litters_per_sow_yr * inp.born_alive_per_litter * (1 - inp.prewean_mortality)
per_week_now = float(df["marketed_head"].iloc[0])
per_week_end = float(df["marketed_head"].iloc[-1])
first_year = float(df["marketed_head"].to_numpy()[:52].sum())
to_market = sum(lag.values())

change = inp.sows_target - inp.sows_start
bred = date.today() + timedelta(weeks=inp.change_week)
arrives = bred + timedelta(weeks=to_market)
if change:
    insight(
        "neutral",
        f"Herd change: {change:+,.0f} sows",
        f"The change bred from {bred:%b %d} first reaches market around {arrives:%b %d, %Y}.",
        [
            ("Sold per week today", f"{per_week_now:,.0f}"),
            ("Sold per week after", f"{per_week_end:,.0f}"),
            ("Breeding to market", f"{to_market} weeks"),
            ("First extra pigs sold", f"{arrives:%b %d, %Y}"),
        ],
    )
else:
    insight(
        "neutral",
        "Steady herd",
        f"{inp.sows_start:,.0f} sows sell about {per_week_now:,.0f} market hogs a week.",
        [
            ("Next 12 months", f"{first_year:,.0f} pigs"),
            ("Breeding to market", f"{to_market} weeks"),
            ("A change bred today sells from", f"{arrives:%b %d, %Y}"),
        ],
    )

c1, c2, c3, c4 = st.columns(4)
c1.metric("Pigs weaned / sow / yr", f"{weaned_per_sow_yr:.1f}", height="stretch")
c2.metric(
    "Pigs sold / sow / yr",
    f"{pigs_sold_per_sow_yr(inp):.1f}",
    help="Weaned pigs that survive to market.",
    height="stretch",
)
c3.metric("Market hogs, next 12 months", f"{first_year:,.0f}", height="stretch")
c4.metric(
    "Breeding to market",
    f"{to_market} wk",
    f"{lag['gestation']} + {lag['lactation']} + {lag['wean_to_market']} wk",
    delta_color="off",
    delta_arrow="off",
    help="Gestation + nursing + wean-to-market, rounded to whole weeks.",
    height="stretch",
)
st.space("small")


def weekly_lines(series: list[tuple[str, str, str]], key: str, title: str, sub: str) -> None:
    with card(key):
        section(title, sub)
        fig = go.Figure()
        for col, name, color in series:
            fig.add_scatter(
                x=df["date"],
                y=df[col],
                name=name,
                mode="lines",
                line={"color": color, "width": 2},
                hovertemplate=f"{name}: %{{y:,.0f}}<extra></extra>",
            )
        fig.update_yaxes(rangemode="tozero", tickformat=",.0f")
        fig.update_xaxes(tickformat="%b %Y")
        chart(fig, 300)


left, right = st.columns(2, gap="medium")
with left:
    weekly_lines(
        [("weaned_head", "Weaned", "#9ec5f4"), ("marketed_head", "Sold", SERIES[0])],
        "flow",
        "Pigs per week",
        "Head weaned and sold each week",
    )
with right:
    weekly_lines(
        [
            ("growing_inventory_head", "Nursery & finishing", SERIES[0]),
            ("suckling_inventory_head", "Nursing", "#9ec5f4"),
        ],
        "inventory",
        "Pigs on hand",
        "Head in each phase at the end of the week",
    )

with st.expander("Weekly detail", icon=":material/table_rows:"):
    table = df[
        ["date", "sows", "farrowings", "weaned_head", "marketed_head", "growing_inventory_head"]
    ]
    st.dataframe(
        table,
        hide_index=True,
        column_config={
            "date": st.column_config.DateColumn("Week of", format="MMM D, YYYY"),
            "sows": st.column_config.NumberColumn("Sows", format="%,.0f"),
            "farrowings": st.column_config.NumberColumn("Farrowings", format="%,.1f"),
            "weaned_head": st.column_config.NumberColumn("Weaned", format="%,.0f"),
            "marketed_head": st.column_config.NumberColumn("Sold", format="%,.0f"),
            "growing_inventory_head": st.column_config.NumberColumn("On feed", format="%,.0f"),
        },
    )
    st.download_button(
        "Download CSV",
        df.to_csv(index=False),
        "herd_flow.csv",
        "text/csv",
        icon=":material/download:",
    )
