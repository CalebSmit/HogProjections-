"""Hog market: the Lean Hog Index and what's behind it: cutout, spread, slaughter, weights."""

import calendar

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hogproj import hogmarket as hm
from hogproj import seasonal, supply
from hogproj.freshness import is_current
from hogproj.markets import seasonal_factors
from hogproj.text import day
from hogproj.ui import (
    ACCENT,
    HISTORY,
    INK,
    MUTED,
    NEG,
    PAGE,
    POS,
    REFERENCE,
    chart,
    chart_title,
    cold_storage,
    crush_book,
    end_tag,
    ers_data,
    excel_button,
    fas_data,
    forecast_accuracy,
    hero,
    hog_index,
    hog_market,
    market_signals,
    mars_data,
    masthead,
    nass_data,
    pork_cutout,
    quote,
    ref_line,
    rule,
    seasonal_chart,
    signal_list,
    signed,
    source_note,
    stat_strip,
    storage_now,
    table,
    tone_of,
    usd,
    wasde_data,
    wasde_history,
    wasde_now,
)

idx, source, _ = hog_index()
cut_raw, cut_source, _ = pork_cutout()
d = hog_market()
dates = pd.to_datetime(idx["index_date"])
values = idx["lean_hog_index_usd_per_cwt_carcass"].to_numpy(dtype=float)
latest_date, latest = dates.iloc[-1], float(values[-1])


def value_days_ago(days: int) -> float | None:
    mask = (dates <= latest_date - pd.Timedelta(days=days)).to_numpy()
    return float(values[mask][-1]) if mask.any() else None


week, month, year = value_days_ago(7), value_days_ago(30), value_days_ago(365)
move_30 = latest - month if month is not None else 0.0
last_year = values[(dates >= latest_date - pd.Timedelta(days=365)).to_numpy()]
supply_pct = supply.next_six_months(nass_data()[0])["pct"]
sigs = market_signals()
tone, why = hm.overall(sigs)
good = [s.name.lower() for s in sigs if s.tone == "good"]
bad = [s.name.lower() for s in sigs if s.tone == "bad"]


def joined(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


lead = {
    "good": "The market behind hog prices looks supportive.",
    "bad": "The market behind hog prices looks soft.",
    "neutral": "Signals behind hog prices are mixed.",
}[tone]
detail = []
if bad:
    detail.append(f"Working against hogs: {joined(bad)}.")
if good:
    detail.append(f"Working for them: {joined(good)}.")

masthead(
    lead,
    f"Lean hogs at {usd(latest)}, {'up' if move_30 >= 0 else 'down'} {usd(abs(move_30))} in a "
    f"month. " + " ".join(detail),
    kicker="Hog market",
)

st.space("small")
with hero():
    left, right = st.columns([1.75, 1], gap="large")
    with left:
        pct = move_30 / month if month else 0.0
        quote(
            "Lean Hog Index",
            usd(latest),
            "/cwt carcass",
            f"{signed(move_30)} ({pct:+.1%}) 30 days".replace("-", "−"),
            tone_of(move_30),
            f"Index for {day(latest_date, '%b %d, %Y')} · rebuilt from USDA AMS LM_HG201",
        )
        span = st.segmented_control(
            "Range",
            ["3M", "6M", "1Y", "3Y", "All"],
            default="1Y",
            key="mkt_span",
            label_visibility="collapsed",
        )
        days = {"3M": 91, "6M": 182, "1Y": 365, "3Y": 1096}.get(span or "1Y")
        sel = (
            (dates >= latest_date - pd.Timedelta(days=days)).to_numpy()
            if days
            else np.ones(len(dates), dtype=bool)
        )
        vx, vy = dates[sel], values[sel]
        fig = go.Figure(
            go.Scatter(
                x=vx,
                y=vy,
                mode="lines",
                line={"color": HISTORY, "width": 2},
                hovertemplate="%{x|%b %d, %Y}: $%{y:.2f}<extra></extra>",
            )
        )
        end_tag(fig, vx.iloc[-1], latest, usd(latest), NEG if move_30 < 0 else POS)
        lo, hi = float(vy.min()), float(vy.max())
        fig.update_yaxes(range=[lo - (hi - lo) * 0.12, hi + (hi - lo) * 0.12], tickprefix="$")
        fig.update_xaxes(tickformat="%b %Y")
        fig.update_layout(showlegend=False, margin={"l": 4, "r": 64, "t": 8, "b": 4})
        chart(fig, 280)
        stat_strip(
            [
                ("Week ago", "—" if week is None else usd(week), "", "neutral"),
                ("1 year ago", "—" if year is None else usd(year),
                 "" if year is None else signed(latest - year) + " since", "neutral"),
                ("52-week range",
                 f"{usd(float(last_year.min()), 0)}–{usd(float(last_year.max()), 0)}",
                 "", "neutral"),
            ]
        )  # fmt: skip
    with right:
        st.markdown(
            '<div class="hp-quote-label" style="margin-bottom:2px">What the market is saying</div>',
            unsafe_allow_html=True,
        )
        signal_list([(s.name, s.value, s.read, s.tone, s.rule) for s in sigs])
        st.caption(f"Overall: {why}. Hover a signal for its rule.")
    source_note(
        "USDA AMS LM_HG201 (index, slaughter, weights), LM_PK602 (cutout); USDA NASS Hogs and "
        "Pigs (supply)",
        "index matched CME's published value to the cent on Oct 12, 2026",
    )
    excel_button(
        {"Lean Hog Index": idx, "Signals": pd.DataFrame([vars(x) for x in sigs])},
        "lean_hog_index",
        "Lean Hog Index and market signals",
        "USDA AMS LM_HG201",
    )

st.space("medium")

# --- Cutout and packer spread ---------------------------------------------------------------
win = d[d["date"] >= d["date"].max() - pd.Timedelta(days=days or 4000)]
w = hm.weekly(d)
sp_hist = w["spread_per_head"].to_numpy(dtype=float)
p25, p75 = (float(np.nanpercentile(sp_hist, q)) for q in (25, 75))
left, mid, right = st.columns([1.2, 0.06, 1])
with left:
    cut_now = float(pd.Series(cut_raw["carcass"]).iloc[-1])
    chart_title(
        f"Pork cutout {usd(cut_now)}, {usd(cut_now - latest)} over the index",
        "Wholesale value of a carcass vs what packers pay for hogs · $/cwt carcass",
    )
    cf = go.Figure()
    cf.add_scatter(x=win["date"], y=win["cutout"], mode="lines", name="Cutout",
                   line={"color": ACCENT, "width": 2}, connectgaps=True,
                   hovertemplate="%{x|%b %d, %Y}<br>Cutout $%{y:.2f}<extra></extra>")  # fmt: skip
    cf.add_scatter(x=win["date"], y=win["index"], mode="lines", name="Lean Hog Index",
                   line={"color": HISTORY, "width": 1.5}, connectgaps=True,
                   hovertemplate="%{x|%b %d, %Y}<br>Index $%{y:.2f}<extra></extra>")  # fmt: skip
    last_cut = win.dropna(subset=["cutout"]).iloc[-1]
    last_idx = win.dropna(subset=["index"]).iloc[-1]
    end_tag(cf, last_cut["date"], float(last_cut["cutout"]), "Cutout", ACCENT)
    end_tag(cf, last_idx["date"], float(last_idx["index"]), "Index", HISTORY)
    cf.update_yaxes(tickprefix="$")
    cf.update_xaxes(tickformat="%b %Y")
    cf.update_layout(showlegend=False, margin={"l": 4, "r": 64, "t": 8, "b": 4})
    chart(cf, 290, on=PAGE)
    source_note(
        "USDA AMS LM_PK602 (afternoon cutout) and LM_HG201",
        "gap + by-products = packer gross spread",
    )
with mid:
    st.markdown(
        '<div class="hp-vrule" style="height:380px"></div>',
        unsafe_allow_html=True,
    )
with right:
    wk = w[w["week_ending"] >= w["week_ending"].max() - pd.Timedelta(days=days or 4000)]
    wk = wk.dropna(subset=["spread_per_head"])
    now_sp = float(wk["spread_per_head"].iloc[-1])
    chart_title(
        f"Packers are grossing {usd(now_sp)} a head on average this week",
        "Weekly packer gross spread per head · cutout + by-products − hogs, before plant costs",
    )
    sf = go.Figure(
        go.Bar(
            x=wk["week_ending"],
            y=wk["spread_per_head"],
            marker={"color": [POS if v >= p75 else NEG if v <= p25 else "#9aa79f"
                              for v in wk["spread_per_head"]], "cornerradius": 2},
            hovertemplate="Week ending %{x|%b %d, %Y}: $%{y:.2f}/head<extra></extra>",
        )
    )  # fmt: skip
    ref_line(sf, p75, f"Top 25% {usd(p75, 0)}", REFERENCE)
    ref_line(sf, p25, f"Bottom 25% {usd(p25, 0)}", REFERENCE)
    sf.update_yaxes(tickprefix="$")
    sf.update_xaxes(tickformat="%b %Y")
    sf.update_layout(showlegend=False, bargap=0.15, hovermode="closest")
    chart(sf, 290, on=PAGE)
    source_note("model on USDA LMR", "green: top 25% since 2020, red: bottom 25%")
    excel_button({"Daily": d, "Weekly": w}, "hog_market", "Cutout, packer spread, slaughter and "
                 "weights", "USDA AMS LM_HG201, LM_PK602")  # fmt: skip

rule()


# --- Against the usual season: index, cutout, weights, slaughter --------------------------------
def season(col: str, frame: pd.DataFrame, date_col: str = "date", how: str = "mean"
           ) -> tuple[pd.DataFrame, seasonal.Verdict | None]:  # fmt: skip
    wk = seasonal.by_week(frame.set_index(date_col)[col], how)
    return wk, seasonal.verdict(wk)


idx_wk, idx_v = season("index", d)
cut_wk, cut_v = season("cutout", d)
if idx_v is not None and cut_v is not None:
    left, mid, right = st.columns([1, 0.06, 1])
    for col, name, wk, v in ((left, "Lean hogs", idx_wk, idx_v),
                             (right, "The cutout", cut_wk, cut_v)):  # fmt: skip
        with col:
            verb, its = ("are", "their") if name == "Lean hogs" else ("is", "its")
            chart_title(f"{name} {verb} {v.sentence(its)}",
                        f"$/cwt carcass, weekly average · shaded: {v.span} range · dotted: last "
                        "year")  # fmt: skip
            chart(seasonal_chart(wk, ",.2f", "$"), 290, on=PAGE)
            source_note(
                "USDA AMS LM_HG201" if name == "Lean hogs" else "USDA AMS LM_PK602",
                f"this week {usd(v.value)} vs a {v.span} average of {usd(v.avg)}",
            )
    with mid:
        st.markdown('<div class="hp-vrule" style="height:380px"></div>', unsafe_allow_html=True)
    rule()

wkly = w.dropna(subset=["weight_lb"]).set_index("week_ending")
wt_wk = seasonal.by_week(wkly["weight_lb"])
full = w[w["days"] >= 5].set_index("week_ending")  # holiday-short weeks look like supply drops
head_wk = seasonal.by_week(full["head"], "sum")


wt = hm.vs_year_ago(d, "weight_lb")
sl = hm.vs_year_ago(d, "head", how="sum")
left, mid, right = st.columns([1, 0.06, 1])
with left:
    chart_title(
        f"Carcasses {abs(wt['change']):.1f} lb {'heavier' if wt['change'] >= 0 else 'lighter'} "
        "than a year ago",
        "Average carcass weight, producer-sold barrows and gilts · lb · shaded: range of the 5 "
        "years before (2020 left out)",
    )
    fw = seasonal_chart(wt_wk, ".1f", suffix=" lb")
    chart(fw, 290, on=PAGE)
    source_note("USDA AMS LM_HG201", "last 4 weeks vs the same weeks a year ago")
with mid:
    st.markdown(
        '<div class="hp-vrule" style="height:380px"></div>',
        unsafe_allow_html=True,
    )
fi_all = mars_data("fi_slaughter")[0]
fi_now = hm.fi_vs_year_ago(fi_all)
if fi_now is not None and not is_current("Inspected slaughter", fi_now["end"]):
    fi_now = None  # stale here: the producer-sold count below is current
with right:
    if fi_now is not None:  # all inspected hogs: the same count the Slaughter signal uses
        fw_ = hm.fi_weekly(fi_all)
        fw_ = fw_[fw_["week_ending"] <= pd.to_datetime(fi_all["date"]).max()].tail(52)
        chart_title(
            f"Slaughter {abs(fi_now['pct']):.1%} {'above' if fi_now['pct'] >= 0 else 'below'} "
            "last year",
            "All federally inspected hogs per week · head · last 4 weeks vs the same days a year "
            "ago",
        )
        fh = go.Figure()
        fh.add_scatter(
            x=fw_["week_ending"],
            y=fw_["head_year_ago"],
            mode="lines",
            name="A year ago",
            line={"color": MUTED, "width": 1.5, "dash": "dot"},
            hovertemplate="A year earlier: %{y:,.0f}<extra></extra>",
        )
        fh.add_scatter(
            x=fw_["week_ending"],
            y=fw_["head"],
            mode="lines",
            name="This year",
            line={"color": ACCENT, "width": 2.2},
            hovertemplate="Week ending %{x|%b %d}: %{y:,.0f}<extra></extra>",
        )
        fh.update_yaxes(tickformat="~s")
        fh.update_xaxes(tickformat="%b %Y")
        fh.update_layout(showlegend=False, margin={"l": 4, "r": 8, "t": 8, "b": 4})
        chart(fh, 290, on=PAGE)
        source_note("USDA AMS Daily Livestock Slaughter (AMS_3208), packer-owned included",
                    "producer-sold barrows and gilts (LMR): "
                    + f"{sl['pct']:+.1%}".replace("-", "−") + " on the same basis")  # fmt: skip
    else:
        chart_title(
            f"Slaughter {abs(sl['pct']):.1%} {'above' if sl['pct'] >= 0 else 'below'} last year",
            "Producer-sold barrows and gilts per week · head · shaded: range of the 5 years before",
        )
        fh = seasonal_chart(head_wk, ",.0f")
        fh.update_yaxes(tickformat="~s")
        chart(fh, 290, on=PAGE)
        source_note("USDA AMS LM_HG201", "excludes packer-owned hogs; holiday-short weeks left out")

rule()

# --- USDA's outlook (WASDE) --------------------------------------------------------------------
wd, wd_source, _ = wasde_data()
if not wd.empty:
    report = str(wd["report"].iloc[0])
    pr = wd[wd["series"] == "barrows_gilts_usd_cwt_live"].copy()
    po = wd[wd["series"] == "pork_production_mlb"].copy()
    for df_ in (pr, po):
        df_["label"] = "Q" + df_["quarter"].astype(str) + " " + df_["year"].astype(str)
    prod = po.set_index(["year", "quarter"])["value"]
    po["yoy"] = [
        prod.get((y - 1, q), np.nan) for y, q in zip(po["year"], po["quarter"], strict=True)
    ]
    po["yoy"] = po["value"] / po["yoy"] - 1
    nxt = wasde_now()
    left, mid, right = st.columns([1, 0.06, 1])
    with left:
        lead_q = pr[pr["projected"]].iloc[0] if pr["projected"].any() else pr.iloc[-1]
        chart_title(
            f"USDA sees hogs at {usd(float(lead_q['value']))} live in {lead_q['label']}",
            f"Barrows and gilts, national base 51-52% lean, $/cwt live · {report} WASDE",
        )
        fb = go.Figure(
            go.Bar(
                x=pr["label"],
                y=pr["value"],
                marker={"color": [ACCENT if p else HISTORY for p in pr["projected"]],
                        "opacity": [0.55 if p else 1 for p in pr["projected"]],
                        "cornerradius": 3},
                text=[usd(v, 0) for v in pr["value"]], textposition="outside",
                textfont={"size": 11, "color": MUTED}, cliponaxis=False,
                hovertemplate="%{x}: $%{y:.2f}/cwt live<extra></extra>",
            )
        )  # fmt: skip
        fb.update_yaxes(tickprefix="$", range=[0, float(pr["value"].max()) * 1.2])
        fb.update_layout(showlegend=False, bargap=0.35, hovermode="closest")
        chart(fb, 260, on=PAGE)
        source_note(
            "USDA WASDE" + (" (live)" if wd_source == "live" else " (saved)"),
            "dark: reported · light: USDA projection · live price; the index is carcass "
            "(≈ live ÷ 0.75)",
        )
    with mid:
        st.markdown('<div class="hp-vrule" style="height:340px"></div>', unsafe_allow_html=True)
    with right:
        shown = po.dropna(subset=["yoy"])
        chart_title(
            f"USDA expects {abs(nxt['pct']):.1%} {'more' if nxt['pct'] > 0 else 'less'} pork "
            "in the next two quarters"
            if nxt
            else "Pork production vs a year earlier",
            f"Commercial pork production, change vs the same quarter a year earlier · {report}",
        )
        fp = go.Figure(
            go.Bar(
                x=shown["label"],
                y=shown["yoy"] * 100,
                marker={"color": [NEG if v > 0 else POS for v in shown["yoy"]],
                        "opacity": [0.55 if p else 1 for p in shown["projected"]],
                        "cornerradius": 3},
                hovertemplate="%{x}: %{y:+.1f}%<extra></extra>",
            )
        )  # fmt: skip
        fp.update_yaxes(ticksuffix="%", zeroline=True, zerolinecolor="#cfc8b9")
        fp.update_layout(showlegend=False, bargap=0.35, hovermode="closest")
        chart(fp, 260, on=PAGE)
        source_note("USDA WASDE", "red: more pork than a year earlier (bearish), green: less")
    acc = hm.wasde_accuracy(wasde_history()[0])
    if len(acc):
        one = acc.set_index("horizon").loc[1] if (acc["horizon"] == 1).any() else acc.iloc[0]
        ahead = "one quarter ahead" if (acc["horizon"] == 1).any() else "for the current quarter"
        st.caption(
            f"How close USDA has been: in {int(one['n'])} recent forecasts of the barrow/gilt "
            f"price {ahead}, USDA ran "
            f"{'high' if one['bias'] > 0 else 'low'} by {usd(abs(one['bias']))}/cwt live on "
            f"average"
            + (
                f" (typical miss {usd(one['mae'])})"
                if abs(one["mae"] - abs(one["bias"])) > 0.1
                else ""
            )
            + ". A small sample that grows each month; "
            "weigh USDA's price outlook with it in mind."
        )
        excel_button({"WASDE pork": wd}, "wasde_pork", "USDA WASDE pork outlook", "USDA WASDE")
    rule()

# --- How good is the app's own estimate? -------------------------------------------------------
acc_ = forecast_accuracy()
if len(acc_):
    mid_ = acc_[acc_["months_ahead"].between(3, 6)]
    miss_, better_ = float(mid_["miss"].mean()), float(mid_["better_than_no_change"].mean())
    band_ = float(mid_["within_8_in_10"].mean())
    chart_title(
        f"The seasonal estimate has missed by {usd(miss_)}/cwt on average 3–6 months out, "
        f"{better_:.0%} less than assuming prices stay put",
        f"Lean Hog Index, $/cwt carcass · {int(acc_['n'].max())} estimates replayed from the start "
        f"of each month since 2022 with only the data known then · 8 in 10 landed within "
        f"{usd(band_)}",
    )
    left, mid, right = st.columns([1.3, 0.06, 1])
    with left:
        fa = go.Figure()
        fa.add_bar(
            x=acc_["months_ahead"],
            y=acc_["miss_no_change"],
            name="Assume no change",
            marker={"color": "#cfc8b9", "cornerradius": 3},
            hovertemplate="%{x} months ahead, no change: off by $%{y:.2f}<extra></extra>",
        )
        fa.add_bar(
            x=acc_["months_ahead"],
            y=acc_["miss"],
            name="Seasonal estimate",
            marker={"color": ACCENT, "cornerradius": 3},
            hovertemplate="%{x} months ahead, seasonal: off by $%{y:.2f}<extra></extra>",
        )
        fa.update_xaxes(title="months ahead", dtick=1)
        fa.update_yaxes(tickprefix="$", title="average miss")
        fa.update_layout(barmode="group", bargap=0.3, hovermode="closest",
                         legend={"orientation": "h", "y": 1.1, "x": 0})  # fmt: skip
        chart(fa, 260, on=PAGE)
    with mid:
        st.markdown('<div class="hp-vrule" style="height:300px"></div>', unsafe_allow_html=True)
    with right:
        st.markdown(
            "**What this means.** Contract prices you haven't entered come from this estimate, "
            "and every margin is only as good as the hog price under it. A miss of "
            f"{usd(band_)}/cwt is about {usd(band_ * crush_book().c.carcass_cwt, 0)} a pig, "
            "so a projected margin closer to zero than that could go either way: the "
            "**likely range** on Hedging shows it for each contract.".replace("$", r"\$")
        )
        st.caption(f"On average the estimate ran {usd(abs(float(mid_['bias'].mean())))}/cwt "
                   f"{'high' if float(mid_['bias'].mean()) > 0 else 'low'} at 3–6 months, "
                   + ("close to unbiased." if abs(float(mid_["bias"].mean())) < 2
                      else "allow for that lean."))  # fmt: skip
    source_note(
        "model on USDA AMS LM_HG201",
        "no change = the last week's index carried "
        "forward; seasonal = the same moved by the typical month-to-month pattern",
    )
    excel_button({"Accuracy by months ahead": acc_}, "estimate_accuracy",
                 "How far the seasonal hog price estimate has missed", "model")  # fmt: skip
    rule()

# --- Cold storage -------------------------------------------------------------------------------
cs, cs_source, _ = cold_storage()
stor = storage_now()
if stor is not None:
    m_ = pd.to_datetime(cs["month"])
    last_year_ = int(m_.dt.year.max())
    left, mid, right = st.columns([1.2, 0.06, 1])
    with left:
        chart_title(
            f"Pork in storage is {abs(stor['pct']):.0%} "
            f"{'above' if stor['pct'] >= 0 else 'below'} normal for {stor['month']:%B}",
            "Frozen pork stocks, million lb, start of month · shaded: range of the 5 years before",
        )
        fs = go.Figure()
        prior = cs[(m_.dt.year < last_year_) & (m_.dt.year >= last_year_ - 5)]
        pm = pd.to_datetime(prior["month"]).dt.month
        lo_, hi_ = (
            prior.groupby(pm)["pork_stocks_mlb"].min(),
            prior.groupby(pm)["pork_stocks_mlb"].max(),
        )
        avg_ = prior.groupby(pm)["pork_stocks_mlb"].mean()
        names_ = [calendar.month_abbr[k] for k in hi_.index]
        fs.add_scatter(x=names_, y=hi_.to_numpy(), mode="lines", line={"width": 0},
                       hoverinfo="skip", showlegend=False)  # fmt: skip
        fs.add_scatter(x=names_, y=lo_.to_numpy(), mode="lines", line={"width": 0},
                       fill="tonexty", fillcolor="rgba(133,127,115,0.16)", hoverinfo="skip",
                       showlegend=False)  # fmt: skip
        fs.add_scatter(x=names_, y=avg_.to_numpy(), mode="lines", name="5-yr avg",
                       line={"color": MUTED, "width": 1.2, "dash": "dot"},
                       hovertemplate="%{x} 5-yr avg: %{y:,.0f}M lb<extra></extra>")  # fmt: skip
        cur_ = cs[m_.dt.year == last_year_]
        fs.add_scatter(x=[calendar.month_abbr[k] for k in pd.to_datetime(cur_["month"]).dt.month],
                       y=cur_["pork_stocks_mlb"], mode="lines+markers", name=str(last_year_),
                       line={"color": ACCENT, "width": 2.2}, marker={"size": 6},
                       hovertemplate=f"%{{x}} {last_year_}: %{{y:,.0f}}M lb"
                       "<extra></extra>")  # fmt: skip
        fs.update_yaxes(ticksuffix="M")
        fs.update_layout(showlegend=False, hovermode="closest")
        chart(fs, 260, on=PAGE)
        source_note("USDA ERS (NASS Cold Storage)" + (" (live)" if cs_source == "live" else
                    " (saved)"), "dotted: 5-year average")  # fmt: skip
        excel_button({"Pork in cold storage": cs}, "cold_storage", "Pork in cold storage",
                     "USDA ERS")  # fmt: skip
    with mid:
        st.markdown('<div class="hp-vrule" style="height:340px"></div>', unsafe_allow_html=True)
    with right:
        chart_title("How the signals are scored", "Each rule is fixed and written out")
        for x in sigs:
            st.markdown(f"**{x.name}** — {x.rule}.")
    rule()

# --- Demand: exports and the retail pork dollar -----------------------------------------------
trade, trade_src, _ = ers_data("pork_trade")
spreads, spreads_src, _ = ers_data("spreads")
ex = hm.exports_ytd(trade)
wx_raw, wx_src, _ = fas_data()
wx = hm.export_sales_weekly(wx_raw)
fs_ = hm.farmer_share(spreads)
if ex is not None or wx is not None or fs_ is not None:
    left, mid, right = st.columns([1, 0.06, 1])
    with left:
        by, vals, amounts, unit, note, src, sheet = pd.DataFrame(), [], [], "", "", "", {}
        big = ""
        if wx is not None:  # USDA weekly export sales (FAS key)
            by = wx["by_country"]
            big = by.index[0]
            tops = ", ".join(f"{c} {v:,.0f} t" for c, v in wx["week_top"].items())
            chart_title(
                f"Pork muscle-cut shipments are {abs(wx['pct']):.1%} "
                f"{'above' if wx['pct'] >= 0 else 'below'} last year so far; {big} takes "
                f"{by.loc[big, 'share']:.0%}",
                f"{wx['ytd_mt'] / 1000:,.0f}k metric tons shipped this year to the "
                f"{wx['label']} · last 4 weeks vs a year ago: shipments "
                + f"{wx['ship_4wk_pct']:+.0%}, new sales {wx['sales_4wk_pct']:+.0%}".replace(
                    "-", "−"
                )
                + f" · that week's biggest buyers: {tops}",
            )
            vals = [wx["pct"] * 100, *(by["pct"] * 100)]
            amounts = [wx["ytd_mt"], *by["ytd"]]
            unit = "t"
            note = (
                "weekly, about a week behind; fresh, chilled and frozen muscle cuts only, "
                "metric tons"
                + (
                    f" · all pork (ERS monthly, carcass weight): {ex['pct']:+.1%} through "
                    f"{ex['through']:%B}".replace("-", "−")
                    if ex is not None
                    else ""
                )
            )
            src = "USDA FAS Export Sales" + (" (live)" if wx_src == "live" else " (saved)")
            sheet = {"Weekly export sales by country": wx_raw}
        elif ex is not None:  # ERS monthly
            by = ex["by_country"]
            big = by.index[0]
            chart_title(
                f"Pork exports are {abs(ex['pct']):.1%} {'above' if ex['pct'] >= 0 else 'below'}"
                f" last year through {ex['through']:%B}; {big} takes "
                f"{by.loc[big, 'share']:.0%}",
                f"{ex['total_mlb']:,.0f}M lb carcass weight so far this year · change vs the "
                "same months last year, biggest buyers",
            )
            vals = [ex["pct"] * 100, *(by["pct"] * 100)]
            amounts = [ex["total_mlb"] * 1000, *by["ytd"]]
            unit, note = "k lb", "monthly, about two months behind; carcass weight"
            src = "USDA ERS Livestock and Meat International Trade" + (
                " (live)" if trade_src == "live" else " (saved)"
            )
            sheet = {"Pork trade by country": trade}
        if wx is not None or ex is not None:
            names = ["All buyers", *by.index]
            fx = go.Figure(go.Bar(
                y=names[::-1], x=vals[::-1], orientation="h",
                marker={"color": [POS if v >= 0 else NEG for v in vals[::-1]],
                        "cornerradius": 3},
                text=[f"{v:+.0f}%".replace("-", "−") for v in vals[::-1]],
                textposition="outside", cliponaxis=False, customdata=amounts[::-1],
                hovertemplate=f"%{{y}}: %{{text}} · %{{customdata:,.0f}} {unit}<extra></extra>",
            ))  # fmt: skip
            lim = max(abs(v) for v in vals) * 1.4 + 1
            fx.update_xaxes(range=[-lim, lim], ticksuffix="%", zeroline=True,
                            zerolinecolor="#cfc8b9")  # fmt: skip
            fx.update_layout(showlegend=False, hovermode="closest", bargap=0.35)
            chart(fx, 260, on=PAGE)
            source_note(src, note)
            excel_button(sheet, "pork_exports", "Pork exports by country", src)
    with mid:
        st.markdown('<div class="hp-vrule" style="height:340px"></div>', unsafe_allow_html=True)
    with right:
        if fs_ is not None:
            ya = fs_["year_ago"]
            chart_title(
                f"Farmers get {fs_['share']:.0%} of the retail pork dollar"
                + (
                    f", {'up' if fs_['share'] >= ya else 'down'} from {ya:.0%} a year ago"
                    if ya
                    else ""
                ),  # fmt: skip
                f"Cents per lb, retail weight · {fs_['month']:%B %Y}: retail "
                f"{fs_['retail']:.0f}¢, wholesale {fs_['wholesale']:.0f}¢, "
                f"farm {fs_['net_farm']:.0f}¢",
            )
            w_ = spreads.pivot_table(index="month", columns="item", values="value").sort_index()
            w_ = w_[w_.index >= w_.index.max() - pd.DateOffset(years=6)]
            fr = go.Figure()
            for col, name, color, width in (("retail", "Retail", INK, 2.0),
                                            ("wholesale", "Wholesale", MUTED, 1.6),
                                            ("net_farm", "Farm", ACCENT, 2.2)):  # fmt: skip
                if col in w_:
                    fr.add_scatter(
                        x=w_.index,
                        y=w_[col],
                        mode="lines",
                        name=name,
                        line={"color": color, "width": width},
                        hovertemplate=f"{name} %{{x|%b %Y}}: %{{y:.0f}}¢<extra></extra>",
                    )
                    end_tag(fr, w_.index[-1], float(w_[col].iloc[-1]), name, color)
            fr.update_yaxes(ticksuffix="¢", rangemode="tozero")
            fr.update_xaxes(tickformat="%Y")
            fr.update_layout(showlegend=False, margin={"l": 4, "r": 70, "t": 8, "b": 4})
            chart(fr, 260, on=PAGE)
            source_note("USDA ERS Meat Price Spreads"
                        + (" (live)" if spreads_src == "live" else " (saved)"),
                        "farm = net farm value (hog value less by-products); share = farm ÷ "
                        "retail")  # fmt: skip
            excel_button({"Pork values and spreads": spreads}, "pork_spreads",
                         "Pork values and spreads", "USDA ERS")  # fmt: skip
    rule()

# --- Seasonality + primals ---------------------------------------------------------------------
f = seasonal_factors(idx)
n_years = int(f["years"].to_numpy().max()) if not f.empty else 0
peak = int(f.loc[f["factor"].idxmax(), "month"]) if not f.empty else 7
low = int(f.loc[f["factor"].idxmin(), "month"]) if not f.empty else 1
left, mid, right = st.columns([1.2, 0.06, 1])
with left:
    chart_title(
        f"Hogs usually peak in {calendar.month_name[peak]} and bottom in "
        f"{calendar.month_name[low]}",
        f"Typical month vs its year's average · {n_years} full years",
    )
    bar = go.Figure(
        go.Bar(
            x=[calendar.month_abbr[m] for m in f["month"]],
            y=(f["factor"] - 1) * 100,
            marker={"color": [POS if v >= 1 else NEG for v in f["factor"]], "cornerradius": 3},
            hovertemplate="%{x}: %{y:+.1f}%<extra></extra>",
        )
    )
    bar.update_yaxes(ticksuffix="%", zeroline=True, zerolinecolor="#cfc8b9")
    bar.update_layout(hovermode="closest", bargap=0.38, showlegend=False)
    chart(bar, 260, on=PAGE)
    source_note("USDA AMS LM_HG201", "monthly average index ÷ that year's average")
with mid:
    st.markdown(
        '<div class="hp-vrule" style="height:340px"></div>',
        unsafe_allow_html=True,
    )
with right:
    c = cut_raw.sort_values("date")
    last = c.iloc[-1]
    wk_ago = c[c["date"] <= last["date"] - pd.Timedelta(days=7)].iloc[-1]
    yr_ago = c[c["date"] <= last["date"] - pd.Timedelta(days=364)].iloc[-1]
    chart_title("Primal values", f"$/cwt, afternoon report {pd.Timestamp(last['date']):%b %d, %Y}")
    names = [("carcass", "Carcass cutout"), ("belly", "Belly"), ("loin", "Loin"), ("ham", "Ham"),
             ("butt", "Butt"), ("picnic", "Picnic"), ("rib", "Rib")]  # fmt: skip
    table(
        ["Cut", "Value", "Week", "Year"],
        [
            [label, usd(float(last[k])), signed(float(last[k] - wk_ago[k])),
             signed(float(last[k] - yr_ago[k]))]
            for k, label in names
        ],
        emphasis_col=0,
    )  # fmt: skip
    source_note("USDA AMS LM_PK602", "change vs a week and a year earlier")
    excel_button({"Cutout and primals": cut_raw}, "pork_cutout", "Pork cutout and primal values",
                 "USDA AMS LM_PK602")  # fmt: skip
