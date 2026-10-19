"""Scenarios: compare what-ifs side by side against the current plan."""

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from hogproj.markets import seasonal_factors
from hogproj.outlook import Adjustments, compare
from hogproj.ui import (
    BASELINE_SERIES,
    INK,
    INK_2,
    NEG,
    PAGE,
    POS,
    SERIES,
    assumption_bar,
    chart,
    chart_title,
    current_plan,
    hero,
    hog_index,
    masthead,
    md,
    quote,
    rule,
    signed,
    source_note,
    stat_strip,
    table,
    tone_of,
    usd,
    usd_short,
)

idx, _, _ = hog_index()
plan = current_plan()
factors = seasonal_factors(idx)
ss = st.session_state

PRESETS = [
    Adjustments(name="Grow herd 20%", sows_pct=20),
    Adjustments(name="Corn up $1", corn_usd_per_bu=1.0),
    Adjustments(name="2 more pigs per sow", pigs_weaned_per_sow=2),
]

head = st.empty()
scenarios: list[Adjustments] = []
with assumption_bar("scenarios"):
    for i, p in enumerate(PRESETS):
        letter = chr(65 + i)
        label = str(ss.get(f"scn_{i}_name", p.name))
        with st.popover(md(f"{letter} · {label}"), icon=":material/tune:"):
            name = st.text_input("Scenario name", p.name, key=f"scn_{i}_name")
            a, b = st.columns(2)
            hog = a.number_input(
                "Hog price ±$/cwt", -50.0, 50.0, p.hog_usd_per_cwt, 1.0, key=f"scn_{i}_hog"
            )
            corn = b.number_input(
                "Corn ±$/bu", -5.0, 5.0, p.corn_usd_per_bu, 0.1, key=f"scn_{i}_corn"
            )
            sows = a.number_input(
                "Sow herd ±%", -100.0, 200.0, p.sows_pct, 5.0, key=f"scn_{i}_sows"
            )
            pigs = b.number_input(
                "Pigs/sow/yr ±", -10.0, 10.0, p.pigs_weaned_per_sow, 0.5, key=f"scn_{i}_pigs"
            )
            sbm = a.number_input(
                "Soybean meal ±$/ton", -300.0, 300.0, p.sbm_usd_per_ton, 10.0, key=f"scn_{i}_sbm"
            )
            nonfeed = b.number_input(
                "Non-feed ±$/pig", -100.0, 100.0, p.nonfeed_usd_per_head, 1.0,
                key=f"scn_{i}_nonfeed",
            )  # fmt: skip
            weight = a.number_input(
                "Market weight ±lb", -60.0, 60.0, p.weight_lb, 5.0, key=f"scn_{i}_weight"
            )
        scenarios.append(
            Adjustments(
                name=name.strip() or f"Scenario {letter}",
                hog_usd_per_cwt=hog,
                corn_usd_per_bu=corn,
                sbm_usd_per_ton=sbm,
                sows_pct=sows,
                pigs_weaned_per_sow=pigs,
                nonfeed_usd_per_head=nonfeed,
                weight_lb=weight,
            )
        )
    horizon = st.segmented_control(
        "Horizon",
        ["12 months", "24 months"],
        default="24 months",
        key="scn_horizon",
        label_visibility="collapsed",
        help="Herd changes take about 41 weeks to reach market; use 24 months for expansions.",
    )
weeks = 104 if horizon == "24 months" else 52
span = horizon or "24 months"

# Names key the comparison, so make them unique and keep "Current plan" reserved.
seen: dict[str, int] = {}
for s in scenarios:
    if s.name == "Current plan":
        s.name = "Current plan (edited)"
    seen[s.name] = seen.get(s.name, 0) + 1
    if seen[s.name] > 1:
        s.name = f"{s.name} ({seen[s.name]})"

table_df, cum = compare(plan, scenarios, factors, date.today(), weeks)
base = table_df.iloc[0]
alts = table_df.iloc[1:]
best = alts.loc[alts["profit_vs_current_usd"].idxmax()]
winners = int((alts["profit_vs_current_usd"] > 0).sum())

with head.container():
    if winners == 0:
        title = "None of these scenarios beats your current plan."
    elif winners == 1:
        title = f"“{best['scenario']}” is the only scenario that beats your plan."
    else:
        title = f"“{best['scenario']}” adds the most: {usd_short(best['profit_vs_current_usd'])}."
    masthead(
        title,
        f"Over {span}, your current plan makes {usd_short(base['profit_usd'])}. "
        f"“{best['scenario']}” changes that by {signed(best['profit_vs_current_usd'], usd_short)}. "
        "Open a scenario above to change it.",
        kicker="Scenarios",
    )

st.space("small")
colors = [BASELINE_SERIES, *SERIES]
with hero():
    quote(
        "Best scenario vs current plan",
        signed(best["profit_vs_current_usd"], usd_short),
        f"over {span}",
        str(best["scenario"]),
        tone_of(float(best["profit_vs_current_usd"])),
        f"Current plan {usd_short(base['profit_usd'])} · best {usd_short(best['profit_usd'])}",
    )
    stat_strip(
        [
            (
                str(row["scenario"]),
                usd_short(row["profit_usd"]),
                "baseline"
                if row["scenario"] == "Current plan"
                else f"{signed(row['profit_vs_current_usd'], usd_short)} vs current",
                "neutral"
                if row["scenario"] == "Current plan"
                else tone_of(float(row["profit_vs_current_usd"])),
            )
            for _, row in table_df.iterrows()
        ]
    )
    st.space("small")
    chart_title(
        "Running total profit by scenario",
        "Cumulative $ from this week · herd changes show up after the 41-week lag",
    )
    lines = go.Figure()
    for i, name in enumerate(table_df["scenario"]):
        lines.add_scatter(
            x=cum["date"],
            y=cum[name],
            mode="lines",
            line={"color": colors[i], "width": 2.5 if i == 0 else 1.75},
            hovertemplate=f"{name}: $%{{y:,.0f}}<extra></extra>",
            showlegend=False,
        )
    # Label each line at its end instead of a legend; nudge labels apart if they collide.
    ends = sorted(
        ((float(cum[n].iloc[-1]), i, n) for i, n in enumerate(table_df["scenario"])),
        key=lambda e: e[0],
    )
    span_y = max(abs(e[0]) for e in ends) or 1.0
    last_y = None
    for y, i, n in ends:
        y_plot = y if last_y is None or y - last_y > span_y * 0.06 else last_y + span_y * 0.06
        last_y = y_plot
        lines.add_annotation(
            x=cum["date"].iloc[-1], y=y_plot, text=f"<b>{n}</b>  {usd_short(y)}",
            showarrow=False, xanchor="left", xshift=8, font={"size": 11, "color": colors[i]},
        )  # fmt: skip
    lines.update_yaxes(tickformat="$~s")
    lines.update_xaxes(tickformat="%b %Y")
    lines.update_layout(margin={"l": 4, "r": 210, "t": 8, "b": 4})
    chart(lines, 340)
    source_note("model", "each scenario adds its changes to your Herd flow and Costs inputs")

st.space("medium")
left, mid, right = st.columns([1, 0.06, 1.3])
with left:
    chart_title(f"Total profit over {span}", "Change vs current plan in brackets")
    order = table_df.iloc[::-1]
    vals = order["profit_usd"].to_numpy()
    bars = go.Figure(
        go.Bar(
            y=order["scenario"],
            x=vals,
            orientation="h",
            marker={
                "color": [
                    BASELINE_SERIES if n == "Current plan" else (POS if dd >= 0 else NEG)
                    for n, dd in zip(order["scenario"], order["profit_vs_current_usd"], strict=True)
                ],
                "cornerradius": 3,
            },
            hovertemplate="%{y}: $%{x:,.0f}<extra></extra>",
        )
    )
    lim = float(abs(vals).max()) or 1.0
    for n, v, dd in zip(order["scenario"], vals, order["profit_vs_current_usd"], strict=True):
        label = usd_short(v) if n == "Current plan" else f"{usd_short(v)} ({signed(dd, usd_short)})"
        bars.add_annotation(
            y=n, x=max(0.0, float(v)), text=label, xanchor="left", xshift=6, showarrow=False,
            font={"size": 11.5, "color": INK_2},
        )  # fmt: skip
    lo = -lim * 1.08 if (vals < 0).any() else 0
    hi = lim * 1.25 if (vals > 0).any() else lim * 1.05
    bars.update_xaxes(range=[lo, hi], tickformat="$~s", showline=False, ticks="")
    bars.update_yaxes(tickfont={"size": 12.5, "color": INK}, ticksuffix="  ", showgrid=False)
    bars.update_layout(hovermode="closest", bargap=0.42, showlegend=False)
    chart(bars, 290, on=PAGE)
with mid:
    st.markdown(
        '<div style="border-left:1px solid #e5e0d5;height:380px;margin:0 auto;width:1px"></div>',
        unsafe_allow_html=True,
    )
with right:
    chart_title("Side by side", f"Totals over {span}")
    names = list(table_df["scenario"])
    rows = [
        ["Pigs sold", *[f"{v:,.0f}" for v in table_df["pigs_sold"]]],
        ["Revenue", *[usd_short(v) for v in table_df["revenue_usd"]]],
        ["Costs", *[usd_short(v) for v in table_df["cost_usd"]]],
        ["Profit", *[usd_short(v) for v in table_df["profit_usd"]]],
        ["Change vs current", "—", *[signed(v, usd_short) for v in alts["profit_vs_current_usd"]]],
        ["Profit per pig", *[usd(v) for v in table_df["profit_usd_per_head"]]],
        ["Breakeven $/cwt", *[usd(v) for v in table_df["breakeven_cwt_carcass"]]],
        ["Avg hog $/cwt", *[usd(v) for v in table_df["avg_price_cwt_carcass"]]],
    ]
    table(["", *names], rows, emphasis_col=0)

rule()
source_note(
    "model",
    "herd-size changes start being bred this week, so extra pigs reach market after about 41 "
    "weeks; productivity and price changes apply immediately; feed scales with market weight; "
    "sow costs per pig fall as sows wean more pigs",
)
