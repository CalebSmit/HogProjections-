"""This week: what moved, the decisions it points to, and what's coming up."""

from datetime import date

import pandas as pd
import streamlit as st

from hogproj import hogmarket as hm
from hogproj import supply
from hogproj.book import hedge_rule
from hogproj.brief import QUARTERLY_REPORTS, Move, calendar, move, movers
from hogproj.crush import annual_summary, breakeven_pig, contract_label, margin_rank, margin_usd
from hogproj.data import feed
from hogproj.export import build_brief
from hogproj.sowfarm import cost_per_weaned_pig
from hogproj.ui import (
    Tone,
    chart_title,
    crush_book,
    feed_prices,
    hero,
    hog_index,
    hog_market,
    insight,
    iowa_corn,
    masthead,
    nass_data,
    pork_cutout,
    rule,
    signed,
    source_note,
    sow_from_state,
    stat_strip,
    storage_now,
    tone_of,
    usd,
    wasde_now,
    weaned_pigs,
)

today = date.today()
ss = st.session_state
idx, _, _ = hog_index()
cut, _, _ = pork_cutout()
pigs, _, _ = weaned_pigs()
feeds, _, _ = feed_prices()
corn_m, _, _ = iowa_corn()

hogs = move("Lean hogs", "/cwt", idx["index_date"], idx["lean_hog_index_usd_per_cwt_carcass"])
cutout = move("The pork cutout", "/cwt", cut["date"], cut["carcass"])
weaned = move("Weaned pigs", "/head", pigs["week_ending"], pigs["cash_usd_per_head"])
cc = feeds[feeds["item"] == "corn_cash_iowa"]
corn = (
    move("Iowa cash corn", "/bu", cc["date"], cc["value"])
    if len(cc)
    else Move("Iowa cash corn", "/bu", crush_book().c.corn_usd_per_bu, None, None,
              pd.Timestamp(today))  # no USDA bid saved yet: the corn input
)  # fmt: skip
if corn.year_ago is None and not corn_m.empty:  # a year of daily bids builds up in the cache
    same = corn_m[pd.to_datetime(corn_m["month"]).dt.month == corn.as_of.month]
    same = same[pd.to_datetime(same["month"]).dt.year == corn.as_of.year - 1]
    if len(same):
        corn = Move(corn.name, corn.unit, corn.now, corn.week_ago,
                    float(same["usd_per_bu"].iloc[0]), corn.as_of)  # fmt: skip
moves = [hogs, cutout, weaned, corn]

# --- Decisions --------------------------------------------------------------------------------
book = crush_book()
c = book.c
history = book.rows[book.rows["status"] == "sold"]["margin_usd"].to_numpy(dtype=float)
m_today = margin_usd(c, book.hog)
rank_today = margin_rank(m_today, history)
most = breakeven_pig(c, book.hog)

on_feed = pd.DataFrame(book.rows[book.rows["status"] == "on feed"])
by_k = (
    on_feed.groupby("priced_on")["margin_usd"].mean().sort_values(ascending=False)
    if len(on_feed)
    else pd.Series(dtype=float)
)
trigger = float(ss.get("w2f_rule_trigger") or 75)
target = float(ss.get("w2f_rule_target") or 50) / 100

d = hog_market()
sigs = hm.signals(d, supply.next_six_months(nass_data()[0])["pct"], wasde_now(), storage_now())
market_tone, market_why = hm.overall(sigs)

s = sow_from_state()
sow_m = weaned.now + s.adder_usd_per_head - cost_per_weaned_pig(s)

place_txt = (
    f"A pig placed today projects {usd(m_today)}; one is worth up to {usd(most)} at "
    f"{contract_label(book.this_contract)} hogs."
)
if len(by_k):
    best_label, best_margin = str(by_k.index[0]), float(by_k.iloc[0])
    best_rank = margin_rank(best_margin, history)
    best_k = {contract_label(k): k for k in book.contracts}.get(best_label)
    share = (
        float(ss.get(f"w2f_hedge_{best_k[0]}_{best_k[1]:02d}_pct") or 0) / 100 if best_k else 0.0
    )
    hedge_tone, rule_txt = hedge_rule(best_rank, trigger, target, share)
    hedge_txt = (
        f"{best_label} pigs have the best margin on feed: {usd(best_margin)} a pig. " + rule_txt
    )
else:
    hedge_tone, hedge_txt = "neutral", "No pigs on feed in the data."
market_txt = {
    "good": f"The market behind hog prices looks supportive: {market_why}.",
    "bad": f"The market behind hog prices looks soft: {market_why}.",
    "neutral": "Signals behind hog prices are mixed: "
    f"{sum(x.tone == 'good' for x in sigs)} supportive, "
    f"{sum(x.tone == 'bad' for x in sigs)} negative.",
}[market_tone]
sow_txt = (
    f"A weaned pig costs {usd(cost_per_weaned_pig(s))} to make and sells for "
    f"{usd(weaned.now + s.adder_usd_per_head)}: {usd(sow_m)} a pig."
)

week_word = "up" if (hogs.week_change or 0) >= 0 else "down"
headline_txt = (
    f"Hogs {week_word} {usd(abs(hogs.week_change or 0))} on the week; a pig placed today "
    f"projects {usd(m_today)}."
)
action = masthead(
    headline_txt,
    f"Lean Hog Index {usd(hogs.now)}, weaned pigs {usd(weaned.now)}, Iowa corn "
    f"{usd(corn.now)}. "
    + (
        "Contract prices are seasonal estimates until entered on Wean to finish."
        if not book.user_set
        else "Using the contract prices you entered."
    ),
    kicker=f"This week · {today:%B %d, %Y}",
)
with action:
    sold_rows = book.rows[book.rows["status"] == "sold"]
    brief = build_brief(
        today,
        headline_txt,
        [(mv.name.replace("The ", ""), mv.now, mv.week_change, mv.year_pct, "$" + mv.unit)
         for mv in moves],
        [("Placing pigs", place_txt), ("Hedging", hedge_txt), ("Hog market", market_txt),
         ("Sow farm", sow_txt)],
        {
            "Pigs on feed": on_feed[["placed", "sold", "priced_on", "pig_usd", "hog_usd_per_cwt",
                                     "corn_usd_per_bu", "cost_usd", "margin_usd"]],
            "Market signals": pd.DataFrame([{"signal": x.name, "value": x.value, "read": x.read,
                                             "rule": x.rule} for x in sigs]),
            "Crush history by year": annual_summary(book.rows),
        },
    )  # fmt: skip
    st.download_button(
        "Download weekly brief",
        brief,
        f"weekly_brief_{today:%Y-%m-%d}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:",
        width="stretch",
    )

st.space("small")
with hero("week"):
    chart_title("This week in numbers", "Latest USDA figure, change on the week and on the year")

    def cell(mv: Move, decimals: int = 2) -> tuple[str, str, str, Tone]:
        wk = "" if mv.week_change is None else f"{signed(mv.week_change)} wk"
        yr = "" if mv.year_pct is None else f"{mv.year_pct:+.0%} yr".replace("-", "−")
        note = " · ".join(x for x in (wk, yr) if x)
        return (f"{mv.name.replace('The ', '')} · {mv.as_of:%b %d}", usd(mv.now, decimals),
                note, tone_of(mv.week_change or 0))  # fmt: skip

    stat_strip([cell(hogs), cell(cutout), cell(weaned), cell(corn)])
    st.markdown(
        "<div style='margin-top:14px'></div>"
        + "".join(f"<div class='hp-dek' style='margin:2px 0'>• {x}</div>" for x in movers(moves)),
        unsafe_allow_html=True,
    )
    source_note(
        "USDA AMS LM_HG201, LM_PK602, Feeder Pig Report, Iowa Daily Cash Grain Bids",
        "week = latest vs a week earlier; year = vs the same time last year",
    )

st.space("medium")
chart_title("Decisions this week", "Each card links to the page with the detail")
a, b = st.columns(2, gap="large")
with a:
    insight(
        tone_of(m_today) if m_today >= 0 else "bad",
        "Placing pigs",
        place_txt,
        [
            ("USDA weaned pig", usd(weaned.now)),
            ("Most you can pay", usd(most)),
            ("Vs history", f"{rank_today:.0f}th pct"),
        ],  # fmt: skip
        "Contract prices are seasonal estimates." if not book.user_set else "",
    )
    st.page_link(
        "views/8_Wean_to_finish.py", label="Wean to finish", icon=":material/arrow_forward:"
    )
with b:
    if len(by_k):
        card_tone: Tone = "caution" if hedge_tone == "caution" else "neutral"
        insight(
            card_tone,
            "Hedging",
            hedge_txt,
            [(str(k), usd(float(v))) for k, v in by_k.items()][:3],
            "Ranks against every placement since 2020; enter hedges on the Hedging page.",
        )
    else:
        insight("neutral", "Hedging", "No pigs on feed in the data.")
    st.page_link("views/10_Hedging.py", label="Hedging", icon=":material/arrow_forward:")
a, b = st.columns(2, gap="large")
with a:
    strongest = [x for x in sigs if x.tone != "neutral"][:3]
    insight(
        market_tone,
        "Hog market",
        market_txt,
        [(x.name, x.value) for x in strongest],
    )  # fmt: skip
    st.page_link("views/3_Market_prices.py", label="Hog market", icon=":material/arrow_forward:")
with b:
    insight(
        tone_of(sow_m),
        "Sow farm",
        sow_txt,
        [
            ("Per sow per year", usd(sow_m * s.weaned_per_sow_yr, 0)),
            ("Weaned per sow", f"{s.weaned_per_sow_yr:.1f}"),
        ],  # fmt: skip
    )
    st.page_link("views/11_Sow_farm.py", label="Sow farm", icon=":material/arrow_forward:")

rule()
left, right = st.columns([1, 1], gap="large")
with left:
    chart_title("Coming up", "Contract expiries are exact; report days are typical")
    rows = "".join(
        f"<div style='display:grid;grid-template-columns:110px 1fr;padding:8px 0;"
        f"border-bottom:1px solid var(--line);font-size:14px'><b>{d0:%a %b %d}</b>"
        f"<span>{text}</span></div>"
        for d0, text in calendar(today)
    )
    st.markdown(rows, unsafe_allow_html=True)
    st.caption(QUARTERLY_REPORTS)
with right:
    chart_title("Where the numbers come from", "All public USDA data")
    latest = feed.latest(feeds, "sbm_iowa")
    st.markdown(
        f"""
- **Lean Hog Index** rebuilt from USDA LM_HG201, index for {hogs.as_of:%b %d}.
- **Pork cutout** USDA LM_PK602, {cutout.as_of:%b %d}.
- **Weaned pigs** USDA National Direct Feeder Pig Report, week ending {weaned.as_of:%b %d}.
- **Iowa corn** USDA Iowa Daily Cash Grain Bids, {corn.as_of:%b %d}"""
        + (f"; **soybean meal** USDA AMS 3511, {latest[1]:%b %d}." if latest else ".")
    )
