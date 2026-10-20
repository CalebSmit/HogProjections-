"""Sow farm: what a weaned pig costs to produce, what it sells for, and finish-or-sell."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj.sowfarm import SowInputs, by_year, cost_lines, cost_per_weaned_pig, history, integrated
from hogproj.ui import (
    ACCENT,
    HISTORY,
    INK,
    PAGE,
    assumption_bar,
    chart,
    chart_title,
    crush_book,
    end_tag,
    hero,
    iowa_corn,
    latest_weaned_pig,
    masthead,
    md,
    quote,
    rule,
    source_note,
    sow_from_state,
    stat_strip,
    table,
    tone_of,
    usd,
    usd_short,
    user_value,
    weaned_pigs,
)

ss = st.session_state
d = SowInputs()
pigs, pig_source, _ = weaned_pigs()
corn_hist, _, _ = iowa_corn()


def cur(key: str, default: float) -> float:
    return user_value(key, default)


head = st.empty()
with assumption_bar("sow"):
    with st.popover(md(f"Pig sale price · USDA + {usd(cur('sow_adder', 0))}")):
        st.number_input("Adder over USDA ($/head)", -50.0, 100.0, 0.0, 0.25, key="sow_adder",
                        help="Premium (or discount) the sow farm gets over the USDA early "
                        "weaned cash composite: health status, genetics, contract "
                        "terms.")  # fmt: skip
    with st.popover(f"Sow feed · {cur('sow_corn_lb', d.corn_lb_per_sow_yr):,.0f} lb corn/sow"):
        st.caption("Pounds per sow per year (gestation + lactation). Prices are the shared corn "
                   "and soybean meal inputs.")  # fmt: skip
        a, b = st.columns(2)
        a.number_input("Corn (lb/sow/yr)", 0.0, 5000.0, d.corn_lb_per_sow_yr, 25.0,
                       key="sow_corn_lb")  # fmt: skip
        b.number_input("Soybean meal (lb/sow/yr)", 0.0, 2000.0, d.sbm_lb_per_sow_yr, 10.0,
                       key="sow_sbm_lb")  # fmt: skip
        a.number_input("Other feed ($/sow/yr)", 0.0, 500.0, d.other_feed_usd_per_sow_yr, 5.0,
                       key="sow_other")  # fmt: skip
    with st.popover(md(f"Non-feed · {usd(cur('sow_nonfeed', d.nonfeed_usd_per_sow_yr), 0)}/sow")):
        st.number_input("Non-feed ($/sow/yr)", 0.0, 5000.0, d.nonfeed_usd_per_sow_yr, 10.0,
                        key="sow_nonfeed",
                        help="Labor, barns, vet and health, genetics and replacement gilts, "
                        "utilities, interest. Default calibrated to Iowa State's farrow-to-wean "
                        "budget.")  # fmt: skip
    st.caption("Pigs weaned per sow from Herd flow")

s = sow_from_state()
usda = latest_weaned_pig()
cost = cost_per_weaned_pig(s)
m = usda + s.adder_usd_per_head - cost
per_sow = m * s.weaned_per_sow_yr
be_weaned = s.weaned_per_sow_yr * cost / max(usda + s.adder_usd_per_head, 0.01)
hist = history(pigs, s, corn_hist)
book = crush_book()
joint = integrated(hist, book.rows)
years = by_year(joint)
last52 = hist[hist["week_ending"] >= hist["week_ending"].max() - pd.Timedelta(weeks=52)]
finish_avg = float(joint["finish_margin_usd"].mean()) if len(joint) else float("nan")
sow_avg = float(joint["margin_usd"].mean()) if len(joint) else float("nan")

with head.container():
    verb = "makes" if m >= 0 else "loses"
    masthead(
        f"A weaned pig costs {usd(cost)} to make and sells for {usd(usda + s.adder_usd_per_head)}.",
        f"At today's USDA price the sow farm {verb} {usd(abs(m))} a pig, "
        f"{usd_short(abs(per_sow))} per sow a year. Since {joint['week_ending'].min():%Y}, "
        f"finishing your own pigs instead of selling them "
        f"{'added' if finish_avg >= 0 else 'cost'} {usd(abs(finish_avg))} a pig on average.",
        kicker="Sow farm · farrow to wean",
    )

st.space("small")
with hero("sow"):
    left, right = st.columns([1, 1.4], gap="large")
    with left:
        quote(
            "Sow farm margin",
            usd(m),
            "per weaned pig",
            f"{usd_short(per_sow)} per sow per year",
            tone_of(m),
            f"USDA early weaned {usd(usda)}"
            + (f" + {usd(s.adder_usd_per_head)}" if s.adder_usd_per_head else "")
            + f" vs cost {usd(cost)}",
        )
        stat_strip(
            [
                ("Cost per pig", usd(cost), f"{s.weaned_per_sow_yr:.1f} weaned/sow/yr", "neutral"),
                ("Last 52 weeks", usd(float(last52["margin_usd"].mean())), "average margin",
                 tone_of(float(last52["margin_usd"].mean()))),
            ]
        )  # fmt: skip
    with right:
        recent = hist[hist["week_ending"] >= hist["week_ending"].max() - pd.DateOffset(years=4)]
        chart_title(
            "Weaned pig price vs what it costs to make one",
            "USDA early weaned 10-12 lb cash (plus your adder) and cost per weaned pig · $/head",
        )
        fig = go.Figure()
        fig.add_scatter(x=recent["week_ending"], y=recent["cost_usd"], mode="lines",
                        name="Cost", line={"color": HISTORY, "width": 1.5, "dash": "dot"},
                        hovertemplate="%{x|%b %d, %Y}: cost $%{y:.2f}<extra></extra>")  # fmt: skip
        fig.add_scatter(x=recent["week_ending"], y=recent["price_usd"], mode="lines",
                        name="Price", line={"color": ACCENT, "width": 2},
                        hovertemplate="%{x|%b %d, %Y}: price $%{y:.2f}<extra></extra>")  # fmt: skip
        last = recent.iloc[-1]
        end_tag(fig, last["week_ending"], float(last["price_usd"]), "Price", ACCENT)
        end_tag(fig, last["week_ending"], float(last["cost_usd"]), "Cost", HISTORY)
        fig.update_yaxes(tickprefix="$", rangemode="tozero")
        fig.update_xaxes(tickformat="%b %Y")
        fig.update_layout(showlegend=False, margin={"l": 4, "r": 56, "t": 8, "b": 4})
        chart(fig, 280)
    source_note(
        "USDA AMS Feeder Pig Report; cost: Iowa State farrow-to-wean structure with Iowa corn "
        "(USDA NASS) by month",
        "soybean meal and non-feed held at today's inputs",
    )

st.space("medium")

left, right = st.columns([1.3, 1], gap="large")
with left:
    chart_title(
        "Finishing added more than the sow farm made"
        if finish_avg > sow_avg
        else "The sow farm made more than finishing added",
        "Average margin per pig by year placed: selling weaned vs finishing your own",
    )
    fy = go.Figure()
    fy.add_bar(x=years["year"].astype(str), y=years["sow_usd"], name="Sow farm (sell weaned)",
               marker={"color": "#9aa79f", "cornerradius": 3},
               hovertemplate="%{x} sow farm: %{y:$,.2f}<extra></extra>")  # fmt: skip
    fy.add_bar(x=years["year"].astype(str), y=years["finish_usd"], name="Finishing adds",
               marker={"color": ACCENT, "cornerradius": 3},
               hovertemplate="%{x} finishing: %{y:$,.2f}<extra></extra>")  # fmt: skip
    fy.add_scatter(x=years["year"].astype(str), y=years["integrated_usd"], mode="markers",
                   name="Farrow to finish", marker={"color": INK, "size": 10, "symbol": "diamond"},
                   hovertemplate="%{x} farrow to finish: %{y:$,.2f}<extra></extra>")  # fmt: skip
    fy.add_hline(y=0, line={"color": INK, "width": 1})
    fy.update_yaxes(tickprefix="$")
    fy.update_layout(barmode="group", bargap=0.3, hovermode="closest",
                     legend={"orientation": "h", "y": 1.1, "x": 0})  # fmt: skip
    chart(fy, 320, on=PAGE)
    source_note(
        "model on USDA prices",
        "only placements already sold; diamonds = sow farm + finishing (farrow to finish)",
    )
with right:
    chart_title("Cost of a weaned pig", f"Per pig at {s.weaned_per_sow_yr:.1f} weaned/sow/year")
    t = cost_lines(s)
    table(
        ["Line", "Per sow / year", "Per weaned pig"],
        [[k, usd(float(r["usd_per_sow_yr"]), 0), usd(float(r["usd_per_weaned_pig"]))]
         for k, r in t.iterrows()],
        emphasis_col=1,
    )  # fmt: skip
    st.space("small")
    if be_weaned <= 40:
        chart_title(
            f"Break even at {be_weaned:.1f} pigs per sow",
            f"Weaned per sow per year needed at today's {usd(usda + s.adder_usd_per_head)} price",
        )
    else:
        chart_title(
            "No realistic productivity breaks even at today's price",
            f"It would take {be_weaned:.0f} weaned per sow per year at "
            f"{usd(usda + s.adder_usd_per_head)}",
        )
    st.caption(
        f"Each extra pig weaned per sow lowers cost by about "
        f"{usd(cost - cost * s.weaned_per_sow_yr / (s.weaned_per_sow_yr + 1))} a pig."
    )
    source_note("Iowa State farrow-to-wean, Sep 2026 structure", "your inputs")

rule()
with st.expander("Weekly history"):
    st.dataframe(
        hist.sort_values("week_ending", ascending=False),
        hide_index=True,
        column_config={
            "week_ending": st.column_config.DateColumn("Week ending", format="MMM D, YYYY"),
            "price_usd": st.column_config.NumberColumn("Price", format="dollar"),
            "cost_usd": st.column_config.NumberColumn("Cost", format="dollar"),
            "margin_usd": st.column_config.NumberColumn("Margin", format="dollar"),
            "corn_usd_per_bu": st.column_config.NumberColumn("Corn $/bu", format="dollar"),
        },
    )
