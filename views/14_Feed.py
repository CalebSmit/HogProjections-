"""Feed prices: Iowa cash corn, basis, soybean meal and DDGS — history, the curve ahead, and
what feed costs per pig."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj.crush import corn_contract_for, feed_lines
from hogproj.ui import (
    ACCENT,
    HISTORY,
    PAGE,
    chart,
    chart_title,
    corn_curve,
    crush_book,
    end_tag,
    feed_monthly,
    feed_prices,
    hero,
    masthead,
    projection_band,
    quote,
    rule,
    source_note,
    stat_strip,
    tone_of,
    usd,
)

fd, fd_source, _ = feed_prices()


def series(item: str) -> pd.DataFrame:
    x = fd[fd["item"] == item].sort_values("date")
    return pd.DataFrame({"date": pd.to_datetime(x["date"]), "v": x["value"].to_numpy(dtype=float)})


corn = series("corn_cash_iowa")
basis = series("corn_basis_iowa")
sbm, ddgs = series("sbm_iowa"), series("ddgs_iowa")
curve, curve_day = corn_curve()
book = crush_book()
c = book.c

if corn.empty:
    masthead(
        "No Iowa corn prices saved yet.",
        "Connect to the internet to load USDA reports.",
        kicker="Feed prices",
    )
    st.stop()

now = float(corn["v"].iloc[-1])
now_day = pd.Timestamp(corn["date"].iloc[-1])
year_ago = corn[corn["date"] <= now_day - pd.Timedelta(days=364)]
yoy = now / float(year_ago["v"].iloc[-1]) - 1 if len(year_ago) else None

# Basis now vs the same weeks of earlier years.
b_now, b_norm, b_word = None, None, ""
if len(basis) > 260:
    b_now = float(basis["v"].iloc[-1])
    doy = basis["date"].dt.dayofyear.to_numpy()
    same = basis[(np.abs(doy - now_day.dayofyear) <= 10) & (basis["date"].dt.year < now_day.year)]
    if len(same):
        b_norm = float(same["v"].mean())
        diff = b_now - b_norm
        b_word = (
            "stronger than usual"
            if diff > 0.05
            else "weaker than usual"
            if diff < -0.05
            else "about normal"
        )


def cents(b: float) -> str:
    return f"{abs(b) * 100:.0f}¢ {'under' if b < 0 else 'over'} futures"


nearby = None
if curve:
    current = [k for k in curve if k >= corn_contract_for(now_day.year, now_day.month)]
    nearby = min(current) if current else None

masthead(
    f"Iowa cash corn is {usd(now)} a bushel"
    + (f", {abs(yoy):.0%} {'above' if yoy > 0 else 'below'} a year ago." if yoy else "."),
    (
        f"The basis is {cents(b_now)}, {b_word} for {now_day:%B} ({cents(b_norm)} on average). "
        if b_now is not None and b_norm is not None
        else ""
    )
    + f"Feed for a pig placed today costs about {usd(sum(feed_lines(c).values()))}.",
    kicker=f"Feed prices · {now_day:%B %d, %Y}",
)

st.space("small")
with hero("feed"):
    left, right = st.columns([1, 1.5], gap="large")
    with left:
        quote(
            "Iowa cash corn",
            usd(now),
            "/bu",
            "" if yoy is None else f"{yoy:+.0%} vs a year ago".replace("-", "−"),
            tone_of(-(yoy or 0)),
            "Average of six regions, country elevators (USDA AMS)",
        )
        items = []
        if b_now is not None:
            items.append(
                (
                    "Basis",
                    f"{b_now * 100:+.0f}¢".replace("-", "−"),
                    f"normal {b_norm * 100:+.0f}¢".replace("-", "−") if b_norm is not None else "",
                    "neutral",
                )
            )
        if len(sbm):
            items.append(
                ("Soybean meal", usd(float(sbm["v"].iloc[-1]), 0), "Iowa $/ton", "neutral")
            )
        if len(ddgs):
            items.append(("DDGS", usd(float(ddgs["v"].iloc[-1]), 0), "Iowa $/ton", "neutral"))
        stat_strip(items[:3])
    with right:
        chart_title(
            "Corn since 2020, and priced ahead off the futures curve",
            "Iowa cash $/bu · dashed: CBOT settlements plus today's basis",
        )
        fig = go.Figure()
        wk = corn.set_index("date")["v"].resample("W-FRI").mean().dropna()
        fig.add_scatter(
            x=wk.index,
            y=wk.to_numpy(),
            mode="lines",
            line={"color": HISTORY, "width": 1.8},
            hovertemplate="%{x|%b %d, %Y}: $%{y:.2f}<extra></extra>",
        )
        if curve and b_now is not None:
            pts = sorted(k for k in curve if pd.Timestamp(year=k[0], month=k[1], day=15) > now_day)
            xs = [now_day] + [pd.Timestamp(year=y, month=m, day=15) for y, m in pts]
            ys = [now] + [curve[k] + b_now for k in pts]
            fig.add_scatter(
                x=xs,
                y=ys,
                mode="lines+markers",
                line={"color": ACCENT, "width": 2, "dash": "dash"},
                marker={"size": 6},
                hovertemplate="%{x|%b %Y}: $%{y:.2f} delivered<extra></extra>",
            )
            projection_band(fig, now_day, xs[-1], "FUTURES + BASIS")
            end_tag(fig, xs[-1], ys[-1], usd(ys[-1]), ACCENT)
        fig.update_yaxes(tickprefix="$")
        fig.update_xaxes(tickformat="%b %Y")
        fig.update_layout(showlegend=False, margin={"l": 4, "r": 60, "t": 8, "b": 4})
        chart(fig, 300)
    source_note(
        "USDA AMS Iowa Daily Cash Grain Bids (My Market News history; CBOT settlements in the "
        "same report)" + ("" if fd_source == "live" else " · saved"),
        "the curve is what the futures market prices corn at, delivered to you at today's basis",
    )

st.space("medium")

left, mid, right = st.columns([1, 0.06, 1])
with left:
    if len(basis) > 260:
        chart_title(
            f"Basis is {b_word}" if b_word else "Iowa corn basis",
            "Cents under nearby futures, by week of year · shaded: range of earlier years",
        )
        bw = basis.set_index("date")["v"].resample("W-FRI").mean().dropna().reset_index()
        iso = bw["date"].dt.isocalendar()
        bw["year"], bw["wk"] = iso["year"].to_numpy(), iso["week"].to_numpy()
        this = int(bw["year"].max())
        prior = bw[bw["year"] < this]
        lo, hi = prior.groupby("wk")["v"].min() * 100, prior.groupby("wk")["v"].max() * 100
        fb = go.Figure()
        fb.add_scatter(
            x=hi.index,
            y=hi.to_numpy(),
            mode="lines",
            line={"width": 0},
            hoverinfo="skip",
            showlegend=False,
        )
        fb.add_scatter(
            x=lo.index,
            y=lo.to_numpy(),
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor="rgba(133,127,115,0.16)",
            hoverinfo="skip",
            showlegend=False,
        )
        cur = bw[bw["year"] == this]
        fb.add_scatter(
            x=cur["wk"],
            y=cur["v"] * 100,
            mode="lines",
            line={"color": ACCENT, "width": 2.2},
            hovertemplate=f"{this} week %{{x}}: %{{y:.0f}}¢<extra></extra>",
        )
        if len(cur):
            end_tag(fb, int(cur["wk"].iloc[-1]), float(cur["v"].iloc[-1] * 100), str(this), ACCENT)
        fb.update_yaxes(ticksuffix="¢")
        fb.update_xaxes(title="week of year", range=[1, 53])
        fb.update_layout(showlegend=False, margin={"l": 4, "r": 56, "t": 8, "b": 4})
        chart(fb, 280, on=PAGE)
        source_note(
            "USDA AMS Iowa Daily Cash Grain Bids",
            "a stronger (less negative) basis means local corn is dear relative to futures",
        )
with mid:
    st.markdown('<div class="hp-vrule" style="height:360px"></div>', unsafe_allow_html=True)
with right:
    if len(sbm):
        chart_title(
            f"Soybean meal {usd(float(sbm['v'].iloc[-1]), 0)}, DDGS "
            f"{usd(float(ddgs['v'].iloc[-1]), 0) if len(ddgs) else '–'} a ton",
            "Iowa, FOB, $/ton, weekly",
        )
        fs = go.Figure()
        fs.add_scatter(
            x=sbm["date"],
            y=sbm["v"],
            mode="lines",
            line={"color": ACCENT, "width": 2},
            hovertemplate="SBM %{x|%b %d, %Y}: $%{y:.0f}<extra></extra>",
        )
        end_tag(fs, sbm["date"].iloc[-1], float(sbm["v"].iloc[-1]), "SBM", ACCENT)
        if len(ddgs):
            fs.add_scatter(
                x=ddgs["date"],
                y=ddgs["v"],
                mode="lines",
                line={"color": HISTORY, "width": 1.6},
                hovertemplate="DDGS %{x|%b %d, %Y}: $%{y:.0f}<extra></extra>",
            )
            end_tag(fs, ddgs["date"].iloc[-1], float(ddgs["v"].iloc[-1]), "DDGS", HISTORY)
        fs.update_yaxes(tickprefix="$", rangemode="tozero")
        fs.update_xaxes(tickformat="%b %Y")
        fs.update_layout(showlegend=False, margin={"l": 4, "r": 60, "t": 8, "b": 4})
        chart(fs, 280, on=PAGE)
        source_note("USDA AMS National Grain and Oilseed Processor Feedstuff Report (Iowa)")

rule()
# What feed has cost per pig: your ration at each month's Iowa prices.
cm, sm, dm = feed_monthly("corn_cash_iowa"), feed_monthly("sbm_iowa"), feed_monthly("ddgs_iowa")
if len(cm):
    m = cm.rename(columns={"usd": "corn"}).merge(
        sm.rename(columns={"usd": "sbm"}), on="month", how="left"
    )
    m = m.merge(dm.rename(columns={"usd": "ddgs"}), on="month", how="left")
    m["sbm"] = m["sbm"].fillna(c.sbm_usd_per_ton)
    m["ddgs"] = m["ddgs"].fillna(c.ddgs_usd_per_ton)
    m["feed"] = (
        c.corn_lb * m["corn"] / 56
        + c.sbm_lb * m["sbm"] / 2000
        + c.ddgs_lb * m["ddgs"] / 2000
        + c.other_feed_lb * c.other_feed_usd_per_lb
    )
    peak = m.loc[m["feed"].idxmax()]
    chart_title(
        f"Feed per pig peaked at {usd(float(peak['feed']))} in "
        f"{pd.Timestamp(peak['month']):%B %Y}; {usd(float(m['feed'].iloc[-1]))} now",
        "Wean-to-finish feed cost per pig at each month's Iowa prices, your ration",
    )
    ff = go.Figure(
        go.Bar(
            x=m["month"],
            y=m["feed"],
            marker={"color": ACCENT, "opacity": 0.85, "cornerradius": 2},
            hovertemplate="%{x|%b %Y}: $%{y:.2f} a pig<extra></extra>",
        )
    )
    ff.update_yaxes(tickprefix="$")
    ff.update_xaxes(tickformat="%b %Y")
    ff.update_layout(showlegend=False, bargap=0.1, hovermode="closest")
    chart(ff, 260, on=PAGE)
    source_note(
        "model on USDA Iowa prices",
        "soybean meal and DDGS before Feb 2022 at today's "
        "inputs; change the ration on Wean to finish",
    )
