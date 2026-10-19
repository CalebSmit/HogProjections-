"""Overview: are we making money, what does the next year look like, and what moves it?"""

import calendar
from datetime import date

import plotly.graph_objects as go
import streamlit as st

from hogproj.export import build_report
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

idx, source, note = hog_index()
plan = current_plan()
factors = seasonal_factors(idx)
today = date.today()
hl = headline(plan)
r = project(plan, factors, today)

head_l, head_r = st.columns([4, 1], vertical_alignment="bottom")
head_l.title("Overview")
report_slot = head_r.empty()  # filled once the verdict text exists
data_notice(source, note)
year = summary(r)
months = monthly(r)
hog = plan.cost.lean_hog_usd_per_cwt_carcass

# --- The takeaway, in words -------------------------------------------------------------
# Rank months per pig sold: months have 4 or 5 sale weeks, so totals mostly track week count.
per_pig = months["profit_usd_per_head"].fillna(0)
best = months.loc[per_pig.idxmax()]
worst = months.loc[per_pig.idxmin()]
profit_months = int((per_pig >= 0).sum())
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
# Good/bad follows profit (which includes the manure credit). Breakeven follows ISU and
# leaves the credit out, so a price just under breakeven can still be profitable.
if hl["profit_usd_per_head"] >= 0 and hl["gap_cwt_carcass"] >= 0:
    kind = "good"
    title = f"Making {usd(hl['profit_usd_per_head'])} per pig at today's hog price."
    detail = (
        f"Hogs could fall {usd(hl['gap_cwt_carcass'])}/cwt (to "
        f"{usd(hl['breakeven_cwt_carcass'])}) before you stop covering costs. {outlook}"
    )
elif hl["profit_usd_per_head"] >= 0:
    kind = "neutral"
    title = f"Making {usd(hl['profit_usd_per_head'])} per pig, thanks to the manure credit."
    detail = (
        f"The hog price alone is {usd(-hl['gap_cwt_carcass'])}/cwt short of covering costs "
        f"({usd(hl['breakeven_cwt_carcass'])}); the manure's fertilizer value makes up the "
        f"difference. {outlook}"
    )
else:
    kind = "bad"
    title = f"Losing {usd(-hl['profit_usd_per_head'])} per pig at today's hog price."
    detail = (
        f"Hogs need to rise {usd(-hl['gap_cwt_carcass'])}/cwt, to "
        f"{usd(hl['breakeven_cwt_carcass'])}, to break even. {outlook}"
    )
verdict(kind, title, detail)
report_slot.download_button(
    "⬇ Excel report",
    build_report(plan, r, today, note, f"{title} {detail}"),
    f"hog_outlook_{today:%Y-%m-%d}.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    help="Summary, assumptions, 24-month outlook with chart, cost breakdown and weekly detail. "
    "Good for sharing with a client.",
    width="stretch",
)

# --- Headline numbers -------------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)  # height="stretch" keeps the four cards level
k1.metric(
    "Hog price used",
    f"{usd(hog)}/cwt",
    help="Lean hog, $/cwt carcass. Starts at the latest USDA-based index; change it on "
    "Costs & returns. The sparkline is the index over the last 90 days.",
    border=True,
    height="stretch",
    chart_data=idx["lean_hog_index_usd_per_cwt_carcass"].tail(63).round(2).tolist(),
)
k2.metric(
    "Breakeven price",
    f"{usd(hl['breakeven_cwt_carcass'])}/cwt",
    f"{usd(hl['breakeven_cwt_live'])}/cwt live",
    delta_color="off",
    delta_arrow="off",
    border=True,
    height="stretch",
)
k3.metric(
    "Profit per pig today",
    usd(hl["profit_usd_per_head"]),
    f"{usd(hl['gap_cwt_carcass'])}/cwt vs breakeven",
    border=True,
    height="stretch",
)
k4.metric(
    "Next 12 months",
    usd_short(year["profit_usd"]),
    f"{year['pigs_sold']:,.0f} pigs sold",
    delta_color="off",
    delta_arrow="off",
    border=True,
    height="stretch",
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
    st.markdown("**Profit per pig sold, by month**")
    bars = go.Figure(
        go.Bar(
            x=labels,
            y=per_pig,
            marker_color=[GOOD if v >= 0 else BAD for v in per_pig],
            text=[usd(v, 0) for v in per_pig],
            textposition="outside",
            customdata=[usd_short(v) for v in months["profit_usd"]],
            hovertemplate="%{x}: %{text} per pig (%{customdata} total)<extra></extra>",
        )
    )
    bars.update_layout(height=320, margin={"t": 10, "b": 10, "l": 10, "r": 10}, showlegend=False)
    if bool(months["partial"].iloc[0]):
        st.caption(f"{labels[0]} is a partial month (the projection starts {today:%b %d}).")
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
