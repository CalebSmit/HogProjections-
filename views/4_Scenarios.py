"""Scenarios: compare what-ifs side by side against the current plan."""

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from hogproj.markets import seasonal_factors
from hogproj.outlook import Adjustments, compare
from hogproj.ui import BAD, GOOD, NEUTRAL, current_plan, hog_index, usd, usd_short, verdict

st.title("Scenarios")
st.caption(
    "Compare up to three what-ifs with your current plan. Each change is added on top of the "
    "inputs on Herd flow and Costs & returns."
)

idx, _, _ = hog_index()
plan = current_plan()
factors = seasonal_factors(idx)

horizon = st.segmented_control(
    "Compare over",
    ["12 months", "24 months"],
    default="24 months",
    key="scn_horizon",
    help="Herd changes take about 41 weeks to reach market, so use 24 months for expansions.",
)
weeks = 104 if horizon == "24 months" else 52

PRESETS = [
    Adjustments(name="Grow herd 20%", sows_pct=20),
    Adjustments(name="Corn up $1", corn_usd_per_bu=1.0),
    Adjustments(name="2 more pigs per sow", pigs_weaned_per_sow=2),
]
scenarios: list[Adjustments] = []
cols = st.columns(3)
for i, (col, p) in enumerate(zip(cols, PRESETS, strict=True)):
    with col, st.container(border=True):
        name = st.text_input("Name", p.name, key=f"scn_{i}_name")
        hog = st.number_input(
            "Hog price change ($/cwt)", -50.0, 50.0, p.hog_usd_per_cwt, 1.0, key=f"scn_{i}_hog"
        )
        corn = st.number_input(
            "Corn change ($/bu)", -5.0, 5.0, p.corn_usd_per_bu, 0.1, key=f"scn_{i}_corn"
        )
        with st.expander("More changes"):
            sbm = st.number_input(
                "Soybean meal change ($/ton)",
                -300.0,
                300.0,
                p.sbm_usd_per_ton,
                10.0,
                key=f"scn_{i}_sbm",
            )
            sows = st.number_input(
                "Sow herd change (%)", -100.0, 200.0, p.sows_pct, 5.0, key=f"scn_{i}_sows"
            )
            pigs = st.number_input(
                "Pigs weaned / sow / yr change",
                -10.0,
                10.0,
                p.pigs_weaned_per_sow,
                0.5,
                key=f"scn_{i}_pigs",
            )
            nonfeed = st.number_input(
                "Non-feed cost change ($/pig)",
                -100.0,
                100.0,
                p.nonfeed_usd_per_head,
                1.0,
                key=f"scn_{i}_nonfeed",
            )
            weight = st.number_input("Market weight change (lb)", -60.0, 60.0, p.weight_lb, 5.0,
                                     key=f"scn_{i}_weight")  # fmt: skip
        scenarios.append(
            Adjustments(
                name=name.strip() or f"Scenario {i + 1}",
                hog_usd_per_cwt=hog,
                corn_usd_per_bu=corn,
                sbm_usd_per_ton=sbm,
                sows_pct=sows,
                pigs_weaned_per_sow=pigs,
                nonfeed_usd_per_head=nonfeed,
                weight_lb=weight,
            )
        )  # fmt: skip

# Same names would collide in the comparison; number duplicates.
seen: dict[str, int] = {}
for s in scenarios:
    seen[s.name] = seen.get(s.name, 0) + 1
    if seen[s.name] > 1:
        s.name = f"{s.name} ({seen[s.name]})"
if any(s.name == "Current plan" for s in scenarios):
    for s in scenarios:
        if s.name == "Current plan":
            s.name = "Current plan (edited)"

table, cum = compare(plan, scenarios, factors, date.today(), weeks)
base = table.iloc[0]
alts = table.iloc[1:]
best = alts.loc[alts["profit_vs_current_usd"].idxmax()]
worst = alts.loc[alts["profit_vs_current_usd"].idxmin()]
span = horizon or "24 months"

if best["profit_vs_current_usd"] > 0:
    verdict(
        "good",
        f"“{best['scenario']}” adds {usd_short(best['profit_vs_current_usd'])} over {span}.",
        f"Current plan: {usd_short(base['profit_usd'])}. "
        f"Biggest risk shown: “{worst['scenario']}” "
        f"({usd_short(worst['profit_vs_current_usd'])} vs current).",
    )
else:
    verdict(
        "bad",
        f"None of these scenarios beats the current plan over {span}.",
        f"Current plan: {usd_short(base['profit_usd'])}. Least harmful: “{best['scenario']}” "
        f"({usd_short(best['profit_vs_current_usd'])}).",
    )

for col, (_, row) in zip(st.columns(len(table)), table.iterrows(), strict=True):
    is_base = row["scenario"] == "Current plan"
    col.metric(
        row["scenario"],
        usd_short(row["profit_usd"]),
        None if is_base else f"{usd_short(row['profit_vs_current_usd'])} vs current",
        border=True,
        help=f"Total profit over {span}.",
    )

left, right = st.columns(2)
with left, st.container(border=True):
    st.markdown(f"**Total profit over {span}**")
    colors = [NEUTRAL] + [GOOD if v >= 0 else BAD for v in alts["profit_vs_current_usd"]]
    fig = go.Figure(
        go.Bar(
            x=table["scenario"],
            y=table["profit_usd"],
            marker_color=colors,
            text=[usd_short(v) for v in table["profit_usd"]],
            textposition="outside",
            hovertemplate="%{x}: %{text}<extra></extra>",
        )
    )
    fig.update_layout(height=340, margin={"t": 20, "b": 10, "l": 10, "r": 10})
    st.plotly_chart(fig, width="stretch")
with right, st.container(border=True):
    st.markdown("**Running total profit**")
    lines = go.Figure()
    for i, name in enumerate(table["scenario"]):
        lines.add_scatter(
            x=cum["date"],
            y=cum[name],
            name=name,
            mode="lines",
            line={"width": 4 if i == 0 else 2, "dash": "solid" if i == 0 else "dot"},
            hovertemplate="%{x|%b %d, %Y}: $%{y:,.0f}<extra>" + name + "</extra>",
        )
    lines.update_layout(
        height=340,
        margin={"t": 20, "b": 10, "l": 10, "r": 10},
        legend={"orientation": "h", "y": -0.15},
    )
    st.plotly_chart(lines, width="stretch")

with st.container(border=True):
    st.markdown("**Side by side**")
    shown = table.set_index("scenario")
    rows = {
        "Pigs sold": [f"{v:,.0f}" for v in shown["pigs_sold"]],
        "Revenue": [usd_short(v) for v in shown["revenue_usd"]],
        "Costs": [usd_short(v) for v in shown["cost_usd"]],
        "Profit": [usd_short(v) for v in shown["profit_usd"]],
        "Change vs current": ["—"] + [usd_short(v) for v in alts["profit_vs_current_usd"]],
        "Profit per pig": [usd(v) for v in shown["profit_usd_per_head"]],
        "Breakeven ($/cwt carcass)": [usd(v) for v in shown["breakeven_cwt_carcass"]],
        "Avg hog price ($/cwt carcass)": [usd(v) for v in shown["avg_price_cwt_carcass"]],
    }
    st.dataframe(
        {"": list(rows), **{n: [r[i] for r in rows.values()] for i, n in enumerate(shown.index)}},
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Herd-size changes start being bred this week, so extra pigs reach market after about "
        "41 weeks. Productivity and price changes are treated as already in place. Feed scales "
        "with market weight; sow costs per pig fall as sows wean more pigs."
    )
