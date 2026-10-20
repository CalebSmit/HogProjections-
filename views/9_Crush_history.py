"""Crush history: what weaned pigs cost and what they turned out to be worth, week by week."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj.crush import MONTHS, annual_summary, by_month, margin_rank, margin_usd, month_average
from hogproj.ui import (
    ACCENT,
    HISTORY,
    INK,
    LINE,
    NEG,
    PAGE,
    POS,
    chart,
    chart_title,
    chip,
    crush_book,
    end_tag,
    hero,
    masthead,
    quote,
    rule,
    signed,
    source_note,
    stat_strip,
    table,
    tone_of,
    usd,
)

book = crush_book()
c, rows = book.c, book.rows
sold = pd.DataFrame(rows[rows["status"] == "sold"]).sort_values(by="placed")
m = sold["margin_usd"].to_numpy(dtype=float)
paid = sold["pig_usd"].to_numpy(dtype=float)
worth = sold["worth_usd"].to_numpy(dtype=float)
placed = pd.to_datetime(sold["placed"])
first, last = placed.min(), placed.max()
months = month_average(rows)
best_month, worst_month = str(months.idxmax()), str(months.idxmin())
today_margin = margin_usd(c, book.hog)
rank = margin_rank(today_margin, m)
last52 = m[placed.to_numpy() >= np.datetime64(last - pd.DateOffset(weeks=52))]
gap = float(worth.mean() - paid.mean())

masthead(
    f"Since {first:%Y}, a wean-to-finish pig has {'made' if m.mean() >= 0 else 'lost'} "
    f"{usd(abs(float(m.mean())))} on average.",
    f"Across {len(sold)} weeks of USDA weaned pigs placed {first:%b %Y} to {last:%b %Y}, "
    f"{(m > 0).mean():.0%} made money. Pigs placed in {best_month} did best "
    f"({usd(float(months[best_month]))} a head); {worst_month} placements did worst "
    f"({usd(float(months[worst_month]))}).",
    kicker="Crush history · wean to finish",
    meta=[chip("Feed at the prices of the time", "good",
               "Hog prices, Iowa corn (since 2020), soybean meal and DDGS (since Feb 2022) are "
               "historical USDA prices; non-feed costs are today's inputs.")],
)  # fmt: skip

st.space("small")

# --- Hero: paid vs worth --------------------------------------------------------------------
with hero("history"):
    left, right = st.columns([1, 1.45], gap="large")
    with left:
        quote(
            "Average margin per pig",
            usd(float(m.mean())),
            "per pig",
            f"{(m > 0).mean():.0%} of weeks profitable",
            tone_of(float(m.mean())),
            f"Paid {usd(float(paid.mean()))} for a pig worth {usd(float(worth.mean()))} on "
            f"average ({signed(gap)})",
        )
        stat_strip(
            [
                ("Last 52 weeks", usd(float(last52.mean())) if len(last52) else "–",
                 "average margin sold", tone_of(float(last52.mean()) if len(last52) else 0)),
                ("Best week", usd(float(m.max())),
                 f"placed {placed.iloc[int(m.argmax())]:%b %d, %Y}",
                 "good"),
                ("Today vs history", f"{rank:.0f}th", "percentile of a pig placed today",
                 tone_of(rank - 50)),
            ]
        )  # fmt: skip
    with right:
        chart_title(
            "What pigs cost vs what they turned out to be worth",
            "Per head, by week placed · worth = the price that would have broken even",
        )
        fig = go.Figure()
        fig.add_scatter(x=placed, y=worth, mode="lines", name="Worth",
                        line={"color": ACCENT, "width": 2},
                        hovertemplate="Placed %{x|%b %d, %Y}<br>Worth $%{y:.2f}"
                        "<extra></extra>")  # fmt: skip
        fig.add_scatter(x=placed, y=paid, mode="lines", name="Paid",
                        line={"color": HISTORY, "width": 1.5, "dash": "dot"},
                        hovertemplate="Placed %{x|%b %d, %Y}<br>Paid $%{y:.2f}"
                        "<extra></extra>")  # fmt: skip
        end_tag(fig, placed.iloc[-1], float(worth[-1]), "Worth", ACCENT)
        end_tag(fig, placed.iloc[-1], float(paid[-1]), "Paid", HISTORY)
        fig.add_hline(y=0, line={"color": LINE, "width": 1})
        fig.update_yaxes(tickprefix="$")
        fig.update_xaxes(tickformat="%b %Y")
        fig.update_layout(showlegend=False, margin={"l": 4, "r": 60, "t": 8, "b": 4})
        chart(fig, 300)
    source_note(
        "USDA AMS Feeder Pig Report (paid, plus your adder); USDA AMS LM_HG201 (index at sale); "
        "USDA NASS (Iowa corn)",
        "gap between the lines is the margin per pig",
    )

st.space("medium")

# --- When to place: year x month ------------------------------------------------------------
left, mid, right = st.columns([1.45, 0.06, 1])
with left:
    grid = by_month(rows)
    z = grid.to_numpy(dtype=float)
    z_all = np.vstack([z, months.to_numpy(dtype=float)])
    labels = [str(y) for y in grid.index] + ["Average"]
    lim = float(np.nanmax(np.abs(z_all))) or 1.0
    chart_title(
        f"{best_month} placements made the most; {worst_month} the least",
        f"Average margin per pig by month placed · sold about {c.days_on_feed} days later",
    )
    heat = go.Figure(
        go.Heatmap(
            z=z_all,
            x=MONTHS,
            y=labels,
            colorscale=[[0.0, NEG], [0.5, "#f3f1ec"], [1.0, POS]],
            zmin=-lim,
            zmax=lim,
            xgap=2,
            ygap=2,
            text=[["" if np.isnan(v) else usd(v, 0) for v in r] for r in z_all],
            texttemplate="%{text}",
            textfont={"size": 11},
            hovertemplate="%{y} %{x}: %{text} per pig<extra></extra>",
            showscale=False,
        )
    )
    heat.update_yaxes(autorange="reversed", type="category", showgrid=False)
    heat.update_xaxes(type="category", side="top", showline=False, ticks="")
    heat.add_shape(type="rect", xref="paper", yref="y", x0=0, x1=1, y0=len(labels) - 1.5,
                   y1=len(labels) - 0.5, line={"color": INK, "width": 1.5})  # fmt: skip
    heat.update_layout(hovermode="closest")
    chart(heat, 340, on=PAGE)
    source_note("model on USDA prices", "months with no sold placements are blank")
with mid:
    st.markdown(
        '<div class="hp-vrule" style="height:420px"></div>',
        unsafe_allow_html=True,
    )
with right:
    chart_title(
        f"A pig placed today ranks in the {rank:.0f}th percentile",
        f"Margin per pig across {len(m)} placement weeks · today at {usd(today_margin)}",
    )
    bins = np.arange(np.floor(m.min() / 5) * 5, np.ceil(m.max() / 5) * 5 + 5, 5)
    counts, edges = np.histogram(m, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    hist = go.Figure(
        go.Bar(
            x=centers,
            y=counts,
            width=4.4,
            marker={"color": [POS if x >= 0 else NEG for x in centers], "opacity": 0.85,
                    "cornerradius": 2},
            hovertemplate="%{x:$,.0f} a pig: %{y} weeks<extra></extra>",
        )
    )  # fmt: skip
    hist.add_vline(x=today_margin, line={"color": INK, "width": 2})
    hist.add_annotation(x=today_margin, y=1, yref="paper", text=f"Today {usd(today_margin)}",
                        showarrow=False, xanchor="left", xshift=6, yanchor="top",
                        font={"size": 11, "color": INK})  # fmt: skip
    hist.update_xaxes(tickprefix="$")
    hist.update_yaxes(title="weeks")
    hist.update_layout(showlegend=False, hovermode="closest", bargap=0)
    chart(hist, 340, on=PAGE)
    source_note(
        "model",
        f"today prices the pig at {usd(book.hog)}/cwt, the "
        + ("seasonal estimate" if not book.user_set else "price you entered")
        + " for the contract it sells into",
    )

rule()

# --- Annual summary + best/worst weeks ---------------------------------------------------------
left, mid, right = st.columns([1.3, 0.06, 1])
with left:
    s = annual_summary(rows)
    good_year = s.loc[s["margin_usd"].idxmax()]
    chart_title(
        f"{int(good_year['year'])} was the best year: {usd(float(good_year['margin_usd']))} a pig",
        "By year placed · per pig",
    )
    table(
        ["Year", "Paid", "Worth", "Margin", "Weeks profitable", "Worst week"],
        [
            [str(int(r["year"])) + ("*" if r["weeks"] < 50 else ""), usd(r["paid_usd"]),
             usd(r["worth_usd"]), usd(r["margin_usd"]), f"{r['profitable']:.0%}",
             usd(r["worst_usd"])]
            for r in s.to_dict("records")
        ],
        emphasis_col=2,
    )  # fmt: skip
    source_note("model on USDA prices", "* partial year: only the weeks placed and sold so far")
with mid:
    st.markdown(
        '<div class="hp-vrule" style="height:330px"></div>',
        unsafe_allow_html=True,
    )
with right:
    chart_title("Best and worst weeks to have placed", "Per pig · placed → sold")
    ranked = sold.sort_values(by="margin_usd")
    pick = pd.concat([ranked.tail(4).iloc[::-1], ranked.head(4)])
    table(
        ["Placed", "Paid", "Hogs $/cwt", "Margin"],
        [
            [f"{r['placed']:%b %d, %Y}", usd(r["pig_usd"]), usd(r["hog_usd_per_cwt"]),
             usd(r["margin_usd"])]
            for r in pick.to_dict("records")
        ],
    )  # fmt: skip
    source_note("model on USDA prices", "top four, then bottom four")

with st.expander("How this is calculated"):
    st.markdown(
        f"""
Each USDA weekly early weaned pig price (cash composite, plus your adder) is a placement on the
Monday of that week. The pig is sold {c.days_on_feed} days later at the **Lean Hog Index**
averaged over its sale week, plus your basis, at {c.weight_lb_live:.0f} lb live and
{c.carcass_yield:.0%} yield. Corn is the **Iowa cash price** averaged over its months on feed
(USDA daily bids; NASS before Aug 2020), and soybean meal and DDGS are Iowa prices of the time
from Feb 2022 (today's inputs before that); non-feed costs are today's inputs on the Wean to finish
page. **Worth** is the pig price at which that placement would have broken even: worth − paid =
margin. Change any input on Wean to finish and this history updates.
"""
    )
    st.download_button(
        "Download every placement (CSV)",
        sold.to_csv(index=False),
        "crush_history.csv",
        "text/csv",
        icon=":material/download:",
    )
