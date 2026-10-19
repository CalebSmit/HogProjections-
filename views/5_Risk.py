"""Risk: the odds of making money next year, and what a price floor would do."""

from datetime import date

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from hogproj.finance import breakeven
from hogproj.markets import seasonal_factors
from hogproj.outlook import project, synced
from hogproj.risk import RiskInputs, distribution_summary, estimate_hog_dynamics, simulate_profit
from hogproj.ui import ACCENT, BAD, current_plan, hog_index, usd, usd_short, verdict

st.title("Risk")
st.caption(
    "Runs 2,000 possible years of hog and corn prices, based on how the USDA hog index has "
    "actually moved, and shows the range of 12-month profit you could see."
)

idx, _, _ = hog_index()
factors = seasonal_factors(idx)
plan = synced(current_plan())
be = breakeven(plan.cost)["price_cwt_carcass"]
dyn = estimate_hog_dynamics(idx, factors)
weeks = 52
r = project(plan, factors, date.today()).iloc[:weeks]
hog_now = plan.cost.lean_hog_usd_per_cwt_carcass

with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    corn_vol = c1.slider(
        "Corn price uncertainty (% per year)",
        0,
        50,
        20,
        5,
        key="risk_corn_vol",
        help="How much corn could move over a year. About 20% is typical.",
    )
    use_floor = c2.toggle(
        "Add a hog price floor",
        key="risk_floor_on",
        help="Like USDA Livestock Risk Protection (LRP) or a put option: if the hog price falls "
        "below the floor you're paid the difference, in exchange for an up-front premium.",
    )
    floor = c2.number_input(
        "Floor ($/cwt carcass)",
        0.0,
        200.0,
        float(round(hog_now - 3)),
        1.0,
        key="risk_floor",
        disabled=not use_floor,
    )
    premium = c3.number_input(
        "Floor cost ($/cwt carcass)",
        0.0,
        30.0,
        2.5,
        0.25,
        key="risk_premium",
        disabled=not use_floor,
        help="Enter the premium from your LRP or options quote. 2.50 is only a placeholder.",
    )

risk = RiskInputs(
    corn_vol_annual=corn_vol / 100,
    floor_usd_per_cwt_carcass=floor if use_floor else None,
    premium_usd_per_cwt_carcass=premium if use_floor else 0.0,
)
out = simulate_profit(
    r["marketed_head"].to_numpy(),
    r["sold_lb_carcass"].to_numpy() / 100,
    r["hog_usd_per_cwt_carcass"].to_numpy(),
    plan.cost,
    dyn,
    risk,
)
plain = distribution_summary(out["profit"])
shown = distribution_summary(out["profit_with_floor"]) if use_floor else plain

chance = shown["p_profit"]


def odds(p: float) -> str:
    """Don't claim certainty from a simulation: 0.2% -> 'Under 1%'."""
    return "Under 1%" if p < 0.01 else "Over 99%" if p > 0.99 else f"{p:.0%}"


kind = "good" if chance >= 0.6 else "bad" if chance < 0.4 else "neutral"
detail = (
    f"In a bad year (1 in 10) the farm would {'lose' if shown['p10'] < 0 else 'make'} "
    f"{usd_short(abs(shown['p10']))}; in a good year (1 in 10) it would "
    f"{'make' if shown['p90'] >= 0 else 'lose'} {usd_short(abs(shown['p90']))}."
)
if use_floor:
    detail += (
        f" Without the floor: {odds(plain['p_profit'])} chance of profit and a bad year of "
        f"{usd_short(plain['p10'])}."
    )
verdict(kind, f"{odds(chance)} chance of making money over the next 12 months.", detail)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Chance of profit", odds(chance), border=True)
m2.metric(
    "Middle outcome",
    usd_short(shown["p50"]),
    help="Half the simulated years do better, half do worse.",
    border=True,
)
m3.metric("Bad year (1 in 10)", usd_short(shown["p10"]), border=True)
m4.metric("Good year (1 in 10)", usd_short(shown["p90"]), border=True)

left, right = st.columns(2)
with left, st.container(border=True):
    st.markdown("**Where hog prices could go**")
    hog = out["hog_paths"]
    dates = r["date"]
    pct = {q: np.percentile(hog, q, axis=0) for q in (10, 25, 50, 75, 90)}
    fan = go.Figure()
    fan.add_scatter(x=dates, y=pct[90], line={"width": 0}, showlegend=False, hoverinfo="skip")
    fan.add_scatter(
        x=dates,
        y=pct[10],
        fill="tonexty",
        fillcolor="rgba(31,111,80,0.12)",
        line={"width": 0},
        name="8 in 10 years",
    )
    fan.add_scatter(x=dates, y=pct[75], line={"width": 0}, showlegend=False, hoverinfo="skip")
    fan.add_scatter(
        x=dates,
        y=pct[25],
        fill="tonexty",
        fillcolor="rgba(31,111,80,0.25)",
        line={"width": 0},
        name="Half of years",
    )
    fan.add_scatter(x=dates, y=pct[50], name="Middle", line={"color": ACCENT, "width": 3})
    fan.add_hline(y=be, line_dash="dot", line_color=BAD, annotation_text="breakeven")
    if use_floor:
        fan.add_hline(y=floor, line_dash="dash", line_color="#1f4e79", annotation_text="floor")
    fan.update_layout(
        height=340,
        margin={"t": 10, "b": 10, "l": 10, "r": 10},
        yaxis_title="$/cwt carcass",
        legend={"orientation": "h", "y": -0.15},
        hovermode="x unified",
    )
    st.plotly_chart(fan, width="stretch")
with right, st.container(border=True):
    st.markdown("**Range of 12-month profit**")
    hist = go.Figure()
    hist.add_histogram(
        x=out["profit"],
        name="No floor",
        marker_color="rgba(138,154,147,0.6)",
        nbinsx=40,
    )
    if use_floor:
        hist.add_histogram(
            x=out["profit_with_floor"],
            name="With floor",
            marker_color="rgba(31,111,80,0.6)",
            nbinsx=40,
        )
    hist.add_vline(x=0, line_color=BAD, line_dash="dot", annotation_text="breakeven")
    hist.update_layout(
        barmode="overlay",
        height=340,
        margin={"t": 10, "b": 10, "l": 10, "r": 10},
        xaxis_title="12-month profit ($)",
        yaxis_title="Simulated years",
        legend={"orientation": "h", "y": -0.2},
    )
    st.plotly_chart(hist, width="stretch")

with st.expander("How this works"):
    st.markdown(
        f"""
- **Expected path:** today's hog price ({usd(hog_now)}/cwt) following the usual seasonal
  pattern, the same path the Overview uses.
- **Hog price surprises** are fitted to {dyn.weeks_used} weeks of USDA index history with the
  seasonal pattern removed: a typical week moves **{dyn.sigma:.1%}**, and a surprise fades by
  about **{1 - dyn.phi:.0%} a week**, so prices drift back toward the seasonal path.
- **Corn** moves randomly by about {corn_vol}% a year, independent of hogs.
- Herd size, productivity and non-feed costs are held at your inputs. Disease, export shocks
  and futures-market views aren't included.
- The floor pays (floor − hog price) on every cwt sold in a week when hogs are below it.
  Real LRP pays on an ending value over a chosen period, so treat this as a guide and use
  your actual quote for the premium.
"""
    )
    st.caption(
        f"{risk.n_paths:,} simulated years, fixed seed {risk.seed} so results don't jump "
        f"between visits. Breakeven: {usd(be)}/cwt carcass."
    )
