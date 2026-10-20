"""National view: hog prices by region and how they're sold, corn and basis by state, where
weaned pigs and market hogs come from, and the packer weight discount schedule."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj import national as nv
from hogproj.ui import (
    ACCENT,
    HISTORY,
    INK,
    MUTED,
    NEG,
    PAGE,
    POS,
    SERIES,
    chart,
    chart_title,
    ers_data,
    excel_button,
    hero,
    mars_data,
    masthead,
    quote,
    regional_data,
    rule,
    signed,
    source_note,
    stat_strip,
    table,
    usd,
)

prices, p_src, _ = regional_data("prices")
origin, _, _ = regional_data("origin")
weights, _, _ = regional_data("weights")
corn, c_src, _ = mars_data("state_corn")
flows, _, _ = mars_data("flows")

if prices.empty:
    masthead(
        "Regional hog prices aren't available yet.",
        "Connect to the internet once to load USDA's regional reports.",
        kicker="National view",
    )
    st.stop()

latest = nv.regional_latest(prices)
neg = latest[latest["purchase"] == "Pork market formula"].set_index("region")["price"]
nat = float(neg.get("National", np.nan))
gap = float(neg.get("Iowa/Minnesota", np.nan) - neg.get("Eastern Corn Belt", np.nan))
snap = nv.state_corn_snapshot(corn) if not corn.empty else pd.DataFrame()
day = pd.Timestamp(str(pd.to_datetime(prices["date"]).max()))

corn_line = ""
if len(snap):
    cheap, dear = snap.iloc[0], snap.iloc[-1]
    corn_line = (
        f" Corn is cheapest in {cheap['state']} ({usd(cheap['cash'])}) and dearest in "
        f"{dear['state']} ({usd(dear['cash'])})."
    )
masthead(
    f"Iowa/Minnesota formula hogs bring {usd(neg.get('Iowa/Minnesota', np.nan))}, "
    f"{usd(abs(gap))} {'over' if gap >= 0 else 'under'} the Eastern Corn Belt.",
    f"National pork market formula price {usd(nat)}/cwt over the last week of reports." + corn_line,
    kicker=f"National view · {day:%B %d, %Y}",
)

st.space("small")

# --- Hog prices by region --------------------------------------------------------------------
REGION_COLORS = {
    "National": INK,
    "Iowa/Minnesota": ACCENT,
    "Western Corn Belt": SERIES[0],
    "Eastern Corn Belt": SERIES[1],
}
with hero("national"):
    left, right = st.columns([1, 1.45], gap="large")
    with left:
        quote(
            "Pork market formula, national",
            usd(nat),
            "/cwt carcass",
            "",
            "neutral",
            "Head-weighted, last 5 reports · USDA LM_HG218",
        )
        items = []
        for reg in ("Iowa/Minnesota", "Western Corn Belt", "Eastern Corn Belt"):
            if reg in neg:
                items.append(
                    (
                        reg,
                        usd(float(neg[reg])),
                        f"{signed(float(neg[reg]) - nat)} vs national",
                        "neutral",
                    )
                )
        stat_strip(items)
    with right:
        w = nv.regional_weekly(prices, "Pork market formula")
        w = w[w.index >= w.index.max() - pd.Timedelta(days=365)]
        chart_title(
            "Formula hog prices by region, last 12 months",
            "Swine/pork market formula, $/cwt carcass, weekly average",
        )
        fig = go.Figure()
        for reg in w.columns:
            s = w[reg].dropna()
            if s.empty:
                continue
            color = REGION_COLORS.get(reg, MUTED)
            fig.add_scatter(
                x=s.index,
                y=s.to_numpy(),
                mode="lines",
                name=reg,
                line={"color": color, "width": 2.2 if reg == "Iowa/Minnesota" else 1.5},
                hovertemplate=f"{reg} %{{x|%b %d}}: $%{{y:.2f}}<extra></extra>",
            )
        fig.update_yaxes(tickprefix="$")
        fig.update_xaxes(tickformat="%b %Y")
        fig.update_layout(legend={"orientation": "h", "y": 1.08, "x": 0}, hovermode="x unified")
        chart(fig, 280)
    source_note(
        "USDA AMS LM_HG218 (prior-day hog report by region)"
        + (" (live)" if p_src == "live" else " (saved)"),
        "Iowa/Minnesota and the Western Corn Belt overlap; negotiated prices are often "
        "withheld in regions, so formula prices are compared",
    )
    excel_button(
        {
            "Latest by region": latest,
            "Weekly formula price": w.reset_index(),
            "Daily by region": prices,
        },
        "regional_hog_prices",
        "Hog prices by region",
        "USDA AMS LM_HG218",
    )

st.space("medium")

# --- How hogs are sold -------------------------------------------------------------------------
mix = nv.purchase_mix(prices)
left, mid, right = st.columns([1, 0.06, 1.1])
with left:
    top = mix.iloc[0]
    chart_title(
        f"{top['share']:.0%} of hogs are sold on {str(top['purchase']).lower()}",
        "Share of producer-sold barrows and gilts by purchase type, last 4 weeks, national",
    )
    fm = go.Figure(
        go.Bar(
            y=mix["purchase"][::-1],
            x=mix["share"][::-1] * 100,
            orientation="h",
            marker={"color": ACCENT, "cornerradius": 3},
            text=[
                f"{v:.0%} · {usd(p)}"
                for v, p in zip(mix["share"][::-1], mix["price"][::-1], strict=True)
            ],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x:.1f}% of head<extra></extra>",
        )
    )
    fm.update_xaxes(visible=False, range=[0, float(mix["share"].max()) * 140])
    fm.update_yaxes(ticksuffix="  ", showgrid=False)
    fm.update_layout(showlegend=False, bargap=0.4, hovermode="closest")
    chart(fm, 230, on=PAGE)
    source_note(
        "USDA AMS LM_HG218",
        "price: average $/cwt carcass over the same weeks; other "
        "purchase arrangements include cost-plus and contract hogs",
    )
with mid:
    st.markdown('<div class="hp-vrule" style="height:300px"></div>', unsafe_allow_html=True)
with right:
    ws = nv.weight_schedule(weights) if not weights.empty else pd.DataFrame()
    if len(ws):
        worst = ws.loc[ws["now"].idxmin()]
        chart_title(
            f"A {int(worst['band_lb'])} lb carcass gives up {usd(abs(worst['now']))}/cwt",
            "Packer carcass weight discounts, $/cwt (midpoint of USDA range) · tick: a year ago",
        )
        fw = go.Figure()
        fw.add_bar(
            x=[f"{b}" for b in ws["band_lb"]],
            y=ws["now"],
            marker={"color": [NEG if v < 0 else POS for v in ws["now"]], "cornerradius": 3},
            hovertemplate="%{x} lb carcass: %{y:$.2f}/cwt<extra></extra>",
        )
        fw.add_scatter(
            x=[f"{b}" for b in ws["band_lb"]],
            y=ws["year_ago"],
            mode="markers",
            marker={"color": HISTORY, "size": 9, "symbol": "line-ew-open", "line": {"width": 2}},
            hovertemplate="A year ago: %{y:$.2f}<extra></extra>",
        )
        fw.add_hline(y=0, line={"color": INK, "width": 1})
        fw.update_xaxes(title="carcass weight band, lb", type="category")
        fw.update_yaxes(tickprefix="$")
        fw.update_layout(showlegend=False, hovermode="closest", bargap=0.3)
        chart(fw, 230, on=PAGE)
        source_note(
            "USDA AMS LM_HG218 carcass weight differentials",
            "sell before carcasses reach the discounted bands",
        )
        excel_button(
            {"Weight discounts": ws, "Daily history": weights},
            "weight_discounts",
            "Carcass weight discounts",
            "USDA AMS LM_HG218",
        )

rule()

# --- Corn by state -----------------------------------------------------------------------------
GEO = {
    "scope": "usa",
    "bgcolor": "rgba(0,0,0,0)",
    "showlakes": False,
    "landcolor": "#efece5",
    "subunitcolor": "#ffffff",
    "showsubunits": True,
}
if len(snap):
    left, mid, right = st.columns([1.35, 0.06, 1])
    with left:
        under = snap.loc[snap["basis"].idxmin()]
        chart_title(
            f"Corn basis is weakest in {under['state']} ({under['basis'] * 100:+.0f}¢)".replace(
                "-", "−"
            ),
            "Cash corn basis vs nearby futures by state, ¢/bu · country elevators, latest day",
        )
        lim = float(np.nanmax(np.abs(snap["basis"]))) * 100
        fmap = go.Figure(
            go.Choropleth(
                locations=snap["code"],
                z=snap["basis"] * 100,
                locationmode="USA-states",
                colorscale=[[0, POS], [0.5, "#f3f1ec"], [1, NEG]],
                zmin=-lim,
                zmax=lim,
                marker_line_color="#ffffff",
                marker_line_width=1,
                text=[
                    f"{s}: {usd(c)}/bu, basis {b * 100:+.0f}¢"
                    for s, c, b in zip(snap["state"], snap["cash"], snap["basis"], strict=True)
                ],
                hovertemplate="%{text}<extra></extra>",
                colorbar={"title": "¢", "thickness": 10, "len": 0.6, "tickfont": {"size": 10}},
            )
        )
        fmap.update_layout(geo=GEO, margin={"l": 0, "r": 0, "t": 0, "b": 0})
        chart(fmap, 320, on=PAGE)
        source_note(
            "USDA AMS state grain bid reports (My Market News)"
            + (" (live)" if c_src == "live" else " (saved)"),
            "green: corn cheap against futures (good for feeders), red: dear",
        )
    with mid:
        st.markdown('<div class="hp-vrule" style="height:390px"></div>', unsafe_allow_html=True)
    with right:
        chart_title(
            "Cash corn by state", f"$/bu and basis, {pd.Timestamp(snap['date'].max()):%b %d}"
        )
        table(
            ["State", "Cash", "Basis", "Year ago"],
            [
                [
                    r["state"],
                    usd(r["cash"]),
                    f"{r['basis'] * 100:+.0f}¢".replace("-", "−"),
                    usd(r["cash_year_ago"]) if pd.notna(r["cash_year_ago"]) else "–",
                ]
                for r in snap.to_dict("records")
            ],
            emphasis_col=0,
        )
        excel_button(
            {"Latest by state": snap, "Daily by state": corn},
            "corn_by_state",
            "Cash corn and basis by state",
            "USDA AMS state grain bids",
        )
    rule()

# --- Where pigs and hogs come from --------------------------------------------------------------
left, mid, right = st.columns([1, 0.06, 1])
with left:
    if not flows.empty:
        fl = nv.flows_latest(flows)
        o = fl.dropna(subset=["origin_pct"]).sort_values("origin_pct", ascending=False).head(8)
        top = o.iloc[0]
        chart_title(
            f"{top['state']} supplied {top['origin_pct']:.0f}% of feeder pigs sold this week",
            f"Share of USDA-reported feeder pigs by state of origin · week ending "
            f"{pd.Timestamp(fl['week_ending'].iloc[0]):%b %d} · tick: 52-week average",
        )
        ff = go.Figure()
        ff.add_bar(
            y=o["state"][::-1],
            x=o["origin_pct"][::-1],
            orientation="h",
            marker={"color": ACCENT, "cornerradius": 3},
            hovertemplate="%{y}: %{x:.1f}% of pigs<extra></extra>",
        )
        ff.add_scatter(
            y=o["state"][::-1],
            x=o["origin_pct_52wk"][::-1],
            mode="markers",
            marker={"symbol": "line-ns-open", "size": 14, "color": HISTORY, "line": {"width": 2}},
            hovertemplate="52-week average %{x:.1f}%<extra></extra>",
        )
        ff.update_xaxes(ticksuffix="%")
        ff.update_yaxes(ticksuffix="  ", showgrid=False)
        ff.update_layout(showlegend=False, bargap=0.35, hovermode="closest")
        chart(ff, 300, on=PAGE)
        dest = (
            fl.dropna(subset=["destination_pct"])
            .sort_values("destination_pct", ascending=False)
            .head(3)
        )
        source_note(
            "USDA AMS National Direct Feeder Pig Report",
            "top destinations: "
            + ", ".join(
                f"{r['state']} {r['destination_pct']:.0f}%" for r in dest.to_dict("records")
            ),
        )
        excel_button(
            {"Feeder pig flows": flows},
            "feeder_pig_flows",
            "Feeder pig flows by state",
            "USDA AMS 2810",
        )
with mid:
    st.markdown('<div class="hp-vrule" style="height:390px"></div>', unsafe_allow_html=True)
with right:
    if not origin.empty:
        osh = nv.origin_share(origin)
        top = osh.iloc[0]
        chart_title(
            f"{top['share']:.0%} of producer-sold hogs come from {top['state']}",
            "Share of barrows and gilts by state of origin, last 4 weeks",
        )
        us = osh.dropna(subset=["code"])
        fo = go.Figure(
            go.Choropleth(
                locations=us["code"],
                z=us["share"] * 100,
                locationmode="USA-states",
                colorscale=[[0, "#eef3ef"], [1, ACCENT]],
                marker_line_color="#ffffff",
                marker_line_width=1,
                text=us["state"],
                hovertemplate="%{text}: %{z:.1f}% of hogs<extra></extra>",
                colorbar={"title": "%", "thickness": 10, "len": 0.6, "tickfont": {"size": 10}},
            )
        )
        fo.update_layout(geo=GEO, margin={"l": 0, "r": 0, "t": 0, "b": 0})
        chart(fo, 300, on=PAGE)
        source_note("USDA AMS LM_HG218 state of origin", "producer-sold hogs only")
        excel_button(
            {"Share by state": osh, "Daily by state": origin},
            "hogs_by_state",
            "Hogs by state of origin",
            "USDA AMS LM_HG218",
        )

# --- Pigs from Canada ---------------------------------------------------------------------------
ht, ht_src, _ = ers_data("hog_trade")
cp = nv.canada_pigs(ht)
if cp is not None:
    rule()
    m = cp["monthly"]
    this_y, last_y = cp["through"].year, cp["through"].year - 1
    pct_ = cp["pigs_pct"]
    chart_title(
        f"{cp['pigs'] / 1e6:.2f}M weaned and feeder pigs came in from Canada through "
        f"{cp['through']:%B}, {abs(pct_):.0%} {'more' if pct_ >= 0 else 'fewer'} than last year",
        f"Live pigs under 23 kg imported per month, head · bars: {this_y}, dotted: {last_y}",
    )
    now_ = m[m.index.year == this_y]
    prev_ = m[m.index.year == last_y]
    fc = go.Figure()
    fc.add_bar(
        x=now_.index.month,
        y=now_["pigs"],
        name=str(this_y),
        marker={"color": ACCENT, "cornerradius": 3},
        hovertemplate=f"%{{x}}/{this_y}: %{{y:,.0f}} pigs<extra></extra>",
    )
    fc.add_scatter(x=prev_.index.month, y=prev_["pigs"], name=str(last_y), mode="lines+markers",
                   line={"color": MUTED, "width": 1.6, "dash": "dot"},
                   marker={"size": 8, "color": MUTED},
                   hovertemplate=f"%{{x}}/{last_y}: %{{y:,.0f}} pigs<extra></extra>")  # fmt: skip
    fc.update_xaxes(
        tickmode="array",
        tickvals=list(range(1, 13)),
        ticktext=[f"{pd.Timestamp(2000, k, 1):%b}" for k in range(1, 13)],
    )
    fc.update_yaxes(tickformat="~s")
    fc.update_layout(showlegend=False, bargap=0.35, hovermode="closest")
    chart(fc, 270, on=PAGE)
    sp_ = cp["slaughter_pct"]
    source_note(
        "USDA ERS Livestock and Meat International Trade" + (" (live)" if ht_src == "live"
                                                             else " (saved)"),
        f"slaughter hogs imported this year: {cp['slaughter'] / 1e6:.2f}M, "
        + f"{sp_:+.0%}".replace("-", "−") + " vs last year; about two months behind",
    )  # fmt: skip
    excel_button({"Monthly": m.reset_index(), "By class and country": ht}, "live_hog_imports",
                 "Live hog imports", "USDA ERS")  # fmt: skip
