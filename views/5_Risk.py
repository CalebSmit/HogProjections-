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
    ACCENT,
    PAGE,
    REFERENCE,
    assumption_bar,
    chart,
    chart_title,
    current_plan,
    end_tag,
    hero,
    hog_index,
    masthead,
    md,
    quote,
    ref_line,
    source_note,
    stat_strip,
    tone_of,
    usd,
    usd_short,
)

idx, _, _ = hog_index()
factors = seasonal_factors(idx)
plan = synced(current_plan())
be = breakeven(plan.cost)["price_cwt_carcass"]
dyn = estimate_hog_dynamics(idx, factors)
weeks = 52
r = project(plan, factors, date.today()).iloc[:weeks]
hog_now = plan.cost.lean_hog_usd_per_cwt_carcass
ss = st.session_state

head = st.empty()
with assumption_bar("risk"):
    with st.popover(
        f"Corn uncertainty · {ss.get('risk_corn_vol', 20)}% a year", icon=":material/grass:"
    ):
        corn_vol = st.slider(
            "Corn, % per year",
            0,
            50,
            20,
            5,
            key="risk_corn_vol",
            help="How much corn could move over a year. About 20% is typical.",
        )
    floor_on = bool(ss.get("risk_floor_on", False))
    floor_label = (
        f"Price floor · {usd(float(ss.get('risk_floor', round(hog_now - 3))), 0)} for "
        f"{usd(float(ss.get('risk_premium', 2.5)))}"
        if floor_on
        else "Price floor · off"
    )
    with st.popover(md(floor_label), icon=":material/shield:"):
        use_floor = st.toggle(
            "Add a hog price floor",
            key="risk_floor_on",
            help="Like USDA Livestock Risk Protection (LRP) or a put option: below the floor "
            "you're paid the difference, for an up-front premium.",
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
    """Don't claim certainty from a simulation: 0.2% -> 'under 1%'."""
    return "under 1%" if p < 0.01 else "over 99%" if p > 0.99 else f"{p:.0%}"


chance = shown["p_profit"]
end_prices = out["hog_paths"][:, -1]
with head.container():
    masthead(
        f"There's {odds(chance)} chance of a profitable year at today's prices.",
        f"Across {risk.n_paths:,} simulated years of hog and corn prices, the middle outcome is "
        f"{usd_short(shown['p50'])}; a bad year (1 in 10) is {usd_short(shown['p10'])}."
        + (
            f" Without the floor the chance would be {odds(plain['p_profit'])}."
            if use_floor
            else ""
        ),
        kicker="Risk · next 12 months",
    )

st.space("small")
with hero():
    quote(
        "Chance of profit",
        odds(chance).capitalize(),
        "next 12 months",
        "Likely loss" if chance < 0.4 else ("Likely profit" if chance >= 0.6 else "Toss-up"),
        "bad" if chance < 0.4 else ("good" if chance >= 0.6 else "caution"),
        f"Hogs need {usd(be)}/cwt · typical weekly price move ±{dyn.sigma:.1%}",
    )
    stat_strip(
        [
            ("Middle outcome", usd_short(shown["p50"]), "half of years do better", "neutral"),
            ("Bad year · 1 in 10", usd_short(shown["p10"]), "", tone_of(shown["p10"])),
            ("Good year · 1 in 10", usd_short(shown["p90"]), "", tone_of(shown["p90"])),
            (
                "Hog price in 12 months",
                usd(float(np.median(end_prices))),
                f"8 in 10: {usd(float(np.percentile(end_prices, 10)), 0)}–"
                f"{usd(float(np.percentile(end_prices, 90)), 0)}",
                "neutral",
            ),
        ]
    )
    st.space("small")
    p90 = float(np.percentile(out["hog_paths"], 90, axis=0).max())
    chart_title(
        "Hog prices stay below breakeven in 9 of 10 simulated years"
        if p90 < be
        else "Where hog prices could go over the next 12 months",
        "Lean hog, $/cwt carcass · middle path with the middle half and 8 in 10 years shaded",
    )
    hog = out["hog_paths"]
    dates = r["date"]
    pct = {q: np.percentile(hog, q, axis=0) for q in (10, 25, 50, 75, 90)}
    fan = go.Figure()
    for lo_q, hi_q, alpha in [(10, 90, 0.10), (25, 75, 0.17)]:
        fan.add_scatter(
            x=dates, y=pct[hi_q], mode="lines", line={"width": 0}, hoverinfo="skip",
            showlegend=False,
        )  # fmt: skip
        fan.add_scatter(
            x=dates,
            y=pct[lo_q],
            mode="lines",
            fill="tonexty",
            fillcolor=f"rgba(31,92,69,{alpha})",
            line={"width": 0},
            hoverinfo="skip",
            showlegend=False,
        )
    fan.add_scatter(
        x=dates,
        y=pct[50],
        mode="lines",
        line={"color": ACCENT, "width": 2.25},
        hovertemplate="%{x|%b %d}: middle $%{y:.2f}<extra></extra>",
        showlegend=False,
    )
    ref_line(fan, be, f"Breakeven {usd(be)}")
    if use_floor:
        ref_line(fan, floor, f"Floor {usd(floor)}", "#1f4e8c")
    end_tag(fan, dates.iloc[-1], float(pct[50][-1]), usd(float(pct[50][-1])), ACCENT)
    fan.update_yaxes(tickprefix="$")
    fan.update_xaxes(tickformat="%b %Y")
    fan.update_layout(margin={"l": 4, "r": 64, "t": 8, "b": 4})
    chart(fan, 340)
    source_note(
        f"model fitted to {dyn.weeks_used} weeks of USDA LM_HG201 index history",
        f"price surprises fade about {1 - dyn.phi:.0%} a week toward the seasonal path; corn moves "
        f"about {corn_vol}% a year, independent of hogs",
    )

st.space("medium")
chart_title(
    "Range of 12-month profit",
    "Simulated years by outcome" + (" · green: with the floor" if use_floor else ""),
)
hist = go.Figure()
hist.add_histogram(
    x=out["profit"],
    marker={"color": "rgba(124,132,126,0.55)", "line": {"color": PAGE, "width": 1}},
    nbinsx=44,
    hovertemplate="%{x}: %{y} years<extra></extra>",
    name="No floor",
)
if use_floor:
    hist.add_histogram(
        x=out["profit_with_floor"],
        marker={"color": "rgba(23,138,106,0.55)", "line": {"color": PAGE, "width": 1}},
        nbinsx=44,
        hovertemplate="%{x}: %{y} years<extra></extra>",
        name="With floor",
    )
hist.add_vline(x=0, line={"color": REFERENCE, "width": 1.25, "dash": "dot"})
hist.add_annotation(
    x=0, y=1, yref="paper", text="Breakeven", showarrow=False, xanchor="left", xshift=6,
    yanchor="top", font={"size": 11, "color": REFERENCE},
)  # fmt: skip
hist.update_xaxes(tickformat="$~s")
hist.update_yaxes(title="Simulated years")
hist.update_layout(barmode="overlay", hovermode="closest", showlegend=use_floor)
chart(hist, 280, on=PAGE)
source_note(
    f"{risk.n_paths:,} simulated years, fixed seed so results don't change between visits",
    "the floor pays (floor − price) on every cwt sold in a week below it; real LRP pays on an "
    "ending value, so use your actual quote for the premium",
)
