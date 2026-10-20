"""Wean to finish: the margin on a weaned pig bought at the USDA price and sold ~160 days later."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj import seasonal
from hogproj.crush import (
    MONTHS,
    CrushInputs,
    breakeven_hog,
    breakeven_pig,
    contract_label,
    cost_table,
    cost_usd,
    feed_lines,
    margin_rank,
    margin_usd,
    operating_interest,
    pig_seasonality,
)
from hogproj.finance import CostInputs
from hogproj.text import day
from hogproj.ui import (
    ACCENT,
    HISTORY,
    INK,
    INK_2,
    NEG,
    PAGE,
    POS,
    assumption_bar,
    chart,
    chart_title,
    chip,
    crush_book,
    crush_workbook,
    end_tag,
    excel_button,
    feed_default,
    feed_help,
    futures_upload,
    hero,
    hog_index,
    iowa_corn,
    latest_weaned_pig,
    lh_key,
    live_number,
    mars_data,
    masthead,
    md,
    prime_rate,
    projection_band,
    quote,
    ref_line,
    rule,
    signed,
    source_note,
    stat_strip,
    table,
    tone_of,
    usd,
    user_value,
    weaned_pigs,
)

ss = st.session_state
today = date.today()
idx, _, _ = hog_index()
pigs, pig_source, _ = weaned_pigs()
corn_hist, corn_source, _ = iowa_corn()
index_now = float(idx["lean_hog_index_usd_per_cwt_carcass"].iloc[-1])
last_index = date.fromisoformat(str(idx["index_date"].iloc[-1])[:10])
usda_pig = latest_weaned_pig()
usda_week = pd.Timestamp(pigs["week_ending"].iloc[-1])
d = CrushInputs()
cd = CostInputs()

# Contract prices: the user's futures where entered, else a seasonal estimate from the index.
book0 = crush_book()
contracts, model = book0.contracts, book0.model


def avg(df: pd.DataFrame, col: str) -> float:
    return float(np.mean(df[col].to_numpy(dtype=float))) if len(df) else float("nan")


def only(df: pd.DataFrame, mask: object) -> pd.DataFrame:
    return pd.DataFrame(df[mask])  # keeps pyright on DataFrame, not Series | ndarray


def cur(key: str, default: float) -> float:
    return user_value(key, default)


this_contract = book0.this_contract

# --- Masthead + assumptions -------------------------------------------------------------
head = st.empty()
with assumption_bar("w2f"):
    with st.popover(
        md(f"Weaned pig · {usd(cur('w2f_pig', usda_pig))} + {usd(cur('w2f_adder', 0))}")
    ):
        live_number(
            st,
            "Weaned pig price ($/head)",
            0.0,
            200.0,
            usda_pig,
            0.25,
            key="w2f_pig",
            help="USDA early weaned 10-12 lb, cash composite, week ending "
            f"{day(usda_week, '%b %d, %Y')}.",
        )
        st.number_input(
            "Your adder ($/head)",
            -50.0,
            100.0,
            0.0,
            0.25,
            key="w2f_adder",
            help="What you pay over (or under) the USDA price: genetics, health status, "
            "freight. Applies to every placement.",
        )
    hog_label = usd(cur(lh_key(this_contract), model.get(this_contract, index_now)))
    with st.popover(md(f"Hog prices · {contract_label(this_contract)} {hog_label}")):
        futures_upload()
        st.segmented_control(
            "Prices you haven't entered come from",
            ["Seasonal estimate", "USDA outlook"],
            default="Seasonal estimate",
            key="w2f_lh_source",
            help="Seasonal estimate: today's Lean Hog Index carried along its usual seasonal "
            "pattern. USDA outlook: WASDE's quarterly barrow and gilt forecast, converted to an "
            "index price with the ratio between the two in recent quarters.",
        )
        st.caption(
            "Lean hog futures by contract, $/cwt carcass. Enter today's CME settlements for a "
            "market-based answer; entered prices are kept until you change them."
        )
        cols = st.columns(2)
        for i, k in enumerate(contracts):
            live_number(cols[i % 2], contract_label(k), 0.0, 250.0, model[k], 0.25, key=lh_key(k))
        st.number_input(
            "Your basis to the index ($/cwt)",
            -30.0,
            30.0,
            0.0,
            0.25,
            key="w2f_basis",
            help="Your carcass price minus the Lean Hog Index: grid premiums, sort loss, "
            "packer discounts. Negative if you usually sell under the index.",
        )
    with st.popover(
        f"Pig · {cur('w2f_days', d.days_on_feed):.0f} days · "
        f"{cur('w2f_wt', d.weight_lb_live):.0f} lb"
    ):
        st.number_input("Days on feed", 60, 300, d.days_on_feed, 1, key="w2f_days",
                        help="Placement to average marketing date.")  # fmt: skip
        st.number_input("Market weight (lb live)", 150.0, 400.0, d.weight_lb_live, 1.0,
                        key="w2f_wt")  # fmt: skip
        st.number_input("Carcass yield (%)", 60.0, 90.0, d.carcass_yield * 100, 0.5,
                        key="w2f_yield")  # fmt: skip
    corn_note = ""
    if not corn_hist.empty:
        last_corn = corn_hist.iloc[-1]
        corn_note = (
            f" Iowa farmers received {usd(float(last_corn['usd_per_bu']))}/bu in "
            f"{pd.Timestamp(last_corn['month']):%B %Y} (USDA NASS)."
        )
    with st.popover(
        md(
            f"Feed · corn {usd(cur('cost_corn', feed_default('corn_cash_iowa')))} · SBM "
            f"{usd(cur('cost_sbm', feed_default('sbm_iowa')), 0)}"
        )
    ):
        a, b = st.columns(2)
        shared = " Shared with Costs & returns."
        live_number(a, "Corn ($/bu)", 0.0, 20.0, feed_default("corn_cash_iowa"), 0.05,
                       key="cost_corn",
                       help=feed_help("corn_cash_iowa") + shared + corn_note)  # fmt: skip
        live_number(b, "Soybean meal ($/ton)", 0.0, 1000.0, feed_default("sbm_iowa"), 5.0,
                       key="cost_sbm", help=feed_help("sbm_iowa") + shared)  # fmt: skip
        live_number(
            a,
            "DDGS ($/ton)",
            0.0,
            600.0,
            feed_default("ddgs_iowa"),
            5.0,
            key="w2f_ddgs",
            help=feed_help("ddgs_iowa"),
        )
        b.number_input("Other feed ($/lb)", 0.0, 5.0, d.other_feed_usd_per_lb, 0.01,
                       key="w2f_other_price", help="Premix, vitamins, additives.")  # fmt: skip
        st.segmented_control(
            "Corn for pigs on feed",
            ["Futures curve", "Today's cash"],
            default="Futures curve",
            key="w2f_corn_mode",
            help="Futures curve: CBOT corn for each month on feed plus your basis (your cash "
            "price minus nearby futures), as the workbook does. Today's cash: one price for "
            "every month.",
        )
        if book0.corn_mode == "Futures curve":
            st.caption(
                f"A pig placed today eats corn at {usd(book0.c.corn_usd_per_bu)}/bu on average: "
                f"CBOT curve over its months on feed {signed(book0.corn_basis)} basis."
            )
        st.caption("Pounds fed per pig, placement to market")
        a, b = st.columns(2)
        a.number_input("Corn (lb)", 0.0, 1500.0, d.corn_lb, 5.0, key="w2f_corn_lb")
        b.number_input("Soybean meal (lb)", 0.0, 500.0, d.sbm_lb, 1.0, key="w2f_sbm_lb")
        a.number_input("DDGS (lb)", 0.0, 500.0, d.ddgs_lb, 1.0, key="w2f_ddgs_lb")
        b.number_input("Other feed (lb)", 0.0, 200.0, d.other_feed_lb, 0.5, key="w2f_other_lb")
    other_total = sum(
        cur(k, getattr(d, f))
        for k, f in [("w2f_health", "health_usd"), ("w2f_barn", "facilities_labor_usd"),
                     ("w2f_mort", "mortality_usd"), ("w2f_overhead", "overhead_usd"),
                     ("w2f_freight", "freight_usd"), ("w2f_interest", "interest_usd"),
                     ("w2f_other", "other_usd"), ("w2f_principal", "principal_usd"),
                     ("w2f_term_int", "term_interest_usd")]
    )  # fmt: skip
    with st.popover(md(f"Other costs · {usd(other_total)}/pig")):
        a, b = st.columns(2)
        a.number_input("Animal health", 0.0, 100.0, d.health_usd, 0.25, key="w2f_health")
        b.number_input("Barn and labor", 0.0, 200.0, d.facilities_labor_usd, 0.25, key="w2f_barn",
                       help="Facility rent or grower payment plus labor.")  # fmt: skip
        a.number_input("Mortality", 0.0, 100.0, d.mortality_usd, 0.25, key="w2f_mort")
        b.number_input("Overhead (G&A)", 0.0, 100.0, d.overhead_usd, 0.25, key="w2f_overhead")
        a.number_input("Freight out", 0.0, 100.0, d.freight_usd, 0.25, key="w2f_freight")
        pr = prime_rate()
        b.number_input("Operating interest", 0.0, 100.0, d.interest_usd, 0.25, key="w2f_interest",
                       help=None if pr is None else
                       f"Prime rate is {pr[0]:.2f}% (FRED, {pr[1]:%b} {pr[1].day}). At prime + 1%, "
                       f"carrying the pig for {book0.c.days_on_feed} days and half its feed and "
                       f"other costs is about "
                       f"{usd(operating_interest(book0.c, (pr[0] + 1) / 100))}/pig.")  # fmt: skip
        a.number_input("Other / sales premiums", -50.0, 100.0, d.other_usd, 0.25, key="w2f_other")
        st.caption("Debt payments per pig (optional)")
        a, b = st.columns(2)
        a.number_input("Principal", 0.0, 100.0, 0.0, 0.1, key="w2f_principal")
        b.number_input("Term interest", 0.0, 100.0, 0.0, 0.1, key="w2f_term_int")

# --- Numbers ------------------------------------------------------------------------------
book = crush_book()
c, futures, this_contract, hog = book.c, book.futures, book.this_contract, book.hog
m = margin_usd(c, hog)
cost = cost_usd(c)
be_pig = breakeven_pig(c, hog)
be_hog = breakeven_hog(c)
sold_date = today + timedelta(days=c.days_on_feed)
rows = book.rows
sold = only(rows, rows["status"] == "sold")
on_feed = only(rows, rows["status"] == "on feed")
year_ago = only(pigs, pigs["week_ending"] <= usda_week - pd.Timedelta(days=358))
pig_yoy = (
    usda_pig / float(year_ago["cash_usd_per_head"].to_numpy()[-1]) - 1 if len(year_ago) else None
)
uses_model = len(book.user_set) == 0
rank = margin_rank(m, sold["margin_usd"].to_numpy(dtype=float))
first_sold = pd.Timestamp(str(sold["placed"].min())) if len(sold) else pd.Timestamp(today)

with head.container():
    verb = "make" if m >= 0 else "lose"
    action = masthead(
        f"A pig placed today would {verb} {usd(abs(m))}.",
        f"Bought at {usd(c.pig_usd_per_head + c.adder_usd_per_head)} and sold around "
        f"{day(sold_date, "%b %d")} into {contract_label(this_contract)} hogs at {usd(hog)}/cwt. "
        f"You could pay up to {usd(be_pig)} for the pig and still break even.",
        kicker=f"Wean to finish · {day(today, "%B %d, %Y")}",
        meta=[
            chip(f"Hog prices: {book.price_source.lower()}", "caution",
                 "Enter today's lean hog futures under Hog prices.")
            if uses_model
            else chip("Hog prices: your futures", "good", "Using the contract prices you entered.")
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
            help="Your inputs, contract prices and hedges in a live Excel workbook: one column "
            "per placement on feed, every margin a formula.",
            on_click="ignore",
        )
st.space("small")

# --- Hero ---------------------------------------------------------------------------------
with hero("w2f"):
    left, right = st.columns([1, 1.35], gap="large")
    with left:
        quote(
            "Pig placed today",
            usd(m),
            "per pig",
            f"{signed(hog - be_hog)}/cwt vs breakeven",
            tone_of(m),
            f"Better than {rank:.0f}% of placements since {first_sold:%Y} · wean-to-finish "
            f"breakeven {usd(be_hog)}/cwt index",
        )
        on_feed_avg = avg(on_feed, "margin_usd")
        stat_strip(
            [
                ("Weaned pig", usd(c.pig_usd_per_head + c.adder_usd_per_head),
                 (f"USDA {usd(c.pig_usd_per_head)} + {usd(c.adder_usd_per_head)} yours"
                  if c.adder_usd_per_head else "USDA cash price, no adder"),
                 "neutral"),
                ("Most you can pay", usd(be_pig), f"{signed(be_pig - c.pig_usd_per_head)} vs USDA",
                 tone_of(be_pig - c.pig_usd_per_head)),
                ("Pigs on feed", usd(on_feed_avg) if len(on_feed) else "–",
                 f"avg, {len(on_feed)} weeks placed", tone_of(on_feed_avg if len(on_feed) else 0)),
            ]
        )  # fmt: skip
    with right:
        recent = only(rows, rows["placed"] >= rows["placed"].max() - pd.DateOffset(years=3))
        r_sold = only(recent, recent["status"] == "sold")
        chart_title(
            f"Placements sold since {r_sold['placed'].min():%b %Y} averaged "
            f"{usd(avg(r_sold, 'margin_usd'))} a pig"
            if len(r_sold)
            else "Margin by week placed",
            "Margin per pig by week placed · sold at the index, on feed at futures",
        )
        fig = go.Figure()
        for status, opacity in (("sold", 1.0), ("on feed", 0.45)):
            part = only(recent, recent["status"] == status)
            fig.add_bar(
                x=part["placed"],
                y=part["margin_usd"],
                name="Sold" if status == "sold" else "On feed (projected)",
                marker={"color": [POS if v >= 0 else NEG for v in part["margin_usd"]],
                        "opacity": opacity, "cornerradius": 2},
                customdata=np.stack([pd.to_datetime(part["sold"]).dt.strftime("%b %d, %Y"),
                                     part["priced_on"],
                                     part["pig_usd"], part["hog_usd_per_cwt"]], axis=-1)
                if len(part) else None,
                hovertemplate="Placed %{x|%b %d, %Y}, sold %{customdata[0]}<br>"
                "Pig $%{customdata[2]:.2f} · hogs $%{customdata[3]:.2f} (%{customdata[1]})<br>"
                "<b>%{y:$,.2f} per pig</b><extra></extra>",
            )  # fmt: skip
        if len(on_feed):
            projection_band(fig, on_feed["placed"].min() - pd.Timedelta(days=3),
                            on_feed["placed"].max() + pd.Timedelta(days=4), "ON FEED")  # fmt: skip
        fig.add_hline(y=0, line={"color": INK, "width": 1})
        fig.update_yaxes(tickprefix="$")
        fig.update_xaxes(tickformat="%b %Y")
        fig.update_layout(bargap=0.15, showlegend=False, hovermode="closest")
        chart(fig, 290)
    source_note(
        "USDA AMS National Direct Feeder Pig Report (early weaned 10-12 lb, cash); "
        "USDA AMS LM_HG201 (Lean Hog Index); USDA NASS (Iowa corn)",
        "sold pigs use the index in their sale week and Iowa corn over their months on feed; "
        "soybean meal and DDGS from 2022 too; non-feed costs are today's inputs",
    )

st.space("medium")

# --- Weaned pig price + cost per pig --------------------------------------------------------
left, mid, right = st.columns([1.25, 0.06, 1])
with left:
    hist = only(pigs, pigs["week_ending"] >= pigs["week_ending"].max() - pd.DateOffset(years=4))
    chg = (
        f", {abs(pig_yoy):.0%} {'below' if pig_yoy < 0 else 'above'} a year ago" if pig_yoy else ""
    )
    pv = seasonal.verdict(seasonal.by_week(pigs.set_index("week_ending")["cash_usd_per_head"]))
    chart_title(
        f"Weaned pigs are {usd(usda_pig)} a head{chg}",
        "USDA early weaned pigs, 10-12 lb, cash composite, $/head delivered · weekly"
        + (f" · {pv.sentence()}" if pv else ""),
    )
    pf = go.Figure()
    band = only(hist, hist["low_usd_per_head"].notna() & hist["high_usd_per_head"].notna())
    pf.add_scatter(x=band["week_ending"], y=band["high_usd_per_head"], mode="lines",
                   line={"width": 0}, hoverinfo="skip", showlegend=False)  # fmt: skip
    pf.add_scatter(x=band["week_ending"], y=band["low_usd_per_head"], mode="lines",
                   line={"width": 0}, fill="tonexty", fillcolor="rgba(31,92,69,0.10)",
                   hoverinfo="skip", showlegend=False)  # fmt: skip
    pf.add_scatter(
        x=hist["week_ending"],
        y=hist["cash_usd_per_head"],
        mode="lines",
        line={"color": HISTORY, "width": 2},
        hovertemplate="Week ending %{x|%b %d, %Y}: $%{y:.2f}<extra></extra>",
        showlegend=False,
    )
    mm, _, _ = mars_data("feeder")
    formula_note = ""
    if not mm.empty:  # My Market News: formula (contract) pigs alongside cash
        fm = mm[pd.to_datetime(mm["week_ending"]) >= hist["week_ending"].min()]
        fm = fm.dropna(subset=["ew_formula_usd"])
        pf.add_scatter(x=pd.to_datetime(fm["week_ending"]), y=fm["ew_formula_usd"], mode="lines",
                       line={"color": ACCENT, "width": 1.4, "dash": "dot"},
                       hovertemplate="Formula, week ending %{x|%b %d, %Y}: $%{y:.2f}"
                       "<extra></extra>", showlegend=False)  # fmt: skip
        last52 = fm[pd.to_datetime(fm["week_ending"]) >= fm["week_ending"].max()
                    - pd.Timedelta(weeks=52)]  # fmt: skip
        both = mm.dropna(subset=["ew_formula_usd", "ew_cash_usd"]).tail(52)
        prem = float((both["ew_formula_usd"] - both["ew_cash_usd"]).mean()) if len(both) else 0.0
        if len(last52):
            end_tag(pf, pd.Timestamp(str(fm["week_ending"].iloc[-1])),
                    float(fm["ew_formula_usd"].iloc[-1]), "Formula", ACCENT)  # fmt: skip
            formula_note = f"; dotted: formula pigs, {usd(prem)} over cash on average this year"
    ref_line(pf, be_pig, f"Most you can pay today {usd(be_pig)}", ACCENT, side="left")
    pf.update_yaxes(tickprefix="$", rangemode="tozero")
    pf.update_xaxes(tickformat="%b %Y")
    chart(pf, 300, on=PAGE)
    source_note(
        "USDA AMS National Direct Feeder Pig Report"
        + (" (live)" if pig_source == "live" else " (saved)"),
        "shaded: cash low–high range" + formula_note + "; breakeven uses today's inputs and "
        f"the {contract_label(this_contract)} price",
    )
with mid:
    st.markdown(
        '<div class="hp-vrule" style="height:400px"></div>',
        unsafe_allow_html=True,
    )
with right:
    t = cost_table(c)
    lines = t.drop(index="Total cost")
    feed = sum(feed_lines(c).values())
    chart_title(
        f"Feed is {usd(feed)} a pig, {feed / cost:.0%} of the cost; the pig "
        f"{lines.loc['Weaned pig', 'share']:.0%}",
        f"Cost per pig by line · total {usd(cost)}",
    )
    order = lines.iloc[::-1]
    feed_names = set(feed_lines(c))
    bars = go.Figure(
        go.Bar(
            y=order.index,
            x=order["usd_per_head"],
            orientation="h",
            marker={"color": [ACCENT if n in feed_names else "#9aa79f" for n in order.index],
                    "cornerradius": 3},
            text=[f"{usd(v)}  ·  {s:.0%}" for v, s in zip(order["usd_per_head"], order["share"],
                                                        strict=True)],
            textposition="outside",
            textfont={"size": 11.5, "color": INK_2},
            cliponaxis=False,
            hovertemplate="%{y}: %{text}<extra></extra>",
        )
    )  # fmt: skip
    bars.update_xaxes(visible=False, range=[0, float(order["usd_per_head"].max()) * 1.55])
    bars.update_yaxes(tickfont={"size": 12.5, "color": INK}, ticksuffix="  ", showgrid=False)
    bars.update_layout(hovermode="closest", bargap=0.35, showlegend=False)
    chart(bars, 340, on=PAGE)
    source_note("your inputs", "feed lines in green")

rule()

# --- Placing ahead ----------------------------------------------------------------------------
fwd = book.forward
if fwd is not None and len(fwd):
    season = pig_seasonality(pigs)
    good = fwd[fwd["most_usd"] >= fwd["pig_expected_usd"]]
    best = fwd.loc[fwd["margin_usd"].idxmax()]
    left, mid, right = st.columns([1.5, 0.06, 1])
    with left:
        chart_title(
            f"Pigs placed the week of {best['placed']:%b %d} look best: {usd(best['margin_usd'])} "
            "a pig"
            if len(good) == 0 or best["margin_usd"] < 0
            else f"{len(good)} of the next {len(fwd)} weeks pay for a pig at the usual price",
            "Most you can pay for a weaned pig placed each week (bars) vs what weaned pigs usually "
            "cost then (line) · at today's contract prices",
        )
        fp = go.Figure()
        fp.add_bar(x=fwd["placed"], y=fwd["most_usd"],
                   marker={"color": [POS if a >= b else NEG for a, b in
                                     zip(fwd["most_usd"], fwd["pig_expected_usd"], strict=True)],
                           "opacity": 0.8, "cornerradius": 2},
                   customdata=np.stack([fwd["contract"], fwd["margin_usd"]], axis=-1),
                   hovertemplate="Placed week of %{x|%b %d}: worth $%{y:.2f}<br>sells into "
                   "%{customdata[0]} · margin at the usual pig price $%{customdata[1]:.2f}"
                   "<extra></extra>")  # fmt: skip
        fp.add_scatter(x=fwd["placed"], y=fwd["pig_expected_usd"], mode="lines",
                       line={"color": HISTORY, "width": 2},
                       hovertemplate="Usual USDA price %{x|%b %d}: $%{y:.2f}"
                       "<extra></extra>")  # fmt: skip
        end_tag(fp, fwd["placed"].iloc[-1], float(fwd["pig_expected_usd"].iloc[-1]), "Usual price",
                HISTORY)  # fmt: skip
        fp.add_hline(y=0, line={"color": INK, "width": 1})
        fp.update_yaxes(tickprefix="$")
        fp.update_xaxes(tickformat="%b %d")
        fp.update_layout(showlegend=False, bargap=0.2, hovermode="closest",
                         margin={"l": 4, "r": 80, "t": 8, "b": 4})  # fmt: skip
        chart(fp, 300, on=PAGE)
        source_note(
            "model: today's contract prices"
            + (f" ({book.price_source.lower()})" if not book.user_set else "")
            + " and corn curve; usual price = today's USDA price moved by the seasonal pattern",
            "green: worth more than pigs usually cost that week",
        )
    with mid:
        st.markdown('<div class="hp-vrule" style="height:380px"></div>', unsafe_allow_html=True)
    with right:
        by_m = season.groupby(lambda w: min(12, (w - 1) * 12 // 52 + 1)).mean()
        dear, cheap = MONTHS[int(by_m.idxmax()) - 1], MONTHS[int(by_m.idxmin()) - 1]
        chart_title(
            f"Weaned pigs are dearest in {dear} and cheapest in {cheap}",
            "USDA early weaned price vs its year's average, by month · full years since 2021",
        )
        fs = go.Figure(
            go.Bar(
                x=MONTHS,
                y=(by_m.to_numpy() - 1) * 100,
                marker={"color": [NEG if v > 1 else POS for v in by_m], "cornerradius": 3},
                hovertemplate="%{x}: %{y:+.0f}% vs the year<extra></extra>",
            )
        )  # fmt: skip
        fs.update_yaxes(ticksuffix="%", zeroline=True, zerolinecolor="#cfc8b9")
        fs.update_layout(showlegend=False, bargap=0.35, hovermode="closest")
        chart(fs, 300, on=PAGE)
        source_note("USDA AMS Feeder Pig Report", "red: dearer than usual for a buyer")
    rule()

# --- Pigs on feed table + what-to-pay grid ---------------------------------------------------
left, mid, right = st.columns([1.15, 0.06, 1])
with left:
    if len(on_feed):
        total = avg(on_feed, "margin_usd")
        chart_title(
            f"Pigs on feed project {usd(total)} a head on average",
            f"Each week placed in the last {c.days_on_feed} days, at its USDA pig price",
        )
        show = on_feed.sort_values(by="placed", ascending=False).to_dict("records")
        table(
            ["Placed", "Pig", "Sells", "Priced on", "Hogs $/cwt", "Cost", "Margin"],
            [
                [f"{r['placed']:%b %d}", usd(r["pig_usd"]), f"{r['sold']:%b %d}",
                 str(r["priced_on"]).replace(" ", " "),
                 usd(r["hog_usd_per_cwt"]), usd(r["cost_usd"]), usd(r["margin_usd"])]
                for r in show
            ],
            emphasis_col=5,
        )  # fmt: skip
        source_note(
            "USDA weaned pig prices + your inputs",
            "pigs placed in weeks USDA didn't report are not shown",
        )
    else:
        chart_title("No pigs on feed in the data", "USDA weaned pig prices are missing")
with mid:
    st.markdown(
        '<div class="hp-vrule" style="height:440px"></div>',
        unsafe_allow_html=True,
    )
with right:
    hogs = np.arange(hog - 15, hog + 15.01, 5)
    pig_lo = max(0.0, round(c.pig_usd_per_head / 5) * 5 - 20)
    pig_px = np.arange(pig_lo, pig_lo + 40.01, 5)
    z = np.array([[margin_usd(c, h, pig=p) for p in pig_px] for h in hogs])
    chart_title(
        f"At {usd(hog, 0)} hogs, a pig is worth up to {usd(be_pig, 0)}",
        f"Margin per pig placed today by weaned pig price and {contract_label(this_contract)} "
        "hog price",
    )
    lim = float(np.abs(z).max()) or 1.0
    heat = go.Figure(
        go.Heatmap(
            z=z,
            x=[f"${p:.0f}" for p in pig_px],
            y=[f"${h:.2f}" for h in hogs],
            colorscale=[[0.0, NEG], [0.5, "#f3f1ec"], [1.0, POS]],
            zmin=-lim,
            zmax=lim,
            xgap=2,
            ygap=2,
            text=[[usd(v, 0) for v in row] for row in z],
            texttemplate="%{text}",
            textfont={"size": 11},
            hovertemplate="Pig %{x} · hogs %{y}/cwt<br>%{text} per pig<extra></extra>",
            showscale=False,
        )
    )
    col = int(np.argmin(np.abs(pig_px - c.pig_usd_per_head)))
    heat.add_shape(type="rect", xref="x", yref="y", x0=col - 0.5, x1=col + 0.5, y0=2.5, y1=3.5,
                   line={"color": INK, "width": 2})  # fmt: skip
    heat.update_xaxes(title="Weaned pig, $/head", showline=False, ticks="", type="category")
    heat.update_yaxes(title="Lean hog, $/cwt", showgrid=False, type="category")
    heat.update_layout(hovermode="closest")
    chart(heat, 330, on=PAGE)
    source_note("model", "today's USDA price and your contract price outlined")

with st.expander("Every placement week"):
    st.dataframe(
        rows.sort_values("placed", ascending=False),
        hide_index=True,
        column_config={
            "placed": st.column_config.DateColumn("Placed", format="MMM D, YYYY"),
            "sold": st.column_config.DateColumn("Sold", format="MMM D, YYYY"),
            "status": "Status",
            "priced_on": "Priced on",
            "pig_usd": st.column_config.NumberColumn("Pig $", format="dollar"),
            "hog_usd_per_cwt": st.column_config.NumberColumn("Hogs $/cwt", format="dollar"),
            "corn_usd_per_bu": st.column_config.NumberColumn("Corn $/bu", format="dollar"),
            "revenue_usd": st.column_config.NumberColumn("Revenue", format="dollar"),
            "cost_usd": st.column_config.NumberColumn("Cost", format="dollar"),
            "margin_usd": st.column_config.NumberColumn("Margin", format="dollar"),
        },
    )
    excel_button(
        {"Every placement week": rows, **({"Placing ahead": book.forward}
         if book.forward is not None else {}),
         "Pig seasonality": pig_seasonality(pigs).rename("vs year average").rename_axis(
             "ISO week").reset_index(),
         "Cost per pig": cost_table(c).reset_index(names="line")},
        "wean_to_finish", "Wean to finish placements", "USDA AMS Feeder Pig Report, LM_HG201",
        label="Download all of it (Excel)",
    )  # fmt: skip
