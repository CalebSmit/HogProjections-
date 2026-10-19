"""Herd flow: how many pigs come out, and when."""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj.herd import HerdInputs, lags_weeks, pigs_sold_per_sow_yr, simulate
from hogproj.ui import (
    ACCENT,
    HISTORY,
    MUTED,
    PAGE,
    assumption_bar,
    chart,
    chart_title,
    end_tag,
    hero,
    masthead,
    quote,
    source_note,
    stat_strip,
)

d = HerdInputs()
ss = st.session_state


def cur(key: str, default: float) -> float:
    return float(ss.get(key, default))


head = st.empty()  # masthead, filled once the numbers exist
with assumption_bar("herd"):
    # Widget keys start with "herd_" so app.py keeps them when the user switches pages.
    change_now = cur("herd_sows_change", 0)
    with st.popover(
        f"Herd · {cur('herd_sows', d.sows_start):,.0f} sows"
        + (
            f" · {change_now:+,.0f} from week {cur('herd_change_week', 0):.0f}"
            if change_now
            else ""
        ),
    ):
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
    weaned_now = (
        cur("herd_litters", d.litters_per_sow_yr)
        * cur("herd_born", d.born_alive_per_litter)
        * (1 - cur("herd_pw_mort", d.prewean_mortality * 100) / 100)
    )
    with st.popover(f"Productivity · {weaned_now:.1f} weaned/sow/yr"):
        a, b = st.columns(2)
        litters = a.number_input(
            "Litters / sow / year", 1.0, 3.0, d.litters_per_sow_yr, 0.05, key="herd_litters"
        )
        born = b.number_input(
            "Born alive / litter", 5.0, 25.0, d.born_alive_per_litter, 0.1, key="herd_born"
        )
        pw_mort = a.number_input(
            "Pre-wean mortality %", 0.0, 60.0, d.prewean_mortality * 100, 0.5, key="herd_pw_mort"
        )
        w2f_mort = b.number_input(
            "Wean-to-market mortality %",
            0.0,
            60.0,
            d.wean_to_market_mortality * 100,
            0.5,
            key="herd_w2f_mort",
        )
    # Same rounding as the model (each phase to whole weeks), so the chip matches the page.
    to_mkt_now = sum(
        max(1, round(cur(k, v) / 7))
        for k, v in [
            ("herd_gest", d.gestation_days),
            ("herd_lact", d.lactation_days),
            ("herd_w2f", d.wean_to_market_days),
        ]
    )
    with st.popover(f"Timing · {to_mkt_now} wk breeding to market"):
        gest = st.number_input("Gestation (days)", 100, 130, int(d.gestation_days), key="herd_gest")
        lact = st.number_input("Weaning age (days)", 14, 35, int(d.lactation_days), key="herd_lact")
        w2f = st.number_input(
            "Wean to market (days)", 100, 250, int(d.wean_to_market_days), key="herd_w2f"
        )
        weeks = st.slider("Projection length (weeks)", 52, 260, d.weeks, step=13, key="herd_weeks")
    with st.popover(f"Market hog · {cur('herd_wt', d.weight_lb_live_market):.0f} lb"):
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
ss["herd_inputs"] = inp  # the other pages project these marketings
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

with head.container():
    if change:
        masthead(
            f"The {change:+,.0f}-sow change reaches market around {arrives:%B %d, %Y}.",
            f"Sows bred from {bred:%b %d} take {to_market} weeks to become market hogs; after "
            f"that the farm sells about {per_week_end:,.0f} a week instead of "
            f"{per_week_now:,.0f}.",
            kicker="Herd flow",
        )
    else:
        masthead(
            f"{inp.sows_start:,.0f} sows sell about {per_week_now:,.0f} market hogs a week.",
            f"That's {first_year:,.0f} pigs over the next 12 months. A herd change bred today "
            f"would first reach market around {arrives:%B %d, %Y}.",
            kicker="Herd flow",
        )

st.space("small")
with hero():
    quote(
        "Market hogs, next 12 months",
        f"{first_year:,.0f}",
        "head",
        sub=f"{per_week_now:,.0f} a week today · {pigs_sold_per_sow_yr(inp):.1f} sold per sow per "
        "year",
    )
    stat_strip(
        [
            ("Weaned / sow / yr", f"{weaned_per_sow_yr:.1f}",
             f"{inp.litters_per_sow_yr:.2f} litters × {inp.born_alive_per_litter:.1f} born",
             "neutral"),
            ("Sold / sow / yr", f"{pigs_sold_per_sow_yr(inp):.1f}", "after nursery and finishing"
             " losses", "neutral"),
            ("Per week, end", f"{per_week_end:,.0f}", f"{per_week_end - per_week_now:+,.0f} vs now"
             if change else "steady", "neutral"),
            ("Breeding to market", f"{to_market} wk", f"{lag['gestation']} + {lag['lactation']}"
             f" + {lag['wean_to_market']}", "neutral"),
        ]
    )  # fmt: skip
    st.space("small")
    chart_title(
        "Pigs sold each week" + (f", stepping up from {arrives:%b %Y}" if change > 0 else
                                 f", stepping down from {arrives:%b %Y}" if change < 0 else ""),
        "Head per week · weaned (light) and sold (dark)",
    )  # fmt: skip
    fig = go.Figure()
    fig.add_scatter(
        x=df["date"], y=df["weaned_head"], mode="lines", line={"color": "#a9c4b6", "width": 2},
        hovertemplate="Weaned: %{y:,.0f}<extra></extra>",
    )  # fmt: skip
    fig.add_scatter(
        x=df["date"], y=df["marketed_head"], mode="lines", line={"color": ACCENT, "width": 2.25},
        hovertemplate="Sold: %{y:,.0f}<extra></extra>",
    )  # fmt: skip
    end_tag(fig, df["date"].iloc[-1], per_week_end, f"{per_week_end:,.0f} sold", ACCENT)
    if change:
        for when, label in [(bred, "Change bred"), (arrives, "First extra pigs sold")]:
            fig.add_vline(x=pd.Timestamp(when), line={"color": MUTED, "width": 1, "dash": "dot"})
            fig.add_annotation(
                x=pd.Timestamp(when), y=1, yref="paper", text=label, showarrow=False,
                xanchor="left", yanchor="top", xshift=6, font={"size": 11, "color": MUTED},
            )  # fmt: skip
    fig.update_yaxes(rangemode="tozero", tickformat=",.0f")
    fig.update_xaxes(tickformat="%b %Y")
    fig.update_layout(showlegend=False, margin={"l": 4, "r": 90, "t": 8, "b": 4})
    chart(fig, 330)
    source_note(
        "weekly cohort model",
        f"{lag['gestation']} weeks gestation, {lag['lactation']} nursing, "
        f"{lag['wean_to_market']} to market; mortality applied as pigs leave each phase",
    )

st.space("medium")
chart_title("Pigs on hand", "Head in each phase at the end of the week")
inv = go.Figure()
inv.add_scatter(
    x=df["date"], y=df["growing_inventory_head"], mode="lines",
    line={"color": HISTORY, "width": 2}, hovertemplate="Nursery & finishing: %{y:,.0f}"
    "<extra></extra>",
)  # fmt: skip
inv.add_scatter(
    x=df["date"], y=df["suckling_inventory_head"], mode="lines",
    line={"color": "#a9c4b6", "width": 2}, hovertemplate="Nursing: %{y:,.0f}<extra></extra>",
)  # fmt: skip
end_tag(inv, df["date"].iloc[-1], float(df["growing_inventory_head"].iloc[-1]), "Nursery & "
        "finishing", HISTORY)  # fmt: skip
end_tag(inv, df["date"].iloc[-1], float(df["suckling_inventory_head"].iloc[-1]), "Nursing",
        "#7f9e8d")  # fmt: skip
inv.update_yaxes(rangemode="tozero", tickformat=",.0f")
inv.update_xaxes(tickformat="%b %Y")
inv.update_layout(showlegend=False, margin={"l": 4, "r": 130, "t": 8, "b": 4})
chart(inv, 280, on=PAGE)

with st.expander("Weekly detail"):
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
