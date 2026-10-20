"""Hedging: the book of pigs on feed, what's locked in, what's open, and what your rule says."""

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj.book import Hedge, business_days_since, by_contract, hedge_rule, positions, what_if
from hogproj.crush import contract_label, margin_rank
from hogproj.ui import (
    ACCENT,
    HISTORY,
    INK,
    MUTED,
    PAGE,
    Tone,
    assumption_bar,
    chart,
    chart_title,
    chip,
    crush_book,
    end_tag,
    hero,
    lh_key,
    masthead,
    md,
    quote,
    rule,
    source_note,
    stat_strip,
    table,
    tone_of,
    usd,
    usd_short,
)

ss = st.session_state
today = date.today()
book = crush_book()
c = book.c
on_feed = pd.DataFrame(book.rows[book.rows["status"] == "on feed"])
history = book.rows[book.rows["status"] == "sold"]["margin_usd"].to_numpy(dtype=float)


def key(k: tuple[int, int], what: str) -> str:
    return f"w2f_hedge_{k[0]}_{k[1]:02d}_{what}"


def cur(name: str, default: float) -> float:
    v = ss.get(name)
    return float(default if v is None else v)


hedged_now = [k for k in book.contracts if cur(key(k, "pct"), 0) > 0]
asof = ss.get("w2f_asof")
stale = asof is not None and business_days_since(asof, today) > 3

# --- Inputs ---------------------------------------------------------------------------------
head = st.empty()
with assumption_bar("hedge"):
    with st.popover(
        "Contract prices · " + (f"as of {asof:%b %d}" if asof else "seasonal estimate")
    ):
        st.caption(
            "Lean hog futures, $/cwt. Shared with Wean to finish. Enter the latest settlements "
            "and their date; prices older than three business days are flagged."
        )
        st.date_input("Prices as of", value=None, key="w2f_asof", format="MM/DD/YYYY")
        cols = st.columns(2)
        for i, k in enumerate(book.contracts):
            cols[i % 2].number_input(contract_label(k), 0.0, 250.0, book.model[k], 0.25,
                                     key=lh_key(k))  # fmt: skip
    with st.popover(
        md(
            "Hog hedges · "
            + (", ".join(f"{contract_label(k)} {cur(key(k, 'pct'), 0):.0f}%" for k in hedged_now)
               or "none")
        )
    ):  # fmt: skip
        st.caption("Share of each contract's pigs already sold forward (futures, forward "
                   "contract, LRP floor at its strike) and the price locked.")  # fmt: skip
        for k in book.contracts:
            a, b = st.columns([1, 1])
            a.number_input(f"{contract_label(k)} hedged (%)", 0.0, 100.0, 0.0, 5.0,
                           key=key(k, "pct"))  # fmt: skip
            b.number_input(f"{contract_label(k)} price ($/cwt)", 0.0, 250.0, book.futures[k],
                           0.25, key=key(k, "px"))  # fmt: skip
    with st.popover(
        f"Feed hedges · corn {cur('w2f_corn_hedge_pct', 0):.0f}% · SBM "
        f"{cur('w2f_sbm_hedge_pct', 0):.0f}%"
    ):
        a, b = st.columns(2)
        a.number_input("Corn hedged (%)", 0.0, 100.0, 0.0, 5.0, key="w2f_corn_hedge_pct")
        b.number_input("Corn price ($/bu)", 0.0, 20.0, c.corn_usd_per_bu, 0.05,
                       key="w2f_corn_hedge_px")  # fmt: skip
        a.number_input("SBM hedged (%)", 0.0, 100.0, 0.0, 5.0, key="w2f_sbm_hedge_pct")
        b.number_input("SBM price ($/ton)", 0.0, 1000.0, c.sbm_usd_per_ton, 5.0,
                       key="w2f_sbm_hedge_px")  # fmt: skip
    with st.popover(f"Pigs placed · {cur('w2f_head_week', 1000):,.0f}/week"):
        st.number_input("Pigs placed per week", 0.0, 1_000_000.0, 1000.0, 100.0,
                        key="w2f_head_week", help="Used to size the book in dollars.")  # fmt: skip
    with st.popover(
        f"Hedge rule · {cur('w2f_rule_trigger', 75):.0f}th pct → {cur('w2f_rule_target', 50):.0f}%"
    ):
        st.caption("Your rule, not advice: when a contract's projected margin ranks at or above "
                   "the trigger against every placement since 2020, hedge the target "
                   "share.")  # fmt: skip
        st.slider("Trigger percentile", 50, 95, 75, 5, key="w2f_rule_trigger")
        st.slider("Target hedged (%)", 10, 100, 50, 10, key="w2f_rule_target")

# --- Numbers ---------------------------------------------------------------------------------
hog_hedges = {
    k: Hedge(share=cur(key(k, "pct"), 0) / 100, price=cur(key(k, "px"), book.futures[k]))
    for k in book.contracts
}
corn_h = Hedge(share=cur("w2f_corn_hedge_pct", 0) / 100,
               price=cur("w2f_corn_hedge_px", c.corn_usd_per_bu))  # fmt: skip
sbm_h = Hedge(share=cur("w2f_sbm_hedge_pct", 0) / 100,
              price=cur("w2f_sbm_hedge_px", c.sbm_usd_per_ton))  # fmt: skip
per_week = cur("w2f_head_week", 1000)
pos = positions(on_feed, c, book.futures, hog_hedges, per_week, corn_h, sbm_h)
summary = by_contract(pos)
trigger, target = cur("w2f_rule_trigger", 75), cur("w2f_rule_target", 50) / 100

if pos.empty:
    with head.container():
        masthead("No pigs on feed in the data.", "USDA weaned pig prices are missing.",
                 kicker="Hedging")  # fmt: skip
    st.stop()

total = float(summary["margin_usd"].sum())
pigs = float(summary["head"].sum())
exposure = float(summary["exposure_usd"].sum())
hog_share = 1 - exposure / float((pos["head"] * pos["cwt"]).sum())
summary["rank"] = [
    margin_rank(float(r["unhedged_margin_usd"]) / float(r["head"]), history)
    for r in summary.to_dict("records")
]
best = summary.loc[summary["rank"].idxmax()]

with head.container():
    if hog_share > 0:
        title = (f"Pigs on feed project {usd_short(total)}, with {hog_share:.0%} of the hogs "
                 "locked in.")  # fmt: skip
    else:
        title = f"{pigs:,.0f} pigs on feed project {usd_short(total)}, none of it hedged."
    masthead(
        title,
        f"Each $1/cwt move in lean hogs changes the book by {usd_short(exposure)}. "
        f"{best['label']} pigs have the best margin versus history ({best['rank']:.0f}th "
        "percentile).",
        kicker="Hedging · pigs on feed",
        meta=[
            chip("Contract prices stale", "bad", "Prices are more than three business days old.")
            if stale
            else chip("Contract prices: seasonal estimate", "caution",
                      "Enter today's futures under Contract prices.")
            if not book.user_set
            else chip(f"Contract prices as of {asof:%b %d}" if asof else "Your contract prices",
                      "good")
        ],
    )  # fmt: skip

st.space("small")

with hero("hedge"):
    left, right = st.columns([1.15, 1.2], gap="large")
    with left:
        quote(
            "Projected margin on pigs on feed",
            usd_short(total),
            f"on {pigs:,.0f} pigs",
            f"{usd(total / pigs)} a pig",
            tone_of(total),
            f"{len(pos)} weeks placed, selling {pd.Timestamp(pos['sold'].min()):%b %d} to "
            f"{pd.Timestamp(pos['sold'].max()):%b %d, %Y}",
        )
        stats: list[tuple[str, str, str, Tone]] = [
            ("Hogs hedged", f"{hog_share:.0%}", "of pigs on feed", "neutral"),
            ("$1/cwt move", usd_short(exposure), "change in the book", "neutral"),
        ]
        if corn_h.share or sbm_h.share:
            stats[0] = ("Hedged", f"{hog_share:.0%} hogs",
                        f"corn {corn_h.share:.0%} · SBM {sbm_h.share:.0%}", "neutral")  # fmt: skip
        stat_strip(stats)
    with right:
        chart_title(
            "Margin per pig by the contract it sells into",
            "Open: at today's contract price · with hedges: your hedges applied · label: rank vs "
            "history",
        )
        fig = go.Figure()
        any_hedge = hog_share > 0 or corn_h.share > 0 or sbm_h.share > 0
        if any_hedge:
            fig.add_bar(x=summary["label"], y=summary["unhedged_margin_usd"] / summary["head"],
                        name="Open", marker={"color": "#c9c3b6", "cornerradius": 3},
                        hovertemplate="%{x} open: %{y:$,.2f}/pig<extra></extra>")  # fmt: skip
        fig.add_bar(x=summary["label"], y=summary["margin_usd_per_head"], name="With hedges",
                    marker={"color": [ACCENT if v >= 0 else "#c8453a"
                                      for v in summary["margin_usd_per_head"]],
                            "cornerradius": 3},
                    text=[f"{r:.0f}th pct" for r in summary["rank"]], textposition="outside",
                    textfont={"size": 11, "color": MUTED}, cliponaxis=False,
                    hovertemplate="%{x} with hedges: %{y:$,.2f}/pig<extra></extra>")  # fmt: skip
        fig.add_hline(y=0, line={"color": INK, "width": 1})
        fig.update_yaxes(tickprefix="$")
        fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08, hovermode="closest",
                          showlegend=any_hedge,
                          legend={"orientation": "h", "y": 1.08, "x": 0})  # fmt: skip
        chart(fig, 290)
    source_note(
        "your contract prices and hedges; USDA weaned pig prices",
        "labels: each contract's open margin ranked against every placement since 2020",
    )

st.space("medium")

chart_title(
    "What your rule says, contract by contract",
    f"Trigger: {trigger:.0f}th percentile · target {target:.0%} hedged",
)
rows = []
for r in summary.to_dict("records"):
    tone, sentence = hedge_rule(float(r["rank"]), trigger, target, float(r["hedged_share"]))
    rows.append([r["label"], f"{r['head']:,.0f}", usd(r["market_usd_per_cwt"]),
                 f"{r['hedged_share']:.0%}", usd(r["margin_usd_per_head"]),
                 usd_short(r["margin_usd"]), sentence])  # fmt: skip
table(["Contract", "Pigs", "Price $/cwt", "Hedged", "Margin/pig", "Total", "Rule"], rows,
      emphasis_col=3)  # fmt: skip
source_note("model", "ranks use the open margin, so they show the market, not your hedges")

rule()

left, right = st.columns([1.3, 1], gap="large")
with left:
    shifts = [float(x) for x in np.arange(-15, 15.01, 1.0)]
    w = what_if(pos, shifts)
    chart_title(
        "Hedges flatten the swing" if hog_share > 0 else "Unhedged, the book moves with hogs",
        "Book margin if every lean hog contract moves by this much · $/cwt",
    )
    wf = go.Figure()
    if hog_share > 0:
        wf.add_scatter(x=w["shift"], y=w["without_hedges_usd"], mode="lines", name="Without hedges",
                       line={"color": HISTORY, "width": 1.5, "dash": "dot"},
                       hovertemplate="%{x:+.0f}/cwt: %{y:$,.0f}"
                       "<extra>without hedges</extra>")  # fmt: skip
        end_tag(wf, 15, float(w["without_hedges_usd"].iloc[-1]), "Without", HISTORY)
    wf.add_scatter(x=w["shift"], y=w["with_hedges_usd"], mode="lines", name="With hedges",
                   line={"color": ACCENT, "width": 2.2},
                   hovertemplate="%{x:+.0f}/cwt: %{y:$,.0f}<extra>with hedges</extra>")  # fmt: skip
    end_tag(wf, 15, float(w["with_hedges_usd"].iloc[-1]),
            "With hedges" if hog_share > 0 else "Book", ACCENT)  # fmt: skip
    wf.add_hline(y=0, line={"color": INK, "width": 1})
    wf.add_vline(x=0, line={"color": MUTED, "width": 1, "dash": "dot"})
    wf.update_xaxes(tickprefix="$", title="change in lean hog futures", range=[-15.5, 15.5])
    wf.update_yaxes(tickformat="$~s")
    wf.update_layout(showlegend=False, margin={"l": 4, "r": 90, "t": 8, "b": 4})
    chart(wf, 300, on=PAGE)
    source_note("model", "feed hedges and costs held constant")
with right:
    chart_title("How this works", "")
    st.markdown(
        f"""
- **Pigs on feed** are every weekly USDA placement in the last {c.days_on_feed} days, at
  {per_week:,.0f} pigs a week, each priced against the lean hog contract it sells into.
- **Hedged share** of a contract earns your hedge price; the rest earns today's contract price.
  An LRP floor or put can be entered at its strike if prices are below it.
- **Ranks** compare each contract's open margin per pig with every placement sold since 2020
  (Crush history). The rule is yours — set the trigger and target above.
- It shows the position; your marketing advisor and lender make the call.
"""
    )
