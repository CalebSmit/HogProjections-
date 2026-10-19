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
    POS,
    SERIES,
    card,
    chart,
    current_plan,
    delta,
    hog_index,
    insight,
    page_header,
    section,
    signed,
    table,
    usd,
    usd_short,
)

idx, _, _ = hog_index()
plan = current_plan()
factors = seasonal_factors(idx)

right = page_header(
    "Scenarios",
    "Compare up to three what-ifs with your current plan. Changes are added to your inputs.",
    eyebrow="Decisions",
)
with right:
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

PRESETS = [
    Adjustments(name="Grow herd 20%", sows_pct=20),
    Adjustments(name="Corn up $1", corn_usd_per_bu=1.0),
    Adjustments(name="2 more pigs per sow", pigs_weaned_per_sow=2),
]
scenarios: list[Adjustments] = []
for i, (col, p) in enumerate(zip(st.columns(3, gap="medium"), PRESETS, strict=True)):
    with col, card(f"scn{i}"):
        st.markdown(
            f'<div class="hp-eyebrow" style="color:{SERIES[i]}">Scenario {chr(65 + i)}</div>',
            unsafe_allow_html=True,
        )
        name = st.text_input("Name", p.name, key=f"scn_{i}_name", label_visibility="collapsed")
        a, b = st.columns(2)
        hog = a.number_input(
            "Hog price ±$/cwt", -50.0, 50.0, p.hog_usd_per_cwt, 1.0, key=f"scn_{i}_hog"
        )
        corn = b.number_input("Corn ±$/bu", -5.0, 5.0, p.corn_usd_per_bu, 0.1, key=f"scn_{i}_corn")
        a, b = st.columns(2)
        sows = a.number_input("Sow herd ±%", -100.0, 200.0, p.sows_pct, 5.0, key=f"scn_{i}_sows")
        pigs = b.number_input(
            "Pigs/sow/yr ±", -10.0, 10.0, p.pigs_weaned_per_sow, 0.5, key=f"scn_{i}_pigs"
        )
        with st.popover("More changes", icon=":material/tune:", width="stretch"):
            sbm = st.number_input(
                "Soybean meal ±$/ton", -300.0, 300.0, p.sbm_usd_per_ton, 10.0, key=f"scn_{i}_sbm"
            )
            nonfeed = st.number_input(
                "Non-feed cost ±$/pig",
                -100.0,
                100.0,
                p.nonfeed_usd_per_head,
                1.0,
                key=f"scn_{i}_nonfeed",
            )
            weight = st.number_input(
                "Market weight ±lb", -60.0, 60.0, p.weight_lb, 5.0, key=f"scn_{i}_weight"
            )
        scenarios.append(
            Adjustments(
                name=name.strip() or f"Scenario {chr(65 + i)}",
                hog_usd_per_cwt=hog,
                corn_usd_per_bu=corn,
                sbm_usd_per_ton=sbm,
                sows_pct=sows,
                pigs_weaned_per_sow=pigs,
                nonfeed_usd_per_head=nonfeed,
                weight_lb=weight,
            )
        )

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
worst = alts.loc[alts["profit_vs_current_usd"].idxmin()]

st.space("small")
if best["profit_vs_current_usd"] > 0:
    insight(
        "good",
        f"Best over {span}",
        f"“{best['scenario']}” adds {usd_short(best['profit_vs_current_usd'])} vs your plan.",
        [
            ("Current plan", usd_short(base["profit_usd"])),
            (str(best["scenario"]), usd_short(best["profit_usd"])),
            ("Biggest risk shown", f"{worst['scenario']}"),
            ("Its impact", usd_short(worst["profit_vs_current_usd"])),
        ],
    )
else:
    insight(
        "bad",
        f"No improvement over {span}",
        "None of these scenarios beats the current plan.",
        [
            ("Current plan", usd_short(base["profit_usd"])),
            ("Least harmful", str(best["scenario"])),
            ("Its impact", usd_short(best["profit_vs_current_usd"])),
        ],
    )

colors = [BASELINE_SERIES, *SERIES]
for col, (_, row) in zip(st.columns(len(table_df)), table_df.iterrows(), strict=True):
    is_base = row["scenario"] == "Current plan"
    col.metric(
        str(row["scenario"]),
        usd_short(row["profit_usd"]),
        None if is_base else delta(row["profit_vs_current_usd"], usd_short, " vs current"),
        help=f"Total profit over {span}.",
        height="stretch",
    )
st.space("small")

left, right_col = st.columns([2, 3], gap="medium")
with left, card("totals"):
    section(f"Total profit over {span}", "Change vs current plan in brackets")
    order = table_df.iloc[::-1]
    vals = order["profit_usd"].to_numpy()
    bars = go.Figure(
        go.Bar(
            y=order["scenario"],
            x=vals,
            orientation="h",
            marker={
                "color": [
                    BASELINE_SERIES if n == "Current plan" else (POS if d >= 0 else NEG)
                    for n, d in zip(order["scenario"], order["profit_vs_current_usd"], strict=True)
                ],
                "cornerradius": 3,
            },
            hovertemplate="%{y}: $%{x:,.0f}<extra></extra>",
        )
    )
    # Labels sit just right of the larger of 0 and the bar end, so they never hit the names.
    lim = float(abs(vals).max()) or 1.0
    for n, v, d in zip(order["scenario"], vals, order["profit_vs_current_usd"], strict=True):
        label = usd_short(v) if n == "Current plan" else f"{usd_short(v)}  ({signed(d, usd_short)})"
        bars.add_annotation(
            y=n,
            x=max(0.0, float(v)),
            text=label,
            xanchor="left",
            xshift=6,
            showarrow=False,
            font={"size": 11.5, "color": INK_2},
        )
    lo = -lim * 1.08 if (vals < 0).any() else 0
    hi = lim * 1.25 if (vals > 0).any() else lim * 1.05  # room for the labels
    bars.update_xaxes(range=[lo, hi], tickformat="$~s", showline=False, ticks="")
    bars.update_yaxes(tickfont={"size": 12.5, "color": INK}, ticksuffix="  ", showgrid=False)
    bars.update_layout(hovermode="closest", bargap=0.42, showlegend=False)
    chart(bars, 300)
with right_col, card("running"):
    section("Running total profit", "Herd changes show up after the 41-week lag")
    lines = go.Figure()
    for i, name in enumerate(table_df["scenario"]):
        lines.add_scatter(
            x=cum["date"],
            y=cum[name],
            name=name,
            mode="lines",
            line={"color": colors[i], "width": 2.5 if i == 0 else 2},
            hovertemplate=f"{name}: $%{{y:,.0f}}<extra></extra>",
        )
    lines.update_yaxes(tickformat="$~s")
    lines.update_xaxes(tickformat="%b %Y")
    chart(lines, 300)

with card("compare"):
    section("Side by side", f"Totals over {span}")
    names = list(table_df["scenario"])
    rows = [
        ["Pigs sold", *[f"{v:,.0f}" for v in table_df["pigs_sold"]]],
        ["Revenue", *[usd_short(v) for v in table_df["revenue_usd"]]],
        ["Costs", *[usd_short(v) for v in table_df["cost_usd"]]],
        ["Profit", *[usd_short(v) for v in table_df["profit_usd"]]],
        ["Change vs current", "—", *[signed(v, usd_short) for v in alts["profit_vs_current_usd"]]],
        ["Profit per pig", *[usd(v) for v in table_df["profit_usd_per_head"]]],
        ["Breakeven, $/cwt carcass", *[usd(v) for v in table_df["breakeven_cwt_carcass"]]],
        ["Avg hog price, $/cwt carcass", *[usd(v) for v in table_df["avg_price_cwt_carcass"]]],
    ]
    table(["", *names], rows, emphasis_col=0)
    st.caption(
        "Herd-size changes start being bred this week, so extra pigs reach market after about "
        "41 weeks. Productivity and price changes apply immediately. Feed scales with market "
        "weight; sow costs per pig fall as sows wean more pigs."
    )
