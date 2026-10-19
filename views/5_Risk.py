"""Risk: the odds of making money next year, and what a price floor would do."""

from datetime import date

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from hogproj.finance import breakeven
from hogproj.markets import seasonal_factors
from hogproj.outlook import project, synced
from hogproj.risk import RiskInputs, distribution_summary, estimate_hog_dynamics, simulate_profit
from hogproj.ui import (
    REFERENCE,
    SERIES,
    card,
    chart,
    current_plan,
    hog_index,
    insight,
    page_header,
    section,
    usd,
    usd_short,
)

page_header(
    "Risk",
    "The range of 12-month profit across 2,000 simulated years of hog and corn prices.",
    eyebrow="Decisions",
)

idx, _, _ = hog_index()
factors = seasonal_factors(idx)
plan = synced(current_plan())
be = breakeven(plan.cost)["price_cwt_carcass"]
dyn = estimate_hog_dynamics(idx, factors)
weeks = 52
r = project(plan, factors, date.today()).iloc[:weeks]
hog_now = plan.cost.lean_hog_usd_per_cwt_carcass

with st.sidebar:
    st.header("Price uncertainty")
    corn_vol = st.slider(
        "Corn, % per year",
        0,
        50,
        20,
        5,
        key="risk_corn_vol",
        help="How much corn could move over a year. About 20% is typical.",
    )
    st.header("Price protection")
    use_floor = st.toggle(
        "Add a hog price floor",
        key="risk_floor_on",
        help="Like USDA Livestock Risk Protection (LRP) or a put option: below the floor you're "
        "paid the difference, for an up-front premium.",
    )
    floor = st.number_input(
        "Floor, $/cwt carcass",
        0.0,
        200.0,
        float(round(hog_now - 3)),
        1.0,
        key="risk_floor",
        disabled=not use_floor,
    )
    premium = st.number_input(
        "Premium, $/cwt carcass",
        0.0,
        30.0,
        2.5,
        0.25,
        key="risk_premium",
        disabled=not use_floor,
        help="Use the premium from your LRP or options quote. 2.50 is a placeholder.",
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


def odds(p: float) -> str:
    """Don't claim certainty from a simulation: 0.2% -> 'Under 1%'."""
    return "Under 1%" if p < 0.01 else "Over 99%" if p > 0.99 else f"{p:.0%}"


chance = shown["p_profit"]
tone = "good" if chance >= 0.6 else "bad" if chance < 0.4 else "caution"
status = {"good": "Likely profitable", "bad": "Likely loss", "caution": "Toss-up"}[tone]
end_prices = out["hog_paths"][:, -1]
facts = [
    ("Price needed", f"{usd(be)}/cwt"),
    ("Hog price in 12 months, middle", f"{usd(float(np.median(end_prices)))}/cwt"),
    (
        "8 in 10 years between",
        f"{usd(float(np.percentile(end_prices, 10)), 0)}–"
        f"{usd(float(np.percentile(end_prices, 90)), 0)}",
    ),
    ("Typical weekly price move", f"±{dyn.sigma:.1%}"),
]
if use_floor:
    facts.append(("Chance without floor", odds(plain["p_profit"])))
insight(tone, status, f"{odds(chance)} chance of making money over the next 12 months.", facts)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Chance of profit", odds(chance), height="stretch")
m2.metric(
    "Middle outcome",
    usd_short(shown["p50"]),
    help="Half the simulated years do better, half worse.",
    height="stretch",
)
m3.metric("Bad year, 1 in 10", usd_short(shown["p10"]), height="stretch")
m4.metric("Good year, 1 in 10", usd_short(shown["p90"]), height="stretch")
st.space("small")

left, right = st.columns(2, gap="medium")
with left, card("fan"):
    p90_end = float(np.percentile(out["hog_paths"][:, -1], 90))
    section(
        "Hog prices stay below breakeven in 9 of 10 years"
        if p90_end < be
        else "Where hog prices could go",
        "Lean hog, $/cwt carcass · shaded: middle half and 8 in 10 simulated years",
    )
    hog = out["hog_paths"]
    dates = r["date"]
    pct = {q: np.percentile(hog, q, axis=0) for q in (10, 25, 50, 75, 90)}
    fan = go.Figure()
    for lo_q, hi_q, alpha in [(10, 90, 0.10), (25, 75, 0.20)]:
        fan.add_scatter(x=dates, y=pct[hi_q], line={"width": 0}, hoverinfo="skip", showlegend=False)
        fan.add_scatter(
            x=dates,
            y=pct[lo_q],
            fill="tonexty",
            fillcolor=f"rgba(42,120,214,{alpha})",
            line={"width": 0},
            hoverinfo="skip",
            showlegend=False,
        )
    fan.add_scatter(
        x=dates,
        y=pct[50],
        line={"color": SERIES[0], "width": 2.25},
        hovertemplate="%{x|%b %d}: middle $%{y:.2f}<extra></extra>",
        showlegend=False,
    )
    fan.add_hline(y=be, line={"color": REFERENCE, "width": 1, "dash": "dash"})
    fan.add_annotation(
        x=dates.iloc[-1], y=be, text=f"Breakeven {usd(be)}", showarrow=False,
        xanchor="right", yanchor="bottom", font={"size": 11, "color": REFERENCE},
    )  # fmt: skip
    if use_floor:
        fan.add_hline(y=floor, line={"color": "#1f4e8c", "width": 1.25})
        fan.add_annotation(
            x=dates.iloc[-1], y=floor, text=f"Floor {usd(floor)}", showarrow=False,
            xanchor="right", yanchor="top", font={"size": 11, "color": "#1f4e8c"},
        )  # fmt: skip
    fan.update_yaxes(tickprefix="$")
    fan.update_xaxes(tickformat="%b %Y")
    chart(fan, 320)
with right, card("hist"):
    section(
        "Range of 12-month profit",
        "Simulated years by outcome" + (" · green: with the floor" if use_floor else ""),
    )
    hist = go.Figure()
    hist.add_histogram(
        x=out["profit"],
        name="No floor",
        marker={"color": "rgba(139,144,154,0.55)", "line": {"color": "white", "width": 1}},
        nbinsx=40,
        hovertemplate="%{x}: %{y} years<extra></extra>",
    )
    if use_floor:
        hist.add_histogram(
            x=out["profit_with_floor"],
            name="With floor",
            marker={"color": "rgba(23,138,106,0.55)", "line": {"color": "white", "width": 1}},
            nbinsx=40,
            hovertemplate="%{x}: %{y} years<extra></extra>",
        )
    hist.add_vline(x=0, line={"color": REFERENCE, "width": 1, "dash": "dash"})
    hist.update_xaxes(tickformat="$~s", title="12-month profit")
    hist.update_yaxes(title="Simulated years")
    hist.update_layout(barmode="overlay", hovermode="closest", showlegend=use_floor)
    chart(hist, 320)

with st.expander("How this works", icon=":material/info:"):
    st.markdown(
        f"""
- **Expected path:** today's hog price ({usd(hog_now)}/cwt) following the usual seasonal
  pattern, the same path the Overview uses.
- **Price surprises** are fitted to {dyn.weeks_used} weeks of USDA index history with the
  seasonal pattern removed: a typical week moves **{dyn.sigma:.1%}**, and a surprise fades by
  about **{1 - dyn.phi:.0%} a week**, so prices drift back toward the seasonal path.
- **Corn** moves randomly by about {corn_vol}% a year, independent of hogs.
- Herd size, productivity and non-feed costs are held at your inputs. Disease, export shocks
  and futures-market views aren't included.
- The floor pays (floor − hog price) on every cwt sold in a week when hogs are below it. Real
  LRP pays on an ending value over a chosen period, so treat this as a guide and use your
  actual quote for the premium.
"""
    )
st.markdown(
    f'<div class="hp-foot">{risk.n_paths:,} simulated years with a fixed seed, so results '
    f"don't change between visits. Breakeven {usd(be).replace('$', '&#36;')}/cwt carcass.</div>",
    unsafe_allow_html=True,
)
