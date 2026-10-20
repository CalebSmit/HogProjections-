"""Hedging: the book of pigs on feed, what's locked in, what's open, and what your rule says."""

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj import board as brd
from hogproj.book import (
    RULE_MODES,
    Hedge,
    business_days_since,
    by_contract,
    hedge_rule,
    positions,
    what_if,
)
from hogproj.crush import contract_label, margin_rank
from hogproj.text import day, ordinal
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
    crush_workbook,
    end_tag,
    excel_button,
    futures_upload,
    head_per_week,
    hedge_rule_from_state,
    hero,
    lh_key,
    live_number,
    margin_board,
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
    user_value,
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
    return user_value(name, default)


corn_fut0 = round(book.corn_cash - book.corn_basis, 2)  # nearby futures (cash if no curve)
# Only contracts that pigs on feed sell into; later ones are priced on Wean to finish.
feed_contracts = [k for k in book.contracts if contract_label(k) in set(on_feed["priced_on"])]
head0 = head_per_week()  # Herd flow's weaned pigs per week, until you enter your own
hedged_now = [k for k in feed_contracts if cur(key(k, "pct"), 0) > 0]
asof = ss.get("w2f_asof")
stale = asof is not None and business_days_since(asof, today) > 3

# --- Inputs ---------------------------------------------------------------------------------
head = st.empty()
with assumption_bar("hedge"):
    with st.popover(
        "Contract prices · "
        + (f"as of {day(asof, '%b %d')}" if asof else book.price_source.lower())
    ):
        st.caption(
            "Lean hog futures, $/cwt. Shared with Wean to finish. Enter the latest settlements "
            "and their date; prices older than three business days are flagged."
        )
        futures_upload()
        st.date_input("Prices as of", value=None, key="w2f_asof", format="MM/DD/YYYY")
        cols = st.columns(2)
        for i, k in enumerate(feed_contracts):
            live_number(cols[i % 2], contract_label(k), 0.0, 250.0, book.model[k], 0.25,
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
        for k in feed_contracts:
            a, b = st.columns([1, 1])
            a.number_input(f"{contract_label(k)} hedged (%)", 0.0, 100.0, 0.0, 5.0,
                           key=key(k, "pct"))  # fmt: skip
            live_number(b, f"{contract_label(k)} price ($/cwt)", 0.0, 250.0, book.futures[k],
                           0.25, key=key(k, "px"))  # fmt: skip
    with st.popover(
        f"Feed hedges · corn {cur('w2f_corn_hedge_pct', 0):.0f}% · SBM "
        f"{cur('w2f_sbm_hedge_pct', 0):.0f}%"
    ):
        a, b = st.columns(2)
        a.number_input("Corn hedged (%)", 0.0, 100.0, 0.0, 5.0, key="w2f_corn_hedge_pct")
        live_number(b, "Corn hedge price (CBOT, $/bu)", 0.0, 20.0, corn_fut0, 0.05,
                    key="w2f_corn_hedge_px",
                    help=f"Futures price locked. Your Iowa basis ({signed(book.corn_basis)}) is "
                    "added to get the delivered cost.")  # fmt: skip
        a.number_input("SBM hedged (%)", 0.0, 100.0, 0.0, 5.0, key="w2f_sbm_hedge_pct")
        live_number(b, "SBM price ($/ton)", 0.0, 1000.0, c.sbm_usd_per_ton, 5.0,
                       key="w2f_sbm_hedge_px")  # fmt: skip
    with st.popover(f"Pigs placed · {cur('w2f_head_week', head0):,.0f}/week"):
        live_number(st, "Pigs placed per week", 0.0, 1_000_000.0, head0, 10.0,
                    key="w2f_head_week",
                    help="Starts at Herd flow's weaned pigs per week. Sizes the book.")  # fmt: skip
    with st.popover(hedge_rule_from_state().label()):
        st.caption(
            "Your rule, not advice. Pick what triggers it: a margin that ranks high against "
            "every placement since 2020, or a margin per pig you're happy to lock in."
        )
        first = "w2f_rule_mode" not in st.session_state
        st.segmented_control("Rule", list(RULE_MODES), default="rank" if first else None,
                             key="w2f_rule_mode",
                             format_func=lambda m: RULE_MODES[m], required=True)  # fmt: skip
        mode = st.session_state.get("w2f_rule_mode") or "rank"
        if mode == "rank":
            st.slider("Trigger percentile", 50, 95, 75, 5, key="w2f_rule_trigger")
        elif mode == "margin":
            st.number_input("Hedge when margin is at least ($/pig)", -50.0, 100.0, 10.0, 1.0,
                            key="w2f_rule_margin")  # fmt: skip
        if mode != "off":
            st.slider("Target hedged (%)", 10, 100, 50, 10, key="w2f_rule_target")

# --- Numbers ---------------------------------------------------------------------------------
hog_hedges = {
    k: Hedge(share=cur(key(k, "pct"), 0) / 100, price=cur(key(k, "px"), book.futures[k]))
    for k in feed_contracts
}
corn_h = Hedge(share=cur("w2f_corn_hedge_pct", 0) / 100,
               price=cur("w2f_corn_hedge_px", corn_fut0) + book.corn_basis)  # fmt: skip
sbm_h = Hedge(share=cur("w2f_sbm_hedge_pct", 0) / 100,
              price=cur("w2f_sbm_hedge_px", c.sbm_usd_per_ton))  # fmt: skip
per_week = cur("w2f_head_week", head0)
pos = positions(on_feed, c, book.futures, hog_hedges, per_week, corn_h, sbm_h)
summary = by_contract(pos)
hrule = hedge_rule_from_state()
trigger, target = hrule.trigger, hrule.target

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
    action = masthead(
        title,
        f"Each $1/cwt move in lean hogs changes the book by {usd_short(exposure)}. "
        f"Of pigs on feed, {best['label']} ones have the best margin versus history "
        f"({ordinal(best['rank'])} percentile).",
        kicker="Hedging · pigs on feed",
        meta=[
            chip("Contract prices stale", "bad", "Prices are more than three business days old.")
            if stale
            else chip(f"Contract prices: {book.price_source.lower()}", "caution",
                      "Enter today's futures under Contract prices.")
            if not book.user_set
            else chip(f"Contract prices as of {day(asof, '%b %d')}" if asof
                      else "Your contract prices",
                      "good")
        ],
    )  # fmt: skip

    with action:
        st.download_button(
            "Crush workbook (Excel)",
            crush_workbook,  # built on click
            f"wean_pig_crush_{today:%Y-%m-%d}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            width="stretch",
            help="Pigs on feed, contract prices and your hedges as a live Excel workbook.",
            on_click="ignore",
        )
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
                    text=[f"{ordinal(r)} pct" for r in summary["rank"]], textposition="outside",
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

# --- Forward margin board: pigs not placed yet ---------------------------------------------------
fb = margin_board()
if not fb.empty:
    ranks, margins = brd.trend(date.today(), fb)
    top = fb.loc[fb["rank"].idxmax()]
    was = ranks.loc[top["contract"], "2 wk ago"]
    moved = (f", {'up' if top['rank'] >= was else 'down'} from {ordinal(was)} two weeks ago"
             if pd.notna(was) else "")  # fmt: skip
    chart_title(
        f"Pigs placed {top['placed_from']:%b} {top['placed_from'].day}–{top['placed_to']:%b} "
        f"{top['placed_to'].day} sell into {top['contract']} for {usd(top['margin_usd'])} a pig, "
        f"the best to place now ({ordinal(top['rank'])} percentile{moved})",
        "Pigs not placed yet · margin per pig at today's contract prices, ranked against every "
        "placement since 2020 · colour: rank (green high, red low)"
        + (
            f" · likely {usd(top['low_usd'])} to {usd(top['high_usd'])} a pig unhedged"
            if pd.notna(top.get("low_usd"))
            else ""
        ),  # fmt: skip
    )
    cols = [c for c in ranks.columns if ranks[c].notna().any()]
    z = ranks[cols].to_numpy(dtype=float)
    txt = [[("" if np.isnan(r) else f"{usd(m)}<br><span style='font-size:10px'>{ordinal(r)}"
             "</span>") for r, m in zip(rr, mm, strict=True)]
           for rr, mm in zip(z, margins[cols].to_numpy(dtype=float), strict=True)]  # fmt: skip
    hm_fig = go.Figure(go.Heatmap(
        z=z, x=cols, y=list(ranks.index), text=txt, texttemplate="%{text}", zmin=0, zmax=100,
        colorscale=[[0, "#c8453a"], [0.5, "#ece7dc"], [1, "#178a6a"]], showscale=False,
        xgap=3, ygap=3, hovertemplate="%{y}, %{x}: %{z:.0f}th percentile<extra></extra>",
        textfont={"size": 12.5, "color": INK},
    ))  # fmt: skip
    hm_fig.update_yaxes(autorange="reversed", showgrid=False, tickfont={"size": 12.5})
    hm_fig.update_xaxes(side="top", showgrid=False, tickfont={"size": 11.5})
    hm_fig.update_layout(margin={"l": 4, "r": 4, "t": 28, "b": 4}, hovermode="closest")
    left, right = st.columns([0.3 * len(cols) + 0.5, 2.1], gap="large")
    with left:
        chart(hm_fig, 70 + 46 * len(ranks), on=PAGE)
        if len(cols) == 1:
            st.caption("Earlier columns fill in as the app is used: it keeps one board a day.")
    with right:
        table(["Contract", "Placed", "Hogs $/cwt", "Margin/pig", "Likely range", "Hog:corn",
               "Rule says"],
              [[r["contract"],
                f"{r['placed_from']:%b} {r['placed_from'].day}–{r['placed_to']:%b} "
                f"{r['placed_to'].day}",
                usd(r["hog_usd_per_cwt"]), usd(r["margin_usd"]),
                (f"{usd(r['low_usd'], 0)} to {usd(r['high_usd'], 0)}"
                 if pd.notna(r["low_usd"]) else "–"),
                f"{r['hog_corn_ratio']:.1f}",
                {"good": "In place", "caution": f"Hedge {hrule.target:.0%}",
                 "neutral": "Wait" if hrule.mode != "off" else "–"}[str(r["rule_tone"])]]
               for r in fb.to_dict("records")])  # fmt: skip
    source_note(
        "your contract prices, USDA weaned pig seasonality, corn "
        + ("curve" if book.corn_mode == "Futures curve" else "cash"),
        "pig price expected for each placement week; likely range: where the margin lands if "
        "hogs miss today's price by as much as the seasonal estimate has 8 times in 10 at that "
        "distance (Hog market); hog:corn = live hog price ÷ corn $/bu; "
        f"your rule: {hrule.describe()}",
    )
    excel_button({"Forward board": fb, "Rank by week": ranks.reset_index(names="contract"),
                  "Margin by week": margins.reset_index(names="contract")},
                 "forward_margin_board", "Forward margin board", "model")  # fmt: skip
    rule()

chart_title(
    "What your rule says, contract by contract",
    f"Your rule: {hrule.describe()}",
)
rows = []
for r in summary.to_dict("records"):
    tone, _ = hedge_rule(float(r["rank"]), trigger, target, float(r["hedged_share"]), hrule,
                         float(r["unhedged_margin_usd"]) / float(r["head"]))  # fmt: skip
    short = {"good": "In place", "caution": f"Hedge {target:.0%}",
             "neutral": "Wait" if hrule.mode != "off" else "–"}[tone]  # fmt: skip
    rows.append([r["label"], f"{r['head']:,.0f}", usd(r["market_usd_per_cwt"]),
                 f"{r['hedged_share']:.0%}", usd(r["margin_usd_per_head"]),
                 usd_short(r["margin_usd"]),
                 "lowest" if r["rank"] < 1 else ordinal(r["rank"]), short])  # fmt: skip
table(["Contract", "Pigs", "Price $/cwt", "Hedged", "Margin/pig", "Total", "Rank", "Rule says"],
      rows,
      emphasis_col=3)  # fmt: skip
source_note(
    "model",
    f"rank: open margin vs every placement since 2020; your rule: {hrule.describe()}",
)
excel_button({"By contract": summary, "By placement week": pos,
              "What if hogs move": what_if(pos, [float(x) for x in range(-15, 16)])},
             "hedging_book", "Pigs on feed, hedges and what-ifs", "model")  # fmt: skip

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
