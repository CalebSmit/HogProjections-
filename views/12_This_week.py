"""This week: what moved, the decisions it points to, and what's coming up."""

import html
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj import hogmarket as hm
from hogproj import national as nv
from hogproj import scorecard as sc
from hogproj import seasonal, snapshots
from hogproj.book import hedge_rule
from hogproj.brief import QUARTERLY_REPORTS, Move, calendar, move
from hogproj.brief_pdf import Brief, build_pdf
from hogproj.config import get_settings
from hogproj.crush import annual_summary, breakeven_pig, contract_label, margin_rank, margin_usd
from hogproj.data import feed
from hogproj.export import build_brief
from hogproj.freshness import is_current
from hogproj.sowfarm import cost_per_weaned_pig
from hogproj.text import ordinal
from hogproj.ui import (
    CAUTION,
    MUTED,
    NEG,
    PAGE,
    POS,
    Tone,
    chart,
    chart_title,
    crush_book,
    data_status,
    excel_button,
    feed_prices,
    fuel_prices,
    hedge_rule_from_state,
    hero,
    hog_index,
    hog_market,
    insight,
    iowa_corn,
    margin_board,
    market_signals,
    mars_data,
    masthead,
    pork_cutout,
    regional_data,
    rule,
    scorecard_table,
    signed,
    source_note,
    sow_from_state,
    tone_of,
    usd,
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
sbm = feeds[feeds["item"] == "sbm_iowa"]
fi_raw, _, _ = mars_data("fi_slaughter")
fi_used = not fi_raw.empty and is_current("Inspected slaughter", fi_raw["date"].max())
sows_raw, _, _ = regional_data("sows")
sow_px = nv.sow_price(sows_raw) if not sows_raw.empty else pd.Series(dtype=float)
fuel, _, _ = fuel_prices()
diesel = fuel[fuel["series"] == "diesel_us"].set_index("date")["usd_per_gal"]


def weekly_series(dates: pd.Series, values: pd.Series, weeks: int = 52) -> pd.DataFrame:
    """Last `weeks` weeks of a series as weekly (Friday) averages, for the brief's charts."""
    x = pd.Series(values.to_numpy(dtype=float), index=pd.to_datetime(dates)).sort_index()
    w = x.resample("W-FRI").mean().dropna().tail(weeks)
    return pd.DataFrame({"date": w.index, "value": w.to_numpy()})


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
hrule = hedge_rule_from_state()

d = hog_market()
fi_series = (fi_raw.set_index("date")["head"] if fi_used
             else d.set_index("date")["head"])  # fmt: skip
sigs = market_signals()
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
    hedge_tone, rule_txt = hedge_rule(best_rank, hrule.trigger, hrule.target, share, hrule,
                                      best_margin)  # fmt: skip
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

# --- The answer, in three sentences ------------------------------------------------------------
before = snapshots.previous(today)
since = ""
if before is not None:
    moved = m_today - float(before["margin_today"])
    since = (f", {'up' if moved >= 0 else 'down'} {usd(abs(moved))} since "
             f"{pd.Timestamp(before['date']):%b} {pd.Timestamp(before['date']).day}")  # fmt: skip
week_word = "up" if (hogs.week_change or 0) >= 0 else "down"
headline_txt = f"A pig placed today projects {usd(m_today)} a head{since}."
dek_txt = " ".join([
    f"Hogs are {week_word} {usd(abs(hogs.week_change or 0))} on the week at {usd(hogs.now)}.",
    hedge_txt if len(by_k) else "",
    market_txt,
])  # fmt: skip
action = masthead(
    headline_txt,
    dek_txt
    + (
        " Contract prices are "
        + {"USDA outlook": "USDA's outlook"}.get(book.price_source, "seasonal estimates")
        + " until entered on Wean to finish."
        if not book.user_set
        else ""
    ),
    kicker=f"This week · {today:%B %d, %Y}",
)
with action:
    sold_rows = book.rows[book.rows["status"] == "sold"]
    brief = lambda: build_brief(  # noqa: E731 - built on click
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
        charts={
            "Lean Hog Index, $/cwt": weekly_series(idx["index_date"],
                                                    idx["lean_hog_index_usd_per_cwt_carcass"]),
            "Pork cutout, $/cwt": weekly_series(cut["date"], cut["carcass"]),
            "Weaned pigs, $/head": weekly_series(pigs["week_ending"], pigs["cash_usd_per_head"]),
            "Iowa cash corn, $/bu": weekly_series(cc["date"], cc["value"]),
        },
    )  # fmt: skip
    st.download_button(
        "Weekly brief (Excel)",
        brief,
        f"weekly_brief_{today:%Y-%m-%d}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:",
        width="stretch",
        on_click="ignore",
    )

st.space("small")
with hero("week"):
    chart_title("Scorecard", "Each number against the same week in the five years before "
                "(2020 left out) · status for a hog producer: green helps, red hurts")  # fmt: skip
    metrics = [
        sc.Metric("Lean hogs", idx.set_index("index_date")["lean_hog_index_usd_per_cwt_carcass"],
                  suffix="/cwt", good=1),
        sc.Metric("Pork cutout", cut.set_index("date")["carcass"], suffix="/cwt", good=1),
        sc.Metric("Packer spread", d.set_index("date")["spread_per_head"], suffix="/head", good=1),
        sc.Metric("Weaned pigs", pigs.set_index("week_ending")["cash_usd_per_head"],
                  suffix="/head"),
        sc.Metric("Iowa cash corn", cc.set_index("date")["value"], suffix="/bu", good=-1),
        sc.Metric("Soybean meal", sbm.set_index("date")["value"], suffix="/ton", decimals=0,
                  good=-1),
        sc.Metric("Hogs slaughtered", fi_series, prefix="", decimals=0, good=-1, how="sum",
                  week="W-SAT", year_ago=fi_raw.set_index("date")["head_year_ago"]
                  if fi_used else None),
        sc.Metric("Carcass weight", d.set_index("date")["weight_lb"], prefix="", suffix=" lb",
                  decimals=1, good=-1),
        sc.Metric("Cull sows", sow_px, suffix="/cwt"),
        sc.Metric("Diesel", diesel, suffix="/gal", good=-1),
    ]  # fmt: skip
    card = sc.build(metrics)
    scorecard_table(card)
    source_note(
        "USDA AMS (LMR, cutout, feeder pigs, Iowa grain and feedstuffs, slaughter), U.S. EIA",
        "week and year: latest vs a week and a year earlier; slaughter is the last full week, "
        + ("all federally inspected hogs" if fi_used else "producer-sold barrows and gilts"),
    )
    excel_button({"Scorecard": sc.table(card),
                  "Market signals": pd.DataFrame([vars(x) for x in sigs])},
                 "scorecard", "This week's scorecard and market signals",
                 "USDA AMS, EIA")  # fmt: skip

fb = margin_board()
fb_top = fb.loc[fb["rank"].idxmax()] if not fb.empty else None
# --- Watch list: things to act on ------------------------------
watch: list[tuple[Tone, str]] = []
if len(on_feed):
    for k_label, k_margin in by_k.items():
        k = {contract_label(x): x for x in book.contracts}.get(str(k_label))
        held = float(ss.get(f"w2f_hedge_{k[0]}_{k[1]:02d}_pct") or 0) / 100 if k else 0.0
        t, why = hedge_rule(margin_rank(float(k_margin), history), hrule.trigger, hrule.target,
                            held, hrule, float(k_margin))  # fmt: skip
        if t == "caution":
            watch.append(("caution", f"{k_label}: {why}"))
for r in fb.to_dict("records") if not fb.empty else []:
    if r["rule_tone"] == "caution":
        watch.append(("caution", f"Pigs not placed yet, selling into {r['contract']}: "
                                 f"{r['rule_says']}"))  # fmt: skip
if most > weaned.now:
    watch.append(("good", f"Weaned pigs at {usd(weaned.now)} are below the {usd(most)} one is "
                          "worth at today's contract prices."))  # fmt: skip
late = [f for f in data_status() if f.behind]
if late:
    watch.append(("bad", "Out of date: " + ", ".join(f.name for f in late) + "."))
st.space("small")
if not watch:
    watch.append(("neutral", f"Nothing crosses your rule this week ({hrule.describe()})."))
chart_title("Watch list", "What crosses your hedge rule, pigs priced below what they're "
            "worth, and data that's out of date")  # fmt: skip
dots = {"good": POS, "bad": NEG, "caution": CAUTION, "neutral": MUTED}
st.markdown("".join(
    f"<div style='display:flex;gap:10px;align-items:baseline;padding:7px 0;"
    f"border-bottom:1px solid var(--line);font-size:14px'><span style='flex:none;"
    f"width:8px;height:8px;border-radius:50%;background:{dots[t]};transform:translateY(-1px)'>"
    f"</span><span>{html.escape(text)}</span></div>" for t, text in watch),
    unsafe_allow_html=True)  # fmt: skip

st.space("medium")

with action:  # the one-page PDF, now that the scorecard, board and watch list exist
    pdf = lambda: build_pdf(Brief(  # noqa: E731 - built on click
        as_of=today, headline=headline_txt, dek=dek_txt, scorecard=card,
        index_weeks=sc_weeks(idx), board=fb,
        decisions=[("Placing pigs", place_txt), ("Hedging", hedge_txt),
                   ("Hog market", market_txt), ("Sow farm", sow_txt)],
        watch=[(str(t), w) for t, w in watch],
        signals=[(x.tone, x.name, x.value, x.read) for x in sigs],
        sources="Data: USDA AMS (LMR, cutout, feeder pigs, Iowa grain and feedstuffs, "
                "slaughter), USDA NASS, ERS and WASDE, U.S. EIA; Lean Hog Index for "
                f"{hogs.as_of:%b %d}. Contract prices: "
                + ("entered by the user." if book.user_set else f"{book.price_source.lower()}."),
    ))  # fmt: skip
    st.download_button(
        "Weekly brief (PDF)",
        pdf,
        f"weekly_brief_{today:%Y-%m-%d}.pdf",
        "application/pdf",
        icon=":material/picture_as_pdf:",
        width="stretch",
        on_click="ignore",
        type="primary",
    )


def sc_weeks(index: pd.DataFrame) -> pd.DataFrame:
    return seasonal.by_week(index.set_index("index_date")["lean_hog_index_usd_per_cwt_carcass"])


# --- Since last week --------------------------------------------------------------------------
snap_now = {
    "index": hogs.now, "cutout": cutout.now, "weaned_pig": c.pig_usd_per_head,
    "corn": c.corn_usd_per_bu, "hog_contract": book.hog, "margin_today": m_today,
    "most_pay": most, "sow_margin": sow_m,
    "on_feed_margin": float(on_feed["margin_usd"].mean()) if len(on_feed) else float("nan"),
    "market_score": sum(1 if x.tone == "good" else -1 if x.tone == "bad" else 0 for x in sigs),
    "cwt": c.carcass_cwt, "corn_lb": c.corn_lb,
}  # fmt: skip
if not get_settings().offline:  # tests and offline use don't write the record
    snapshots.record(today, snap_now)
chart_title("Since last week", "What this page said a week ago, and why it moved")
if before is None:
    st.caption(
        "The app keeps a snapshot of these numbers each day this page is opened. From next week, "
        "this section shows what changed and why."
    )
else:
    then = pd.Timestamp(before["date"])
    change = m_today - float(before["margin_today"])
    left, right = st.columns([1, 1.2], gap="large")
    with left:
        insight(
            tone_of(change),
            f"vs {then:%b %d}",
            f"A pig placed today projects {usd(m_today)}, "
            f"{'up' if change >= 0 else 'down'} {usd(abs(change))} since {then:%b %d}.",
            [
                ("Most you can pay", f"{usd(most)} ({signed(most - float(before['most_pay']))})"),
                ("Sow farm margin",
                 f"{usd(sow_m)} ({signed(sow_m - float(before['sow_margin']))})"),
                ("Market signals", f"{snap_now['market_score']:+d} (was "
                 f"{int(before['market_score']):+d})".replace("-", "−")),
            ],
        )  # fmt: skip
    with right:
        parts = snapshots.explain(snap_now, before)
        if parts:
            fx = go.Figure(
                go.Bar(
                    y=[k for k, _ in parts][::-1],
                    x=[v for _, v in parts][::-1],
                    orientation="h",
                    marker={"color": [POS if v >= 0 else NEG for _, v in parts][::-1],
                            "cornerradius": 3},
                    text=[signed(v) for _, v in parts][::-1],
                    textposition="outside",
                    cliponaxis=False,
                    hovertemplate="%{y}: %{text} a pig<extra></extra>",
                )
            )  # fmt: skip
            lim = max(abs(v) for _, v in parts) * 1.5
            fx.update_xaxes(range=[-lim, lim], tickprefix="$", zeroline=True)
            fx.update_layout(showlegend=False, hovermode="closest", bargap=0.45)
            chart(fx, 200, on=PAGE)
            source_note("the app's own snapshot", "how much each input moved the margin per pig")
rule()

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
            ("Vs history", f"{ordinal(rank_today)} pct"),
        ],  # fmt: skip
        f"Contract prices: {book.price_source.lower()}." if not book.user_set else "",
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
            [(str(k), usd(float(v))) for k, v in by_k.items()][:3]
            + (
                [
                    (
                        "Best not yet placed",
                        f"{fb_top['contract']} · {usd(fb_top['margin_usd'])} "
                        f"({ordinal(fb_top['rank'])})",
                    )
                ]
                if fb_top is not None
                else []
            ),
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
    chart_title("Where the numbers come from", "Public USDA and U.S. EIA data")
    latest = feed.latest(feeds, "sbm_iowa")
    st.markdown(
        f"""
- **Lean Hog Index** rebuilt from USDA LM_HG201, index for {hogs.as_of:%b %d}.
- **Pork cutout** USDA LM_PK602, {cutout.as_of:%b %d}.
- **Weaned pigs** USDA National Direct Feeder Pig Report, week ending {weaned.as_of:%b %d}.
- **Iowa corn** USDA Iowa Daily Cash Grain Bids, {corn.as_of:%b %d}"""
        + (f"; **soybean meal** USDA AMS 3511, {latest[1]:%b %d}." if latest else ".")
    )
