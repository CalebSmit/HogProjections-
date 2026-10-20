"""Overview: are we making money, what does the next year look like, and what moves it?"""

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj import supply
from hogproj.export import build_report
from hogproj.finance import CostInputs
from hogproj.herd import pigs_sold_per_sow_yr
from hogproj.markets import seasonal_factors
from hogproj.outlook import drivers, headline, monthly, project, summary, synced
from hogproj.risk import RiskInputs, estimate_hog_dynamics, simulate_profit
from hogproj.text import day
from hogproj.ui import (
    ACCENT,
    HISTORY,
    INK,
    INK_2,
    MUTED,
    NEG,
    PAGE,
    POS,
    assumption_bar,
    chart,
    chart_title,
    chip,
    current_plan,
    end_tag,
    excel_button,
    feed_default,
    feed_help,
    hero,
    hog_index,
    kv_table,
    latest_hog_index,
    live_number,
    masthead,
    md,
    nass_data,
    projection_band,
    quote,
    ref_line,
    rule,
    signed,
    source_note,
    stat_strip,
    tone_of,
    usd,
    usd_short,
    uses_benchmarks,
)

idx, source, note = hog_index()
plan = synced(current_plan())
factors = seasonal_factors(idx)
today = date.today()
hl = headline(plan)
r = project(plan, factors, today)
year = summary(r)
months = monthly(r)
hog = plan.cost.lean_hog_usd_per_cwt_carcass
be = hl["breakeven_cwt_carcass"]
profit = hl["profit_usd_per_head"]
d = drivers(plan, factors, today)
lever = d.iloc[0]
per_pig = months["profit_usd_per_head"].fillna(0)
best, worst = months.loc[per_pig.idxmax()], months.loc[per_pig.idxmin()]
above = int((months["hog_usd_per_cwt_carcass"] >= be).sum())

# Projection range: the same simulation as the Risk page, summarised as bands.
r52 = r.iloc[:52]
dyn = estimate_hog_dynamics(idx, factors)
sim = simulate_profit(
    r52["marketed_head"].to_numpy(),
    r52["sold_lb_carcass"].to_numpy() / 100,
    r52["hog_usd_per_cwt_carcass"].to_numpy(),
    plan.cost,
    dyn,
    RiskInputs(n_paths=1000, corn_vol_annual=0.0),
)
bands = {q: np.percentile(sim["hog_paths"], q, axis=0) for q in (10, 25, 75, 90)}
peak_i = int(r52["hog_usd_per_cwt_carcass"].to_numpy().argmax())
peak_price = float(r52["hog_usd_per_cwt_carcass"].iloc[peak_i])
peak_month = pd.Timestamp(r52["date"].iloc[peak_i])

# --- Masthead: the finding as the headline ----------------------------------------------
if profit >= 0 and hl["gap_cwt_carcass"] >= 0:
    title = f"At {usd(hog)}, each pig sold makes {usd(profit)}."
elif profit >= 0:
    title = f"At {usd(hog)}, pigs make {usd(profit)} each, but only with the manure credit."
else:
    title = f"At {usd(hog)}, each pig sold loses {usd(-profit)}."
if peak_price < be:
    dek = (
        f"Hogs need {usd(be)}/cwt to cover costs. The usual seasonal rally tops out near "
        f"{usd(peak_price, 0)} in {peak_month:%B}, still short of breakeven."
    )
else:
    dek = (
        f"Hogs need {usd(be)}/cwt to cover costs. The usual seasonal rally clears it in "
        f"{above} of the next 12 months, peaking near {usd(peak_price, 0)} in {peak_month:%B}."
    )
inputs_chip = (
    chip(
        "Benchmark inputs",
        "caution",
        "Herd and costs are U.S. industry benchmarks. Set yours on Herd flow and Costs & returns.",
    )
    if uses_benchmarks()
    else chip("Your inputs", "good", "Using the herd and cost inputs you entered.")
)
actions = masthead(
    title,
    dek,
    kicker=f"Farm outlook · {plan.herd.sows_start:,.0f} sows · {day(today, '%B %d, %Y')}",
    meta=[inputs_chip],
)

# Quick what-ifs: the same inputs as Costs & returns (shared keys), so every page agrees.
_d = CostInputs()
with assumption_bar("overview"):
    with st.popover(md(f"Hog price · {usd(hog)}/cwt")):
        live_number(
            st,
            "Lean hog price ($/cwt carcass)",
            0.0,
            200.0,
            latest_hog_index(),
            0.5,
            key="cost_hog",
            help="Starts at the latest Lean Hog Index. Try the price you expect to average.",
        )
    with st.popover(md(f"Corn · {usd(plan.cost.corn_usd_per_bu)}/bu")):
        live_number(
            st,
            "Corn ($/bu)",
            0.0,
            20.0,
            feed_default("corn_cash_iowa"),
            0.05,
            key="cost_corn",
            help=feed_help("corn_cash_iowa"),
        )
    st.segmented_control(
        "Hog price over time",
        ["Seasonal", "Flat"],
        default="Seasonal",
        key="cost_price_path",
        label_visibility="collapsed",
        help="Seasonal follows the usual summer high and winter low; Flat holds today's price.",
    )
    st.caption("More inputs on Herd flow and Costs & returns")


def report_extras() -> dict[str, pd.DataFrame]:
    """Market, wean-to-finish and sow farm sheets for the farm report (built on click)."""
    from hogproj.sowfarm import cost_lines
    from hogproj.ui import crush_book, market_signals, sow_from_state

    sigs = market_signals()
    book = crush_book()
    on_feed = book.rows[book.rows["status"] == "on feed"]
    return {
        "Market signals": pd.DataFrame([vars(x) for x in sigs]),
        "Wean to finish on feed": on_feed,
        "Sow farm cost": cost_lines(sow_from_state()).reset_index(names="line"),
    }


actions.download_button(
    "Export report",
    lambda: build_report(plan, r, today, note, title, report_extras()),
    f"hog_outlook_{today:%Y-%m-%d}.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    icon=":material/download:",
    help="Excel workbook: summary, assumptions, 24-month outlook with chart, costs, weekly detail.",
    width="stretch",
    on_click="ignore",
)

# --- Hero: quote, stat strip, signature chart -------------------------------------------
series = idx["lean_hog_index_usd_per_cwt_carcass"]
us_supply = supply.next_six_months(nass_data()[0])["pct"] or 0.0
index_now = float(series.iloc[-1])
week_ago = float(series.iloc[-6]) if len(series) > 6 else index_now
custom_price = abs(hog - round(index_now, 2)) > 0.005
hog_note, hog_tone = (
    (f"market index {usd(index_now)}", "neutral")
    if custom_price
    else (f"{signed(index_now - week_ago)} this week", tone_of(index_now - week_ago))
)
whose = "your" if custom_price else "today's"
with hero():
    quote(
        "Breakeven price",
        usd(be),
        "/cwt carcass",
        f"{usd(abs(hl['gap_cwt_carcass']))} "
        f"{'above' if hl['gap_cwt_carcass'] < 0 else 'below'} {whose} {usd(hog)}",
        tone_of(hl["gap_cwt_carcass"]),
        f"{usd(hl['breakeven_cwt_live'])}/cwt live · {usd(hl['cost_usd_per_head'])} cost per pig"
        " · Iowa State Estimated Livestock Returns structure",
    )
    stat_strip(
        [
            ("Hog price" + (" (yours)" if custom_price else ""), usd(hog), hog_note, hog_tone),
            ("Profit per pig", usd(profit), "at today's price", tone_of(profit)),
            (
                "Next 12 months",
                usd_short(year["profit_usd"]),
                f"{year['pigs_sold']:,.0f} pigs sold",
                "neutral",
            ),
            ("Above breakeven", f"{above} of 12 mo", "seasonal path", "neutral"),
            ("Biggest lever", str(lever["driver"]),
             f"{signed(float(lever['high_usd']), usd_short)} per {lever['high_label']}",
             "neutral"),
            ("U.S. hog supply", f"{us_supply:+.1%}".replace("-", "\u2212"),
             "next 6 months vs last year", "neutral"),
        ]
    )  # fmt: skip
    st.space("small")
    chart_title(
        "Hog prices recover with the season, but stay below breakeven"
        if float(bands[90].max()) < be
        else "Where hog prices could go over the next year",
        "Lean Hog Index, $/cwt carcass · solid: last 12 months actual · dashed: projection, shaded"
        " band: 8 in 10 simulated years",
    )
    hist = idx[pd.to_datetime(idx["index_date"]) >= pd.Timestamp(today) - pd.Timedelta(days=365)]
    hx = pd.to_datetime(hist["index_date"])
    hy = hist["lean_hog_index_usd_per_cwt_carcass"]
    px = r52["date"]
    fig = go.Figure()
    projection_band(fig, px.iloc[0], px.iloc[-1])
    for lo_q, hi_q, alpha in [(10, 90, 0.10), (25, 75, 0.16)]:
        fig.add_scatter(
            x=px, y=bands[hi_q], mode="lines", line={"width": 0}, hoverinfo="skip",
            showlegend=False,
        )  # fmt: skip
        fig.add_scatter(
            x=px,
            y=bands[lo_q],
            mode="lines",
            fill="tonexty",
            fillcolor=f"rgba(31,92,69,{alpha})",
            line={"width": 0},
            hoverinfo="skip",
            showlegend=False,
        )
    fig.add_scatter(
        x=hx,
        y=hy,
        mode="lines",
        line={"color": HISTORY, "width": 2},
        hovertemplate="%{x|%b %d, %Y}: $%{y:.2f} actual<extra></extra>",
        showlegend=False,
    )
    fig.add_scatter(
        x=px,
        y=r52["hog_usd_per_cwt_carcass"],
        mode="lines",
        line={"color": ACCENT, "width": 2.25, "dash": "dash"},
        hovertemplate="%{x|%b %d, %Y}: $%{y:.2f} projected<extra></extra>",
        showlegend=False,
    )
    ref_line(fig, be, f"Breakeven {usd(be)}")
    end_tag(fig, hx.iloc[-1], float(hy.iloc[-1]), usd(float(hy.iloc[-1])), HISTORY)
    end_tag(
        fig, px.iloc[-1], float(r52["hog_usd_per_cwt_carcass"].iloc[-1]),
        usd(float(r52["hog_usd_per_cwt_carcass"].iloc[-1])), ACCENT,
    )  # fmt: skip
    hy_np = hy.to_numpy(dtype=float)
    lo = min(float(hy_np.min()), float(bands[10].min()), be)
    hi = max(float(hy_np.max()), float(bands[90].max()), be)
    pad = (hi - lo) * 0.08
    fig.update_yaxes(range=[lo - pad, hi + pad], tickprefix="$", side="left")
    fig.update_xaxes(tickformat="%b %Y", range=[hx.iloc[0], px.iloc[-1] + pd.Timedelta(days=40)])
    fig.update_layout(hovermode="x unified", margin={"l": 4, "r": 64, "t": 8, "b": 4})
    chart(fig, 370)
    source_note(
        "USDA AMS LM_HG201 (CME Lean Hog Index rebuilt daily)",
        "projection = today's price × the typical seasonal pattern; range from 1,000 simulated "
        "years (see Risk)",
    )

st.space("medium")

# --- Two editorial charts on the page ---------------------------------------------------
labels = [f"{m:%b}" for m in months["month"]]
left, mid, right = st.columns([1, 0.06, 1.15])
with left:
    chart_title(
        f"{'Strongest' if per_pig.max() >= 0 else 'Smallest loss'} in {best['month']:%B}, "
        f"{'weakest' if per_pig.min() >= 0 else 'deepest loss'} in {worst['month']:%B}",
        "Profit per pig sold, by month"
        + (" · first month partial" if bool(months["partial"].iloc[0]) else ""),
    )
    bars = go.Figure(
        go.Bar(
            x=labels,
            y=per_pig,
            marker={"color": [POS if v >= 0 else NEG for v in per_pig], "cornerradius": 3},
            customdata=[usd_short(v) for v in months["profit_usd"]],
            hovertemplate="%{x}: $%{y:,.2f} per pig<br>%{customdata} total<extra></extra>",
        )
    )
    for i in {int(per_pig.to_numpy().argmax()), int(per_pig.to_numpy().argmin())}:
        v = float(per_pig.iloc[i])
        bars.add_annotation(
            x=labels[i], y=v, text=usd(v, 0), showarrow=False,
            yshift=10 if v >= 0 else -10, font={"size": 11, "color": INK},
        )  # fmt: skip
    bars.update_yaxes(tickprefix="$", zeroline=True, zerolinecolor="#cfc8b9", zerolinewidth=1)
    bars.update_layout(hovermode="closest", bargap=0.38)
    chart(bars, 290, on=PAGE)
    source_note("model projection", "months have 4 or 5 sale weeks, so compare per pig")
with mid:
    st.markdown(
        '<div class="hp-vrule" style="height:420px"></div>',
        unsafe_allow_html=True,
    )
with right:
    chart_title(
        f"{lever['driver']} moves the year's result most",
        "Change in next-12-month profit when one input moves and the rest hold",
    )
    dd = d.iloc[::-1]
    names = [
        f"{n}<br><span style='font-size:10.5px;color:{MUTED}'>{lo} / {hi}</span>"
        for n, lo, hi in zip(dd["driver"], dd["low_label"], dd["high_label"], strict=True)
    ]
    tor = go.Figure()
    for col in ("low_usd", "high_usd"):
        tor.add_bar(
            y=names,
            x=dd[col],
            orientation="h",
            marker={"color": [POS if v >= 0 else NEG for v in dd[col]], "cornerradius": 3},
            text=[signed(v, usd_short) for v in dd[col]],
            textposition="outside",
            textfont={"size": 11, "color": INK_2},
            cliponaxis=False,
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    span = float(dd[["low_usd", "high_usd"]].abs().to_numpy().max()) * 1.7 or 1.0
    tor.update_xaxes(
        range=[-span, span],
        tickformat="$~s",
        showline=False,
        ticks="",
        showgrid=True,
        gridcolor="#ece8de",
        zeroline=True,
        zerolinecolor="#b9b2a3",
    )
    tor.update_yaxes(tickfont={"size": 12, "color": INK}, showgrid=False, ticksuffix="  ")
    tor.update_layout(barmode="overlay", hovermode="closest", bargap=0.42)
    chart(tor, 290, on=PAGE)
    source_note("model projection", "each bar is one input moved by a typical amount")
    excel_button({"Monthly profit": months, "What moves it most": d, "Weekly projection": r},
                 "farm_outlook", "Farm outlook projection", "model")  # fmt: skip

rule()

# --- Assumptions + method ----------------------------------------------------------------
left, mid, right = st.columns([1, 0.06, 1])
with left:
    chart_title("Assumptions behind these numbers", "Edit on Herd flow and Costs & returns")
    h, c = plan.herd, plan.cost
    kv_table(
        [
            ("Sows", f"{h.sows_start:,.0f}"),
            ("Pigs sold per sow per year", f"{pigs_sold_per_sow_yr(h):.1f}"),
            ("Market weight", f"{h.weight_lb_live_market:.0f} lb live"),
            ("Corn", f"{usd(c.corn_usd_per_bu)}/bu"),
            ("Soybean meal", f"{usd(c.sbm_usd_per_ton, 0)}/ton"),
            ("Cost per pig, before manure credit", usd(hl["cost_usd_per_head"])),
            ("Hog price path", "Seasonal" if plan.seasonal else "Flat"),
        ]
    )
with right:
    chart_title("How this is calculated", "Sources and method")
    st.markdown(
        f"""
<div style="font-size:13.5px;color:{INK_2};line-height:1.65">
<p><b style="color:{INK}">Costs</b> follow Iowa State University's Estimated Livestock Returns
for farrow-to-finish, reproduced to the cent for its 2026 months, with sow costs spread over pigs
sold per sow.</p>
<p><b style="color:{INK}">Hog prices</b> are the CME Lean Hog Index, rebuilt each day from USDA
AMS report LM_HG201. The outlook applies the typical monthly pattern in that history.</p>
<p><b style="color:{INK}">Herd</b> is a weekly cohort model: 16 weeks gestation, 3 weeks
nursing, 22 weeks to market. Prices are &#36;/cwt carcass unless marked live (live ≈ carcass
× 0.75).</p>
</div>""",
        unsafe_allow_html=True,
    )
