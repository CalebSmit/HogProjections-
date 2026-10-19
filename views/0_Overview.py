"""Overview: are we making money, what does the next year look like, and what moves it?"""

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from hogproj.export import build_report
from hogproj.herd import pigs_sold_per_sow_yr
from hogproj.markets import seasonal_factors
from hogproj.outlook import drivers, headline, monthly, project, summary, synced
from hogproj.ui import (
    INK,
    INK_2,
    MUTED,
    NEG,
    POS,
    REFERENCE,
    SERIES,
    card,
    chart,
    current_plan,
    delta,
    footer_note,
    hog_index,
    insight,
    page_header,
    section,
    signed,
    usd,
    usd_short,
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
d = drivers(plan, factors, today)

actions = page_header(
    "Farm outlook",
    f"{plan.herd.sows_start:,.0f} sows · farrow to finish · next 12 months from {today:%b %d, %Y}",
    eyebrow="Overview",
)

# Rank months per pig sold: months have 4 or 5 sale weeks, so totals mostly track week count.
per_pig = months["profit_usd_per_head"].fillna(0)
best, worst = months.loc[per_pig.idxmax()], months.loc[per_pig.idxmin()]
above = int((months["hog_usd_per_cwt_carcass"] >= be).sum())
lever = d.iloc[0]

# --- Takeaway ---------------------------------------------------------------------------
# Status follows profit (incl. manure credit); breakeven follows ISU and excludes the credit.
profit = hl["profit_usd_per_head"]
if profit >= 0 and hl["gap_cwt_carcass"] >= 0:
    tone, status = "good", "Above breakeven"
    head = f"Making {usd(profit)} per pig at today's hog price."
elif profit >= 0:
    tone, status = "caution", "Profitable only with manure credit"
    head = f"Making {usd(profit)} per pig, thanks to the manure credit."
else:
    tone, status = "bad", "Below breakeven"
    head = f"Losing {usd(-profit)} per pig at today's hog price."
facts = [
    ("Price move to break even", f"{signed(-hl['gap_cwt_carcass'])}/cwt"),
    ("Months above breakeven", f"{above} of {len(months)}"),
    ("Best month, per pig", f"{best['month']:%B} · {usd(best['profit_usd_per_head'])}"),
    ("Toughest month, per pig", f"{worst['month']:%B} · {usd(worst['profit_usd_per_head'])}"),
    ("Biggest lever", str(lever["driver"])),
]
insight(tone, status, head, facts)

actions.download_button(
    "Export report",
    build_report(plan, r, today, note, f"{status}: {head}"),
    f"hog_outlook_{today:%Y-%m-%d}.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    icon=":material/download:",
    help="Excel workbook: summary, assumptions, 24-month outlook with chart, costs, weekly detail.",
    width="stretch",
)

# --- KPIs -------------------------------------------------------------------------------
series = idx["lean_hog_index_usd_per_cwt_carcass"]
week_ago = float(series.iloc[-6]) if len(series) > 6 else hog
k1, k2, k3, k4 = st.columns(4)
k1.metric(
    "Hog price used",
    usd(hog),
    delta(hog - week_ago, suffix=" this week"),
    help="Lean hog, $/cwt carcass. Starts at the latest USDA-based index; edit it under "
    "Costs & returns. The line shows the last 3 months.",
    chart_data=series.tail(63).round(2).tolist(),
    chart_type="area",
    height="stretch",
)
k2.metric(
    "Breakeven price",
    usd(be),
    f"{usd(hl['breakeven_cwt_live'])} live",
    delta_color="off",
    delta_arrow="off",
    help="All costs per pig ÷ carcass cwt sold. Excludes the manure credit (ISU convention).",
    height="stretch",
)
k3.metric(
    "Profit per pig",
    usd(profit),
    delta(hl["gap_cwt_carcass"], suffix="/cwt vs breakeven"),
    help="At today's hog price, including the manure credit. Bars: next 12 months, per pig.",
    chart_data=months["profit_usd_per_head"].fillna(0).round(2).tolist(),
    chart_type="bar",
    height="stretch",
)
k4.metric(
    "Profit, next 12 months",
    usd_short(year["profit_usd"]),
    f"{year['pigs_sold']:,.0f} pigs sold",
    delta_color="off",
    delta_arrow="off",
    help="With the seasonal price path. Line: running total over the year.",
    chart_data=r["margin_usd"].iloc[:52].cumsum().round(0).tolist(),
    chart_type="line",
    height="stretch",
)
st.space("small")

# --- Outlook ----------------------------------------------------------------------------
labels = [f"{m:%b}" for m in months["month"]]
left, right = st.columns(2, gap="medium")
with left, card("price"):
    if above == 0:
        title = "Hog prices stay below breakeven all year"
    elif above == len(months):
        title = "Hog prices stay above breakeven all year"
    else:
        title = f"Hog prices clear breakeven in {above} of {len(months)} months"
    section(title, "Lean hog, $/cwt carcass, monthly average · seasonal pattern from USDA history")
    price = months["hog_usd_per_cwt_carcass"]
    fig = go.Figure()
    fig.add_scatter(
        x=labels,
        y=price,
        mode="lines+markers",
        line={"color": SERIES[0], "width": 2.25, "shape": "spline", "smoothing": 0.6},
        marker={"size": 6, "color": SERIES[0], "line": {"color": "white", "width": 1.5}},
        hovertemplate="%{x}: $%{y:.2f}/cwt<extra></extra>",
        showlegend=False,
    )
    fig.add_hline(y=be, line={"color": REFERENCE, "width": 1, "dash": "dash"})
    fig.add_annotation(
        x=labels[-1],
        y=be,
        text=f"Breakeven {usd(be)}",
        showarrow=False,
        xanchor="right",
        yanchor="bottom",
        font={"size": 11, "color": REFERENCE},
    )
    lo = min(float(price.to_numpy().min()), be)
    hi = max(float(price.to_numpy().max()), be)
    pad = (hi - lo) * 0.18 + 1
    fig.update_yaxes(range=[lo - pad, hi + pad], tickprefix="$")
    fig.update_layout(hovermode="closest")
    chart(fig, 300)
with right, card("months"):
    section(
        f"{'Strongest' if per_pig.max() >= 0 else 'Smallest loss'} in {best['month']:%B}, "
        f"{'weakest' if per_pig.min() >= 0 else 'largest loss'} in {worst['month']:%B}",
        "Profit per pig sold by month"
        + (" · first month is partial" if bool(months["partial"].iloc[0]) else ""),
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
            x=labels[i],
            y=v,
            text=usd(v, 0),
            showarrow=False,
            yshift=10 if v >= 0 else -10,
            font={"size": 11, "color": INK},
        )
    bars.update_yaxes(tickprefix="$", zeroline=True, zerolinecolor="#cfcfc8", zerolinewidth=1)
    bars.update_layout(hovermode="closest", bargap=0.35)
    chart(bars, 300)

# --- Drivers + assumptions --------------------------------------------------------------
left, right = st.columns([3, 2], gap="medium")
with left, card("drivers"):
    section(
        f"{lever['driver']} moves profit most",
        "Change in next-12-month profit when one input moves and the rest hold",
    )
    dd = d.iloc[::-1]
    names = [
        f"{n}<br><span style='font-size:11px;color:{MUTED}'>{lo} / {hi}</span>"
        for n, lo, hi in zip(dd["driver"], dd["low_label"], dd["high_label"], strict=True)
    ]
    tor = go.Figure()
    for col, lab in [("low_usd", "low_label"), ("high_usd", "high_label")]:
        tor.add_bar(
            y=names,
            x=dd[col],
            orientation="h",
            marker={"color": [POS if v >= 0 else NEG for v in dd[col]], "cornerradius": 3},
            text=[signed(v, usd_short) for v in dd[col]],
            customdata=dd[lab],
            textposition="outside",
            textfont={"size": 11, "color": INK_2},
            cliponaxis=False,
            hovertemplate="%{customdata}: %{text}<extra></extra>",
            showlegend=False,
        )
    span = float(dd[["low_usd", "high_usd"]].abs().to_numpy().max()) * 1.7 or 1.0
    tor.update_xaxes(
        range=[-span, span],
        tickformat="$~s",
        showline=False,
        ticks="",
        showgrid=True,
        gridcolor="#efefeb",
        zeroline=True,
        zerolinecolor="#bdbdb6",
    )
    tor.update_yaxes(
        tickfont={"size": 12, "color": INK}, gridcolor="rgba(0,0,0,0)", ticksuffix="  "
    )
    tor.update_layout(barmode="overlay", hovermode="closest", bargap=0.42)
    chart(tor, 320)
with right, card("assumptions"):
    section("Key assumptions", "Edit on Herd flow and Costs & returns")
    h, c = plan.herd, plan.cost
    rows = [
        ("Sows", f"{h.sows_start:,.0f}"),
        ("Pigs sold / sow / yr", f"{pigs_sold_per_sow_yr(h):.1f}"),
        ("Market weight", f"{h.weight_lb_live_market:.0f} lb live"),
        ("Corn", f"{usd(c.corn_usd_per_bu)}/bu"),
        ("Soybean meal", f"{usd(c.sbm_usd_per_ton, 0)}/ton"),
        ("Cost per pig", usd(hl["cost_usd_per_head"])),
        ("Price path", "Seasonal" if plan.seasonal else "Flat"),
    ]
    st.markdown(
        '<div style="margin-top:6px">'
        + "".join(
            '<div style="display:flex;justify-content:space-between;padding:8px 0;'
            'border-bottom:1px solid #f0f0ec;font-size:13.5px">'
            f'<span style="color:{MUTED}">{k}</span>'
            f'<span style="color:{INK};font-weight:500;font-variant-numeric:tabular-nums">'
            f"{v.replace('$', '&#36;')}</span></div>"
            for k, v in rows
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    st.space("small")
    a, b = st.columns(2)
    a.page_link("views/1_Herd_flow.py", label="Herd flow", icon=":material/timeline:")
    b.page_link("views/2_Costs_and_returns.py", label="Costs", icon=":material/request_quote:")

st.space("small")
with st.expander("Methodology & sources", icon=":material/info:"):
    st.markdown(
        """
- **Costs** follow Iowa State University's Estimated Livestock Returns (farrow to finish),
  reproduced to the cent for its 2026 months, with sow costs spread over pigs sold per sow.
- **Hog price** starts at the CME Lean Hog Index, rebuilt from USDA AMS report LM_HG201, and
  follows the typical monthly pattern in that history. See Risk for the range of outcomes.
- **Herd flow** is a weekly cohort model: 16 weeks gestation, 3 weeks nursing, 22 weeks to
  market.
- Prices are \\$/cwt carcass unless marked live (live ≈ carcass × 0.75).
"""
    )
footer_note(f"Prepared {today:%B %d, %Y} · {note}")
