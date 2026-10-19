"""Cost of production, breakeven and projected returns."""

from datetime import date

import numpy as np
import pandas as pd
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
from hogproj.herd import HerdInputs, pigs_sold_per_sow_yr, simulate
from hogproj.markets import seasonal_factors, seasonal_price_path
from hogproj.ui import (
    ACCENT,
    INK,
    INK_2,
    NEG,
    PAGE,
    POS,
    assumption_bar,
    chart,
    chart_title,
    end_tag,
    hero,
    hog_index,
    masthead,
    md,
    quote,
    ref_line,
    rule,
    signed,
    source_note,
    stat_strip,
    tone_of,
    usd,
    usd_short,
)

herd_inp: HerdInputs = st.session_state.get("herd_inputs", HerdInputs())
d = CostInputs()
idx, idx_source, _ = hog_index()
latest_index = round(float(idx["lean_hog_index_usd_per_cwt_carcass"].iloc[-1]), 2)
latest_date = idx["index_date"].iloc[-1]
ss = st.session_state


def cur(key: str, default: float) -> float:
    """Current value of an input (for the chip labels, which render before the widgets)."""
    return float(ss.get(key, default))


# --- Masthead + assumptions -------------------------------------------------------------
head = st.empty()  # filled once we know the numbers
bar = assumption_bar("costs")
with bar:
    # Widget keys start with "cost_" so app.py keeps them when the user switches pages.
    with st.popover(
        md(
            f"Prices · Corn {usd(cur('cost_corn', d.corn_usd_per_bu))} · SBM "
            f"{usd(cur('cost_sbm', d.sbm_usd_per_ton), 0)} · Hogs "
            f"{usd(cur('cost_hog', latest_index))}"
        ),
    ):
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
            f"({'live' if idx_source == 'live' else 'saved'} USDA data).",
        )
    with st.popover(
        md(f"Costs per pig · non-feed {usd(cur('cost_nonfeed', d.nonfeed_usd_per_head), 0)}"),
    ):
        st.caption("Feed amounts are for a 270 lb pig and scale with your market weight.")
        a, b = st.columns(2)
        corn_bu = a.number_input(
            "Corn (bu / pig)", 0.0, 30.0, d.corn_bu_per_head, 0.1, key="cost_corn_bu"
        )
        sbm_lb = b.number_input(
            "Soybean meal (lb / pig)", 0.0, 400.0, d.sbm_lb_per_head, 1.0, key="cost_sbm_lb"
        )
        other_feed = a.number_input(
            "Other feed ($ / pig)",
            0.0,
            200.0,
            d.other_feed_usd_per_head,
            1.0,
            key="cost_other_feed",
            help="DDGS, complete feeds, minerals and feed processing.",
        )
        nonfeed = b.number_input(
            "Non-feed ($ / pig)",
            0.0,
            300.0,
            d.nonfeed_usd_per_head,
            1.0,
            key="cost_nonfeed",
            help="Labor, vet, utilities, breeding herd, trucking, interest, buildings.",
        )
        death = a.number_input(
            "Death loss ($ / pig)", 0.0, 100.0, d.death_loss_usd_per_head, 0.5, key="cost_death"
        )
        manure = b.number_input(
            "Manure credit ($ / pig)",
            0.0,
            50.0,
            d.manure_credit_usd_per_head,
            0.5,
            key="cost_manure",
            help="Fertilizer value of the manure. Set to 0 if you don't use or sell it.",
        )
    with st.popover(f"Price path · {ss.get('cost_price_path') or 'Seasonal'}"):
        path_choice = st.segmented_control(
            "Hog price over time",
            ["Seasonal", "Flat"],
            default="Seasonal",
            key="cost_price_path",
            help="Seasonal starts at your hog price and follows the typical monthly pattern in "
            "USDA data. Flat keeps today's price every week.",
        )
    st.caption(
        f"Market hog {herd_inp.weight_lb_live_market:.0f} lb live × "
        f"{herd_inp.carcass_yield:.0%} yield, set on Herd flow"
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
    pigs_sold_per_sow_yr=pigs_sold_per_sow_yr(herd_inp),
)
ss["cost_inputs"] = c  # the Overview, Scenarios and Risk pages use these
ss["seasonal"] = path_choice != "Flat"
be = breakeven(c)
m = margin_usd_per_head(c)
t = cost_table(c)
feed = float(t.iloc[:3]["usd_per_head"].sum())
feed_share = feed / float(t.loc["Total cost", "usd_per_head"])
gap = hog - be["price_cwt_carcass"]

herd = simulate(herd_inp)
path = (
    seasonal_price_path(date.today(), len(herd), hog, seasonal_factors(idx))
    if ss["seasonal"]
    else None
)
r = weekly_returns(herd, c, path)
r.insert(1, "date", pd.Timestamp(date.today()) + pd.to_timedelta(r["week"] * 7, unit="D"))
y1 = {k: float(r[k].to_numpy()[:52].sum()) for k in ["revenue_usd", "cost_usd", "margin_usd"]}

with head.container():
    masthead(
        f"You need {usd(be['price_cwt_carcass'])}/cwt to cover every cost.",
        f"Feed is {feed_share:.0%} of the {usd(be['cost_usd_per_head'])} it costs to raise a pig. "
        f"At today's {usd(hog)} hog price that's {usd(abs(m))} "
        f"{'made' if m >= 0 else 'lost'} per pig.",
        kicker="Costs & returns",
    )

st.space("small")

# --- Hero: cost per pig ------------------------------------------------------------------
lines = t.iloc[:6].copy()
lines = lines[lines["usd_per_head"].abs() > 0.005]
with hero():
    left, right = st.columns([1, 1.25], gap="large")
    with left:
        quote(
            "Cost per pig",
            usd(be["cost_usd_per_head"]),
            "before manure credit",
            f"{usd(float(t.loc['Net cost', 'usd_per_head']))} net",
            "neutral",
            f"{usd(be['price_cwt_carcass'])}/cwt carcass · {usd(be['price_cwt_live'])}/cwt live "
            "breakeven",
        )
        stat_strip(
            [
                ("Feed", usd(feed), f"{feed_share:.0%} of cost", "neutral"),
                ("Profit per pig", usd(m), f"{signed(gap)}/cwt vs need", tone_of(m)),
                ("Next 12 months", usd_short(y1["margin_usd"]), "projected profit", tone_of(m)),
                ("Breakeven, live", usd(be["price_cwt_live"]), "per cwt live weight", "neutral"),
            ]
        )
    with right:
        chart_title(
            f"{lines['usd_per_head'].idxmax()} and corn are most of the bill",
            "Cost per pig sold by line, $ and share of total",
        )
        order = lines.iloc[::-1]
        bars = go.Figure(
            go.Bar(
                y=order.index,
                x=order["usd_per_head"],
                orientation="h",
                marker={
                    "color": [ACCENT if i < 3 else "#9aa79f" for i in range(len(order))][::-1],
                    "cornerradius": 3,
                },
                text=[
                    f"{usd(v)}  ·  {sh:.0%}"
                    for v, sh in zip(order["usd_per_head"], order["share"], strict=True)
                ],
                textposition="outside",
                textfont={"size": 11.5, "color": INK_2},
                cliponaxis=False,
                hovertemplate="%{y}: %{text}<extra></extra>",
            )
        )
        bars.update_xaxes(visible=False, range=[0, float(order["usd_per_head"].max()) * 1.5])
        bars.update_yaxes(tickfont={"size": 12.5, "color": INK}, ticksuffix="  ", showgrid=False)
        bars.update_layout(hovermode="closest", bargap=0.4, showlegend=False)
        chart(bars, 250)
    source_note(
        "Iowa State University Estimated Livestock Returns, farrow to finish (September 2026)",
        "feed bars in green; non-feed covers labor, vet, utilities, breeding herd, trucking, "
        "interest and buildings",
    )

st.space("medium")

# --- Sensitivity + projection -----------------------------------------------------------
left, mid, right = st.columns([1.25, 0.06, 1])
with left:
    hogs = np.linspace(hog - 20, hog + 20, 9).clip(min=0)
    corns = np.linspace(corn - 1.5, corn + 1.5, 7).clip(min=0)
    grid = sensitivity(c, hogs, corns)
    z = grid.to_numpy()
    need = float(be["price_cwt_carcass"])
    chart_title(
        f"Profit needs hogs near {usd(need, 0)} at today's corn",
        "Profit per pig across hog and corn prices · today's prices outlined",
    )
    lim = float(np.abs(z).max()) or 1.0
    heat = go.Figure(
        go.Heatmap(
            z=z,
            x=[f"${h:.0f}" for h in grid.columns],
            y=[f"${v:.2f}" for v in grid.index],
            colorscale=[[0.0, NEG], [0.5, "#f3f1ec"], [1.0, POS]],
            zmin=-lim,
            zmax=lim,
            xgap=2,
            ygap=2,
            text=[[usd(v, 0) for v in row] for row in z],
            texttemplate="%{text}",
            textfont={"size": 11},
            hovertemplate="Hog %{x}/cwt · corn %{y}/bu<br>%{text} per pig<extra></extra>",
            showscale=False,
        )
    )
    heat.add_shape(
        type="rect", xref="x", yref="y", x0=3.5, x1=4.5, y0=2.5, y1=3.5,
        line={"color": INK, "width": 2},
    )  # fmt: skip
    # Category axes: Plotly would otherwise parse labels like "$55" as numbers.
    heat.update_xaxes(title="Lean hog, $/cwt carcass", showline=False, ticks="", type="category")
    heat.update_yaxes(title="Corn, $/bu", showgrid=False, type="category")
    heat.update_layout(hovermode="closest")
    chart(heat, 330, on=PAGE)
    source_note("model", "$ per pig sold, including the manure credit")
with mid:
    st.markdown(
        '<div style="border-left:1px solid #e5e0d5;height:430px;margin:0 auto;width:1px"></div>',
        unsafe_allow_html=True,
    )
with right:
    final = float(r["cumulative_margin_usd"].iloc[-1])
    years = len(r) / 52
    chart_title(
        f"{usd_short(final)} over the next {years:.0f} years",
        ("Seasonal price path" if path is not None else "Flat price")
        + f" · first year: revenue {usd_short(y1['revenue_usd'])}, costs "
        f"{usd_short(y1['cost_usd'])}",
    )
    tone_col = POS if final >= 0 else NEG
    cf = go.Figure(
        go.Scatter(
            x=r["date"],
            y=r["cumulative_margin_usd"],
            mode="lines",
            line={"color": tone_col, "width": 2},
            hovertemplate="%{x|%b %d, %Y}: $%{y:,.0f}<extra></extra>",
        )
    )
    end_tag(cf, r["date"].iloc[-1], final, usd_short(final), tone_col)
    cf.update_yaxes(tickformat="$~s")
    cf.update_xaxes(tickformat="%b %Y")
    cf.update_layout(showlegend=False, margin={"l": 4, "r": 64, "t": 8, "b": 4})
    chart(cf, 330, on=PAGE)
    source_note("model", "running total of weekly profit; costs booked when pigs are sold")

rule()
chart_title(
    "Hog price used in the projection",
    ("Seasonal pattern from USDA history" if path is not None else "Flat at today's price")
    + " · $/cwt carcass",
)
pf = go.Figure(
    go.Scatter(
        x=r["date"],
        y=r["hog_usd_per_cwt_carcass"],
        mode="lines",
        line={"color": ACCENT, "width": 2},
        hovertemplate="%{x|%b %d, %Y}: $%{y:.2f}/cwt<extra></extra>",
    )
)
ref_line(pf, float(be["price_cwt_carcass"]), f"Breakeven {usd(be['price_cwt_carcass'])}")
pf.update_yaxes(tickprefix="$")
pf.update_xaxes(tickformat="%b %Y")
pf.update_layout(showlegend=False)
chart(pf, 240, on=PAGE)

with st.expander("Cost table and weekly detail"):
    st.dataframe(
        t,
        column_config={
            "usd_per_head": st.column_config.NumberColumn("$ / pig", format="dollar"),
            "usd_per_cwt_carcass": st.column_config.NumberColumn(
                "$ / cwt carcass", format="dollar"
            ),
            "share": st.column_config.NumberColumn("Share of cost", format="percent"),
        },
    )
    weekly_cols = [
        "date",
        "marketed_head",
        "hog_usd_per_cwt_carcass",
        "revenue_usd",
        "cost_usd",
        "margin_usd",
    ]
    st.dataframe(
        r[weekly_cols],
        hide_index=True,
        column_config={
            "date": st.column_config.DateColumn("Week of", format="MMM D, YYYY"),
            "marketed_head": st.column_config.NumberColumn("Pigs sold", format="%,.0f"),
            "hog_usd_per_cwt_carcass": st.column_config.NumberColumn("Hog $/cwt", format="dollar"),
            "revenue_usd": st.column_config.NumberColumn("Revenue", format="dollar"),
            "cost_usd": st.column_config.NumberColumn("Costs", format="dollar"),
            "margin_usd": st.column_config.NumberColumn("Profit", format="dollar"),
        },
    )
    st.download_button(
        "Download weekly CSV",
        r.to_csv(index=False),
        "returns.csv",
        "text/csv",
        icon=":material/download:",
    )
