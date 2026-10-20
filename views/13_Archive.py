"""Market archive: the weekly record since 2020 — every series in one table, by year."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from hogproj import archive
from hogproj import hogmarket as hm
from hogproj.ui import (
    ACCENT,
    BLUE_RAMP,
    HISTORY,
    PAGE,
    Tone,
    chart,
    chart_title,
    crush_book,
    end_tag,
    excel_button,
    hero,
    hog_market,
    iowa_corn,
    masthead,
    rule,
    signed,
    source_note,
    stat_strip,
    table,
    tone_of,
    usd,
    weaned_pigs,
)

pigs, _, _ = weaned_pigs()
corn, _, _ = iowa_corn()
book = crush_book()
w = archive.weekly(hm.weekly(hog_market()), pigs, corn, book.rows)
a = archive.annual(w)
this_year = int(a["year"].iloc[-1])
chg = archive.year_change(a, "index")
pig_chg = archive.year_change(a, "weaned_pig")


def fmt(col: str, v: float) -> str:
    if np.isnan(v):
        return "–"
    if col == "head":
        return f"{v / 1e6:.2f}M"
    if col == "weight_lb":
        return f"{v:.1f}"
    return usd(v)


masthead(
    f"{this_year} so far: hogs average {usd(float(a['index'].iloc[-1]))}"
    + (f", {abs(chg):.0%} {'below' if chg < 0 else 'above'} {this_year - 1}." if chg else "."),
    f"Weaned pigs average {usd(float(a['weaned_pig'].iloc[-1]))}"
    + (f" ({pig_chg:+.0%} on the year)".replace("-", "−") if pig_chg else "")
    + f". Every week since {w['week_ending'].min():%B %Y} is below, ready to download.",
    kicker="Market archive",
)

st.space("small")
with hero("archive"):

    def stat(col: str, label: str) -> tuple[str, str, str, Tone]:
        now = float(a[col].iloc[-1])
        prev = a[col].iloc[-2] if len(a) > 1 else np.nan
        if col == "crush_margin":  # a margin can cross zero, so give the $ change
            ch = now - float(prev)
            note = "" if np.isnan(ch) else f"{signed(ch)} vs {this_year - 1}"
        else:
            ch = archive.year_change(a, col) or 0.0
            note = f"{ch:+.0%} vs {this_year - 1}".replace("-", "−")
        # A dearer weaned pig is good for a sow farm and bad for a finisher: no colour.
        return (f"{label}, {this_year}", fmt(col, now), note,
                "neutral" if col == "weaned_pig" else tone_of(ch))  # fmt: skip

    stat_strip(
        [
            stat("index", "Lean hogs"),
            stat("cutout", "Pork cutout"),
            stat("weaned_pig", "Weaned pigs"),
            stat("crush_margin", "Crush margin"),
        ]
    )
    st.space("small")
    chart_title("Year by year", "Averages of weekly figures · slaughter is per week")
    cols = list(archive.COLUMNS)
    table(
        ["Year", *[archive.COLUMNS[c][0] for c in cols]],
        [[str(int(r["year"])) + ("*" if r["weeks"] < 50 else ""), *[fmt(c, r[c]) for c in cols]]
         for r in a.to_dict("records")],
        emphasis_col=0,
    )  # fmt: skip
    source_note(
        "USDA AMS LM_HG201, LM_PK602, Feeder Pig Report; USDA NASS; crush margin from the Wean "
        "to finish inputs",
        "* partial year · crush margin = realized margin of pigs placed that year",
    )

st.space("medium")
left, right = st.columns([1.6, 1], gap="large")
with left:
    pick = st.selectbox(
        "Series",
        list(archive.COLUMNS),
        format_func=lambda c: f"{archive.COLUMNS[c][0]} ({archive.COLUMNS[c][1]})",
        key="mkt_archive_series",
        label_visibility="collapsed",
    )
    name, unit = archive.COLUMNS[pick]
    s = w.dropna(subset=[pick])
    iso = s["week_ending"].dt.isocalendar()
    chart_title(f"{name} by week, each year overlaid", f"{unit} · week of year")
    fig = go.Figure()
    years = sorted(iso["year"].unique())
    shades = BLUE_RAMP[: max(len(years) - 1, 1)]
    for i, y in enumerate(years):
        part = s[iso["year"] == y]
        wk = iso.loc[part.index, "week"]
        last = y == years[-1]
        color = ACCENT if last else (shades[min(i, len(shades) - 1)] if len(years) > 1 else HISTORY)
        fig.add_scatter(x=wk, y=part[pick], mode="lines", name=str(y),
                        line={"color": color, "width": 2.4 if last else 1.2},
                        hovertemplate=f"{y} week %{{x}}: %{{y:,.2f}}<extra></extra>")  # fmt: skip
        if len(part) and y >= years[-1] - 1:  # label this year and last; hover for the rest
            end_tag(fig, int(wk.iloc[-1]), float(part[pick].iloc[-1]), str(y), color)
    fig.update_xaxes(range=[1, 54])
    fig.update_layout(showlegend=False, margin={"l": 4, "r": 56, "t": 8, "b": 4})
    chart(fig, 330, on=PAGE)
    source_note("USDA via the app's loaders", "darkest green is the current year")
with right:
    chart_title("Download the record", f"{len(w)} weeks · one row per week ending Friday")
    year_pick = st.selectbox(
        "Year", ["All", *[str(int(y)) for y in a["year"]][::-1]], key="mkt_archive_year"
    )
    view = w if year_pick in (None, "All") else w[w["week_ending"].dt.year == int(year_pick)]
    named = view.rename(columns={c: f"{n} ({u})" for c, (n, u) in archive.COLUMNS.items()})
    st.download_button("CSV", named.to_csv(index=False), "hog_market_archive.csv", "text/csv",
                       icon=":material/download:", width="stretch", on_click="ignore")  # fmt: skip
    excel_button(
        {"Weekly": named,
         "By year": a.rename(columns={c: f"{n} ({u})" for c, (n, u) in archive.COLUMNS.items()})},
        "hog_market_archive", "Market archive, weekly and by year",
        "USDA AMS, NASS, ERS", label="Excel (weekly + by year)",
    )  # fmt: skip
    st.caption(
        "Crush margin is the realized margin of pigs placed that week at your Wean to finish "
        "inputs; corn is the monthly Iowa price, repeated for each week of the month."
    )

rule()
st.dataframe(
    view.sort_values("week_ending", ascending=False),
    hide_index=True,
    column_config={
        "week_ending": st.column_config.DateColumn("Week ending", format="MMM D, YYYY"),
        "index": st.column_config.NumberColumn("Lean Hog Index", format="dollar"),
        "cutout": st.column_config.NumberColumn("Cutout", format="dollar"),
        "spread_per_head": st.column_config.NumberColumn("Packer spread/hd", format="dollar"),
        "head": st.column_config.NumberColumn("Slaughter", format="%,.0f"),
        "weight_lb": st.column_config.NumberColumn("Carcass lb", format="%.1f"),
        "weaned_pig": st.column_config.NumberColumn("Weaned pig", format="dollar"),
        "crush_margin": st.column_config.NumberColumn("Crush margin", format="dollar"),
        "corn": st.column_config.NumberColumn("Iowa corn", format="dollar"),
    },
)
