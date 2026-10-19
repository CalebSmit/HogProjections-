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
    INK,
    INK_2,
    MUTED,
    NEG,
    POS,
    REFERENCE,
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
    usd_short,
)

page_header(
    "Costs & returns",
    "Cost per pig sold, in the format of Iowa State's Estimated Livestock Returns.",
    eyebrow="Your operation",
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
    st.header("Projection")
    path_choice = st.segmented_control(
        "Hog price over time",
        ["Seasonal", "Flat"],
        default="Seasonal",
        key="cost_price_path",
        help="Seasonal starts at your hog price and follows the typical monthly pattern in USDA "
        "data. Flat keeps today's price every week.",
    )
    st.caption(
        f"Market hog: {herd_inp.weight_lb_live_market:.0f} lb live × "
        f"{herd_inp.carcass_yield:.0%} yield, set on Herd flow."
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
st.session_state["cost_inputs"] = c  # the Overview, Scenarios and Risk pages use these
st.session_state["seasonal"] = path_choice != "Flat"
be = breakeven(c)
m = margin_usd_per_head(c)
t = cost_table(c)
feed_share = float(t.iloc[:3]["usd_per_head"].sum() / t.loc["Total cost", "usd_per_head"])

herd = simulate(herd_inp)
path = (
    seasonal_price_path(date.today(), len(herd), hog, seasonal_factors(idx))
    if st.session_state["seasonal"]
    else None
)
r = weekly_returns(herd, c, path)
r.insert(1, "date", pd.Timestamp(date.today()) + pd.to_timedelta(r["week"] * 7, unit="D"))
y1 = {k: float(r[k].to_numpy()[:52].sum()) for k in ["revenue_usd", "cost_usd", "margin_usd"]}

gap = hog - be["price_cwt_carcass"]
if gap >= 0:
    status = "Above breakeven"
elif m >= 0:
    status = "Profitable with manure credit"
else:
    status = "Below breakeven"
insight(
    "good" if gap >= 0 else ("caution" if m >= 0 else "bad"),
    status,
    f"You need {usd(be['price_cwt_carcass'])}/cwt carcass to cover every cost.",
    [
        ("Hog price used", f"{usd(hog)}/cwt"),
        ("Gap to breakeven", f"{signed(gap)}/cwt"),
        ("Live-weight breakeven", f"{usd(be['price_cwt_live'])}/cwt"),
        ("Profit, next 12 months", usd_short(y1["margin_usd"])),
    ],
)

feed_cost = float(t.iloc[:3]["usd_per_head"].sum())
k1, k2, k3, k4 = st.columns(4)
k1.metric(
    "Cost per pig",
    usd(be["cost_usd_per_head"]),
    help="Before the manure credit, as ISU reports it.",
    height="stretch",
)
k2.metric(
    "Feed cost per pig",
    usd(feed_cost),
    f"{feed_share:.0%} of cost",
    delta_color="off",
    delta_arrow="off",
    height="stretch",
)
k3.metric(
    "Net cost per pig",
    usd(float(t.loc["Net cost", "usd_per_head"])),
    "after manure credit",
    delta_color="off",
    delta_arrow="off",
    height="stretch",
)
k4.metric("Profit per pig", usd(m), delta(gap, suffix="/cwt vs breakeven"), height="stretch")
st.space("small")

left, right = st.columns([5, 6], gap="medium")
with left, card("costs"):
    section("Where the money goes", f"Cost per pig sold · feed is {feed_share:.0%} of the total")
    lines = t.iloc[:6].copy()
    lines = lines[lines["usd_per_head"].abs() > 0.005].iloc[::-1]
    labels = [
        f"{usd(v)}  ·  {sh:.0%}"
        for v, sh in zip(lines["usd_per_head"], lines["share"], strict=True)
    ]
    bars = go.Figure(
        go.Bar(
            y=lines.index,
            x=lines["usd_per_head"],
            orientation="h",
            marker={"color": SERIES[0], "cornerradius": 3},
            text=labels,
            textposition="outside",
            textfont={"size": 11.5, "color": INK_2},
            cliponaxis=False,
            hovertemplate="%{y}: %{text}<extra></extra>",
        )
    )
    bars.update_xaxes(visible=False, range=[0, float(lines["usd_per_head"].max()) * 1.45])
    bars.update_yaxes(tickfont={"size": 12.5, "color": INK}, ticksuffix="  ", showgrid=False)
    bars.update_layout(hovermode="closest", bargap=0.38, showlegend=False)
    chart(bars, 260)
    total = float(t.loc["Total cost", "usd_per_head"])
    manure_v = -float(t.loc["Less manure credit", "usd_per_head"])
    net = float(t.loc["Net cost", "usd_per_head"])
    summary_html = (
        '<div style="display:flex;gap:28px;border-top:1px solid #efefeb;padding-top:10px;'
        f'font-size:12.5px;color:{MUTED}">'
        f'<div>Total cost<br><b style="color:{INK};font-size:15px">{usd(total)}</b></div>'
        f'<div>Manure credit<br><b style="color:{INK};font-size:15px">{usd(-manure_v)}</b></div>'
        f'<div>Net cost<br><b style="color:{INK};font-size:15px">{usd(net)}</b></div></div>'
    )
    st.markdown(summary_html.replace("$", "&#36;"), unsafe_allow_html=True)
with right, card("grid"):
    section("Profit per pig across hog and corn prices", "$ per pig · current prices outlined")
    hogs = np.linspace(hog - 20, hog + 20, 9).clip(min=0)
    corns = np.linspace(corn - 1.5, corn + 1.5, 7).clip(min=0)
    grid = sensitivity(c, hogs, corns)
    z = grid.to_numpy()
    lim = float(np.abs(z).max()) or 1.0
    heat = go.Figure(
        go.Heatmap(
            z=z,
            x=[f"${h:.0f}" for h in grid.columns],
            y=[f"${v:.2f}" for v in grid.index],
            colorscale=[[0.0, NEG], [0.5, "#f4f3ef"], [1.0, POS]],
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
        type="rect",
        xref="x",
        yref="y",
        x0=3.5,
        x1=4.5,
        y0=2.5,
        y1=3.5,
        line={"color": INK, "width": 2},
    )
    # Category axes: Plotly would otherwise parse labels like "$55" as numbers.
    heat.update_xaxes(title="Lean hog, $/cwt carcass", showline=False, ticks="", type="category")
    heat.update_yaxes(title="Corn, $/bu", showgrid=False, type="category")
    heat.update_layout(hovermode="closest")
    chart(heat, 330)

st.space("small")
left, right = st.columns(2, gap="medium")
with left, card("path"):
    basis = "Seasonal pattern from USDA history" if path is not None else "Flat at today's price"
    section("Hog price used in the projection", f"{basis} · breakeven dashed")
    pf = go.Figure(
        go.Scatter(
            x=r["date"],
            y=r["hog_usd_per_cwt_carcass"],
            mode="lines",
            line={"color": SERIES[0], "width": 2},
            hovertemplate="%{x|%b %d, %Y}: $%{y:.2f}/cwt<extra></extra>",
        )
    )
    pf.add_hline(y=be["price_cwt_carcass"], line={"color": REFERENCE, "width": 1, "dash": "dash"})
    pf.update_yaxes(tickprefix="$")
    pf.update_xaxes(tickformat="%b %Y")
    pf.update_layout(showlegend=False)
    chart(pf, 280)
with right, card("cum"):
    final = float(r["cumulative_margin_usd"].iloc[-1])
    years = len(r) / 52
    section(
        f"Running total: {usd_short(final)} over {years:.0f} years"
        if years >= 2
        else f"Running total: {usd_short(final)}",
        f"First 12 months: revenue {usd_short(y1['revenue_usd'])}, "
        f"costs {usd_short(y1['cost_usd'])}",
    )
    cf = go.Figure(
        go.Scatter(
            x=r["date"],
            y=r["cumulative_margin_usd"],
            mode="lines",
            line={"color": POS if final >= 0 else NEG, "width": 2},
            fill="tozeroy",
            fillcolor="rgba(23,138,106,0.10)" if final >= 0 else "rgba(200,69,58,0.10)",
            hovertemplate="%{x|%b %d, %Y}: $%{y:,.0f}<extra></extra>",
        )
    )
    cf.update_yaxes(tickformat="$~s")
    cf.update_xaxes(tickformat="%b %Y")
    cf.update_layout(showlegend=False)
    chart(cf, 280)

with st.expander("Cost table & weekly detail", icon=":material/table_rows:"):
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
footer_note(
    "Other feed: DDGS, complete feeds, minerals, processing. Non-feed: labor, vet, utilities, "
    "breeding herd, trucking, interest, buildings. Defaults: ISU Estimated Livestock Returns, "
    "September 2026."
)
