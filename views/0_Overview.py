"""Overview: are we making money, what does the next year look like, and what moves it?"""

import calendar
from datetime import date

import plotly.graph_objects as go
import streamlit as st

from hogproj.markets import seasonal_factors
from hogproj.outlook import drivers, headline, monthly, project, summary
from hogproj.ui import (
    BAD,
    GOOD,
    current_plan,
    data_notice,
    hog_index,
    usd,
    usd_short,
    verdict,
)

st.title("Overview")
idx, source, note = hog_index()
data_notice(source, note)

plan = current_plan()
factors = seasonal_factors(idx)
today = date.today()
hl = headline(plan)
r = project(plan, factors, today)
year = summary(r)
months = monthly(r)
hog = plan.cost.lean_hog_usd_per_cwt_carcass

# --- The takeaway, in words -------------------------------------------------------------
best = months.loc[months["profit_usd"].idxmax()]
worst = months.loc[months["profit_usd"].idxmin()]
profit_months = int((months["profit_usd"] >= 0).sum())
if profit_months == len(months):
    months_note = f"Every month is profitable; strongest is {best['month']:%B}."
elif profit_months == 0:
    months_note = (
        f"Every month loses money; smallest loss in {best['month']:%B}, "
        f"largest in {worst['month']:%B}."
    )
else:
    months_note = (
        f"{profit_months} of {len(months)} months are profitable; best is "
        f"{best['month']:%B}, worst is {worst['month']:%B}."
    )
word = "profit" if year["profit_usd"] >= 0 else "loss"
outlook = (
    f"Over the next 12 months{' (with the usual seasonal swing)' if plan.seasonal else ''} "
    f"the farm is projected to post a {word} of {usd_short(abs(year['profit_usd']))} on "
    f"{year['pigs_sold']:,.0f} pigs, {usd(abs(year['profit_usd_per_head']))} per pig. "
    f"{months_note}"
)
if hl["gap_cwt_carcass"] >= 0:
    verdict(
        "good",
        f"Making {usd(hl['profit_usd_per_head'])} per pig at today's hog price.",
        f"Hogs could fall {usd(hl['gap_cwt_carcass'])}/cwt (to "
        f"{usd(hl['breakeven_cwt_carcass'])}) before you lose money. {outlook}",
    )
else:
    verdict(
        "bad",
        f"Losing {usd(-hl['profit_usd_per_head'])} per pig at today's hog price.",
        f"Hogs need to rise {usd(-hl['gap_cwt_carcass'])}/cwt, to "
        f"{usd(hl['breakeven_cwt_carcass'])}, to break even. {outlook}",
    )

# --- Headline numbers -------------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric(
    "Hog price used",
    f"{usd(hog)}/cwt",
    help="Lean hog, $/cwt carcass. Starts at the latest USDA-based index; change it on "
    "Costs & returns. The sparkline is the index over the last 90 days.",
    border=True,
    chart_data=idx["lean_hog_index_usd_per_cwt_carcass"].tail(63).round(2).tolist(),
)
k2.metric(
    "Breakeven price",
    f"{usd(hl['breakeven_cwt_carcass'])}/cwt",
    f"{usd(hl['breakeven_cwt_live'])}/cwt live",
    delta_color="off",
    delta_arrow="off",
    border=True,
)
k3.metric(
    "Profit per pig today",
    usd(hl["profit_usd_per_head"]),
    f"{usd(hl['gap_cwt_carcass'])}/cwt vs breakeven",
    border=True,
)
k4.metric(
    "Next 12 months",
    usd_short(year["profit_usd"]),
    f"{year['pigs_sold']:,.0f} pigs sold",
    delta_color="off",
    delta_arrow="off",
    border=True,
)

# --- Outlook charts ---------------------------------------------------------------------
left, right = st.columns(2)
with left, st.container(border=True):
    st.markdown("**Hog price vs. breakeven, next 12 months**")
    labels = [f"{m:%b %y}" for m in months["month"]]
    price = months["hog_usd_per_cwt_carcass"]
    fig = go.Figure()
    fig.add_scatter(
        x=labels,
        y=[hl["breakeven_cwt_carcass"]] * len(labels),
        name="Breakeven",
        mode="lines",
        line={"color": BAD, "dash": "dot"},
    )
    fig.add_scatter(
        x=labels,
        y=price,
        name="Hog price",
        mode="lines+markers",
        line={"color": "#1f4e79", "width": 3},
        fill="tonexty",
        fillcolor="rgba(46,125,50,0.12)" if price.mean() >= hl["breakeven_cwt_carcass"] else
        "rgba(198,40,40,0.10)",
        hovertemplate="%{x}: $%{y:.2f}/cwt<extra></extra>",
    )  # fmt: skip
    fig.update_layout(
        height=320,
        margin={"t": 10, "b": 10, "l": 10, "r": 10},
        yaxis_title="$/cwt carcass",
        legend={"orientation": "h", "y": 1.12},
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")
with right, st.container(border=True):
    st.markdown("**Profit by month**")
    bars = go.Figure(
        go.Bar(
            x=labels,
            y=months["profit_usd"],
            marker_color=[GOOD if v >= 0 else BAD for v in months["profit_usd"]],
            text=[usd_short(v) for v in months["profit_usd"]],
            textposition="outside",
            hovertemplate="%{x}: %{text}<extra></extra>",
        )
    )
    bars.update_layout(height=320, margin={"t": 10, "b": 10, "l": 10, "r": 10}, showlegend=False)
    st.plotly_chart(bars, width="stretch")

# --- What moves profit ------------------------------------------------------------------
left, right = st.columns([3, 2])
with left, st.container(border=True):
    st.markdown("**What moves your next-12-month profit most**")
    st.caption("Each bar changes one thing and keeps everything else the same.")
    d = drivers(plan, factors, today).iloc[::-1]  # biggest at the top
    tor = go.Figure()
    for col, lab in [("low_usd", "low_label"), ("high_usd", "high_label")]:
        tor.add_bar(
            y=d["driver"],
            x=d[col],
            orientation="h",
            marker_color=[GOOD if v >= 0 else BAD for v in d[col]],
            text=[f"{a}: {usd_short(v)}" for a, v in zip(d[lab], d[col], strict=True)],
            textposition="auto",
            hovertemplate="%{y} %{text}<extra></extra>",
            showlegend=False,
        )
    tor.update_layout(
        barmode="group",
        height=330,
        margin={"t": 10, "b": 10, "l": 10, "r": 10},
        xaxis_title="Change in 12-month profit ($)",
    )
    st.plotly_chart(tor, width="stretch")
with right, st.container(border=True):
    st.markdown("**Key assumptions**")
    h, c = plan.herd, plan.cost
    weaned = h.litters_per_sow_yr * h.born_alive_per_litter * (1 - h.prewean_mortality)
    rows = {
        "Sows": f"{h.sows_start:,.0f}",
        "Pigs weaned / sow / yr": f"{weaned:.1f}",
        "Market weight": f"{h.weight_lb_live_market:.0f} lb live",
        "Corn": f"{usd(c.corn_usd_per_bu)}/bu",
        "Soybean meal": f"{usd(c.sbm_usd_per_ton, 0)}/ton",
        "Cost per pig (before manure credit)": usd(hl["cost_usd_per_head"]),
        "Price path": "Seasonal" if plan.seasonal else "Flat",
    }
    st.dataframe(
        {"Assumption": list(rows), "Value": list(rows.values())},
        hide_index=True,
        width="stretch",
    )
    st.page_link("views/1_Herd_flow.py", label="Change herd", icon="🐷")
    st.page_link("views/2_Costs_and_returns.py", label="Change prices & costs", icon="💵")

with st.expander("How to use this app"):
    st.markdown(
        f"""
1. **Herd flow** — enter your sow herd and productivity. See how many pigs you'll sell each
   week and when a herd change reaches market (about 41 weeks from breeding).
2. **Costs & returns** — enter corn, soybean meal and hog prices and your costs per pig. See
   your breakeven and profit, and how they change with hog and corn prices.
3. **Market prices** — today's Lean Hog Index from free USDA data, its history and its
   typical seasonal pattern ({
            calendar.month_name[int(factors.loc[factors["factor"].idxmax(), "month"])]
            if not factors.empty
            else "summer"
        } is usually the high).
4. Come back here for the summary. Everything you change is kept while the app is open.

Costs follow Iowa State University's Estimated Livestock Returns budget. Prices are
\\$/cwt carcass unless marked *live* (live ≈ carcass × 0.75).
"""
    )
