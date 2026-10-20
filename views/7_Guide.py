"""Guide: what the numbers mean, where they come from, and how to set the app up."""

import html

import pandas as pd
import streamlit as st

from hogproj import supply
from hogproj.config import get_settings
from hogproj.text import day
from hogproj.ui import INK, INK_2, LINE, MUTED, chart_title, hog_index, masthead, nass_data, rule

idx, hog_source, _ = hog_index()
nass_df, nass_source, _ = nass_data()
index_date = pd.Timestamp(idx["index_date"].iloc[-1])
report = supply.latest_report(nass_df)

masthead(
    "How to read this outlook.",
    "What each number means, where it comes from, and how to set the app up for your farm.",
    kicker="Guide",
)


def _e(text: str) -> str:
    return html.escape(text).replace("$", "&#36;")


def steps(items: list[tuple[str, str]]) -> None:
    rows = "".join(
        f'<div style="display:grid;grid-template-columns:34px 1fr;gap:14px;padding:14px 0;'
        f'border-bottom:1px solid {LINE}">'
        f'<div style="font-family:var(--serif);font-size:24px;color:var(--accent);'
        f'line-height:1">{i}</div>'
        f'<div><div style="font-weight:600;color:{INK};font-size:15.5px">{_e(t)}</div>'
        f'<div style="color:{INK_2};font-size:14.5px;margin-top:2px">{_e(d)}</div></div></div>'
        for i, (t, d) in enumerate(items, start=1)
    )
    st.markdown(rows, unsafe_allow_html=True)


def glossary(items: list[tuple[str, str]]) -> None:
    rows = "".join(
        f'<div style="display:grid;grid-template-columns:200px 1fr;gap:18px;padding:11px 0;'
        f'border-bottom:1px solid {LINE};font-size:14.5px">'
        f'<div style="font-weight:600;color:{INK}">{_e(term)}</div>'
        f'<div style="color:{INK_2}">{_e(meaning)}</div></div>'
        for term, meaning in items
    )
    st.markdown(rows, unsafe_allow_html=True)


left, mid, right = st.columns([1, 0.06, 1.15])
with left:
    chart_title("Set it up", "About five minutes")
    steps(
        [
            (
                "Enter your herd",
                "On Herd flow, open the chips under the headline: sows, productivity, timing and "
                "market weight.",
            ),
            (
                "Enter your prices and costs",
                "On Costs & returns: your local corn and soybean meal bids, the hog price you "
                "expect, and your cost per pig. Hog price and corn can also be changed from the "
                "Farm outlook.",
            ),
            (
                "Start each week on This week",
                "It shows what moved and four decisions with links to the detail: placing pigs, "
                "hedging, the hog market and the sow farm. Farm outlook projects the year.",
            ),
            (
                "Bring in futures",
                "Export a quote board from Barchart or DTN and drop it into Hog prices on Wean "
                "to finish (or Contract prices on Hedging). Every lean hog contract fills in.",
            ),
            (
                "Save your setup",
                "Use Save inputs in the sidebar to keep your numbers, and Load inputs to bring "
                "them back or open a setup someone sent you.",
            ),
        ]
    )
with mid:
    st.markdown(
        '<div class="hp-vrule" style="height:520px"></div>',
        unsafe_allow_html=True,
    )
with right:
    chart_title("Terms used in the app", "In plain language")
    glossary(
        [
            ("cwt", "Hundredweight: 100 pounds. Hog prices are quoted in dollars per cwt."),
            (
                "Carcass vs. live",
                "Carcass price is per 100 lb of carcass after slaughter; live is per 100 lb of "
                "live hog. Live ≈ carcass × 0.75. The app uses carcass unless it says live.",
            ),
            (
                "Lean Hog Index",
                "The CME's daily average price packers paid for hogs, rebuilt here from USDA "
                "reports. Lean hog futures settle on it.",
            ),
            (
                "Breakeven",
                "The hog price that covers every cost of raising a pig, before the manure credit.",
            ),
            (
                "Farrow to finish",
                "Raising pigs from birth (farrowing) to market weight on the same operation.",
            ),
            (
                "Manure credit",
                "Fertilizer value of the manure, which reduces the net cost of each pig.",
            ),
            (
                "Pig crop",
                "Pigs born in a quarter. They reach market about six months later.",
            ),
            (
                "Farrowing intentions",
                "How many sows producers plan to farrow in coming quarters (USDA survey).",
            ),
            (
                "Pork cutout",
                "USDA's estimate of the wholesale value of a 100 lb hog carcass, built from the "
                "prices of its cuts (loin, belly, ham and so on).",
            ),
            (
                "Packer spread",
                "Cutout plus by-product value minus the Lean Hog Index: what packers get for the "
                "whole hog minus what they pay for it, before plant costs. Wide spreads give "
                "packers room to bid more.",
            ),
            (
                "Percentile",
                "Where a number ranks against history: 80th means better than 80% of past weeks.",
            ),
            (
                "Hedged share",
                "Part of the pigs on feed already priced (futures, forward contract, LRP floor). "
                "The rest moves with the market.",
            ),
            (
                "1 in 10 years",
                "On Risk, a bad year is one only 1 in 10 simulated years does worse than.",
            ),
            (
                "Seasonal path",
                "Hog prices usually peak in summer and dip in winter. The projection starts at "
                "today's price and follows that pattern.",
            ),
        ]
    )

rule()
chart_title("Where the data comes from", "What updates when")
rows = [
    (
        "USDA AMS · LM_HG201",
        "Hog prices and the Lean Hog Index",
        "Every business day",
        f"Index for {day(index_date, '%b %d, %Y')}"
        + (" (live)" if hog_source == "live" else " (saved)"),
    ),
    (
        "USDA NASS · Hogs and Pigs",
        "Herd inventory, pig crop, farrowing intentions",
        "Quarterly: late Mar, Jun, Sep, Dec",
        f"{report:%B} 1, {report.year} report"
        + (" (live)" if nass_source == "live" else " (saved)"),
    ),
    (
        "Iowa State University",
        "Estimated Livestock Returns, farrow to finish",
        "Monthly",
        "Other feed, non-feed, death loss and manure defaults follow the latest month until "
        "you edit them (Costs & returns)",
    ),
    (
        "USDA AMS · Feeder Pig Report",
        "Weaned pig prices (early weaned 10-12 lb, cash)",
        "Weekly, Fridays",
        "Wean to finish page; public report, no key needed",
    ),
    (
        "USDA NASS · Prices Received",
        "Iowa corn price, monthly",
        "Monthly",
        "Realized wean-to-finish margins and the corn price hint",
    ),
    (
        "USDA AMS · Iowa grain and feedstuff reports",
        "Iowa cash corn, soybean meal, DDGS, CBOT corn settlements",
        "Corn daily; meal and DDGS weekly",
        "Default feed prices on every page; public reports, no key needed",
    ),
    (
        "USDA AMS · LM_PK602 pork cutout",
        "Cutout and primal values, packer spread",
        "Every business day",
        "Hog market page",
    ),
    (
        "USDA ERS · Livestock and Meat Domestic Data",
        "Pork in cold storage",
        "Monthly",
        "Hog market cold storage chart and signal",
    ),
    (
        "USDA WASDE",
        "Quarterly pork production and hog price forecasts",
        "Monthly, around the 10th-12th",
        "Hog market outlook and signal; reference price on Wean to finish",
    ),
    (
        "USDA AMS · My Market News",
        "History: weaned pigs (cash and formula) since 2020, Iowa corn and basis since 2020, "
        "soybean meal and DDGS since 2022; corn and basis in 11 states, feeder pig flows, hog "
        "by-product (drop) value, retail pork features, all federally inspected slaughter",
        "Daily / weekly",
        "Connected"
        if get_settings().usda_mmn_api_key.strip()
        else "Optional: add USDA_MMN_API_KEY to .env",
    ),
    (
        "USDA AMS · LM_HG218, LM_HG234",
        "Hog prices by region and purchase type, hogs by state of origin, carcass weight "
        "discounts, cull sow prices",
        "Every business day",
        "National view; cull sows on Sow farm; public, no key needed",
    ),
    (
        "USDA ERS · trade and price spreads",
        "Pork exports by country, live hog imports (Canadian pigs), farm-to-retail pork values",
        "Monthly, about two months behind",
        "Demand section on Hog market; pigs from Canada on National view",
    ),
    (
        "USDA AMS · weekly slaughter by class (AMS_3658)",
        "Sows slaughtered each week",
        "Weekly, about two weeks behind",
        "Sow slaughter chart and signal (Hog supply, Hog market)",
    ),
    (
        "U.S. Energy Information Administration",
        "Weekly on-highway diesel; Minnesota and Iowa propane (heating season)",
        "Weekly, Mondays",
        "Fuel charts on Costs & returns",
    ),
    (
        "FRED (St. Louis Fed)",
        "Bank prime loan rate",
        "When the Fed moves rates",
        "Operating interest hint on Wean to finish",
    ),
    (
        "USDA WASDE archive (ESMIS)",
        "Past WASDE hog price forecasts",
        "Monthly",
        "How far off USDA's forecasts have been (Hog market)",
    ),
    (
        "Your Barchart or DTN export",
        "Lean hog futures settlements",
        "Whenever you upload one",
        "Contract prices on Wean to finish and Hedging",
    ),
]
head = "".join(
    f'<th style="text-align:left;padding:8px 12px 8px 0;color:{MUTED};font-size:11px;'
    f'text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid {LINE}">{h}</th>'
    for h in ("Source", "Used for", "Updates", "In this app")
)
body = "".join(
    "<tr>"
    + "".join(
        f'<td style="padding:10px 12px 10px 0;border-bottom:1px solid {LINE};font-size:14px;'
        f'color:{INK if i == 0 else INK_2};{"font-weight:600;" if i == 0 else ""}">{_e(c)}</td>'
        for i, c in enumerate(r)
    )
    + "</tr>"
    for r in rows
)
st.markdown(
    f'<table class="hp-table" style="width:100%;border-collapse:collapse"><thead><tr>{head}'
    f"</tr></thead><tbody>{body}</tbody></table>",
    unsafe_allow_html=True,
)

rule()
chart_title("What the model leaves out", "Read the numbers with these in mind")
st.markdown(
    f"""<div style="color:{INK_2};font-size:14.5px;line-height:1.7;max-width:900px">
<p>Disease outbreaks, export shocks and futures-market views aren't modelled. Costs follow a
typical Iowa farrow-to-finish operation; your contract, basis and facility costs will differ, so
enter your own. Feed prices start at Iowa averages; your bids will differ. The
projections are planning estimates, not financial advice.</p></div>""",
    unsafe_allow_html=True,
)
