"""Hog supply: what the quarterly USDA Hogs and Pigs report says is coming to market."""

import plotly.graph_objects as go
import streamlit as st

from hogproj import supply
from hogproj.ui import (
    ACCENT,
    HISTORY,
    INK,
    INK_2,
    PAGE,
    REFERENCE,
    Tone,
    chart,
    chart_title,
    chip,
    current_plan,
    end_tag,
    excel_button,
    hero,
    masthead,
    nass_data,
    quote,
    ref_line,
    rule,
    source_note,
    stat_strip,
)

df, source, note = nass_data()
ref = supply.latest_report(df)
out = supply.outlook(df)
six = supply.next_six_months(df)
breeding = supply.yoy(df, "breeding", ref)
all_hogs = supply.yoy(df, "all_hogs", ref)
low_year = supply.lowest_since(df, "breeding")
crop_row = out[out["basis"] == "Pigs born last quarter"].iloc[0]
intent = out[out["basis"] == "Sows expected to farrow"]
litter = supply.history(df, "pigs_per_litter")
litter_now, litter_prev = float(litter["value"].iloc[-1]), float(litter["value"].iloc[-5])


def pct(x: float | None) -> str:
    return "—" if x is None else f"{x:+.1%}".replace("-", "−")


def millions(x: float | None) -> str:
    return "—" if x is None else f"{x / 1e6:.2f}M"


status_chip = (
    chip(f"Live USDA NASS · {ref:%b} 1 report", "good", note)
    if source == "live"
    else chip(f"Saved NASS data · {ref:%b} 1 report", "caution", note)
)
direction = "below" if (six["pct"] or 0) < 0 else "above"
masthead(
    f"Hogs coming to market over the next six months are {abs(six['pct'] or 0):.1%} {direction} "
    "a year ago.",
    f"USDA's {ref:%B} 1 Hogs and Pigs report counts {millions(six['value'])} market hogs on farms. "
    f"The breeding herd of {millions(breeding['value'])} sows is the smallest {ref:%B} herd"
    + (f" since {low_year}." if low_year else " on record."),
    kicker=f"Hog supply · USDA Hogs and Pigs, {ref:%B} {ref.year}",
    meta=[status_chip],
)

st.space("small")
with hero():
    quote(
        "Market hogs on farms",
        millions(six["value"]),
        "head",
        f"{pct(six['pct'])} vs a year ago",
        "neutral",
        f"{ref:%B} 1, {ref.year} · these reach market over roughly the next six months",
    )
    # Neutral notes: fewer hogs is good for prices but bad for packers, so no green/red here.
    items: list[tuple[str, str, str, Tone]] = [
        ("Breeding herd", millions(breeding["value"]), f"{pct(breeding['pct'])} y/y", "neutral"),
        ("All hogs", millions(all_hogs["value"]), f"{pct(all_hogs['pct'])} y/y", "neutral"),
        (str(crop_row["label"]), millions(crop_row["value"]), f"{pct(crop_row['pct'])} y/y",
         "neutral"),
        ("Pigs per litter", f"{litter_now:.2f}", f"{litter_now - litter_prev:+.2f} y/y",
         "neutral"),
    ]  # fmt: skip
    if len(intent):
        first = intent.iloc[0]
        when = str(first["label"]).replace("Farrowings ", "")
        items.append((f"{when} farrowings", millions(first["value"]), f"{pct(first['pct'])} y/y",
                      "neutral"))  # fmt: skip
    stat_strip(items)
    st.space("small")

    fewer = int((out["pct"] < 0).sum())
    chart_title(
        "Fewer hogs are coming to market in every window through next summer"
        if fewer == len(out)
        else f"Supply runs below a year ago in {fewer} of {len(out)} windows ahead",
        "Change vs the same report a year ago · when each group of hogs should reach market",
    )
    labels = [
        f"{r['label']}<br><span style='font-size:10.5px;color:#7c847e'>"
        f"{r['start']:%b %Y}–{r['end']:%b %Y}</span>"
        for _, r in out.iterrows()
    ]
    vals = (out["pct"] * 100).to_numpy()
    bars = go.Figure(
        go.Bar(
            x=labels,
            y=vals,
            marker={"color": [ACCENT if v < 0 else "#9aa79f" for v in vals], "cornerradius": 3},
            text=[pct(v / 100) for v in vals],
            textposition="outside",
            textfont={"size": 12, "color": INK},
            cliponaxis=False,
            customdata=out["basis"],
            hovertemplate="%{customdata}: %{text} vs a year ago<extra></extra>",
        )
    )
    lim = max(abs(float(vals.min())), abs(float(vals.max())), 0.5) * 1.4
    bars.update_yaxes(range=[-lim, lim], ticksuffix="%", zeroline=True, zerolinecolor="#b9b2a3")
    bars.update_xaxes(tickfont={"size": 11.5, "color": INK_2}, showline=False, ticks="")
    bars.update_layout(hovermode="closest", bargap=0.45, showlegend=False)
    chart(bars, 330)
    source_note(
        "USDA NASS Quarterly Hogs and Pigs (Quick Stats)",
        "marketing windows are rules of thumb: heavier hogs within weeks, lighter ones months "
        "later, pigs about six months after birth",
    )

st.space("medium")
left, mid, right = st.columns([1.2, 0.06, 1])
with left:
    hist = supply.history(df, "breeding")
    chart_title(
        f"The breeding herd is the smallest since {low_year}"
        if low_year
        else "The breeding herd is at a record low",
        "Breeding hogs on farms, head, quarterly",
    )
    fig = go.Figure(
        go.Scatter(
            x=hist["period_start"],
            y=hist["value"],
            mode="lines",
            line={"color": HISTORY, "width": 2},
            hovertemplate="%{x|%b %Y}: %{y:,.0f}<extra></extra>",
        )
    )
    end_tag(fig, hist["period_start"].iloc[-1], float(hist["value"].iloc[-1]),
            millions(float(hist["value"].iloc[-1])), HISTORY)  # fmt: skip
    fig.update_yaxes(tickformat=".3s")
    fig.update_xaxes(tickformat="%Y")
    fig.update_layout(showlegend=False, margin={"l": 4, "r": 64, "t": 8, "b": 4})
    chart(fig, 290, on=PAGE)
    source_note("USDA NASS Quarterly Hogs and Pigs")
with mid:
    st.markdown(
        '<div class="hp-vrule" style="height:380px"></div>',
        unsafe_allow_html=True,
    )
with right:
    h = current_plan().herd
    yours = h.born_alive_per_litter * (1 - h.prewean_mortality)
    diff = yours - litter_now
    chart_title(
        f"Your herd weans {abs(diff):.2f} {'more' if diff >= 0 else 'fewer'} pigs per litter than "
        "the U.S. average",
        "Pigs saved per litter, U.S. quarterly · dotted: your Herd flow inputs",
    )
    lf = go.Figure(
        go.Scatter(
            x=litter["period_start"],
            y=litter["value"],
            mode="lines",
            line={"color": ACCENT, "width": 2},
            hovertemplate="%{x|%b %Y}: %{y:.2f} pigs<extra></extra>",
        )
    )
    end_tag(lf, litter["period_start"].iloc[-1], litter_now, f"{litter_now:.2f}", ACCENT)
    ref_line(lf, yours, f"Your herd {yours:.2f}", REFERENCE, side="left")
    lf.update_xaxes(tickformat="%Y")
    lf.update_layout(showlegend=False, margin={"l": 4, "r": 64, "t": 8, "b": 4})
    chart(lf, 290, on=PAGE)
    source_note("USDA NASS; your born alive × (1 − pre-wean mortality)")

rule()
excel_button({"Supply outlook": out, "Hogs and Pigs history": df}, "hog_supply",
             "USDA Hogs and Pigs supply outlook", "USDA NASS Quick Stats")  # fmt: skip
with st.expander("Supply outlook table"):
    table = out.assign(
        window=[f"{r['start']:%b %d, %Y} – {r['end']:%b %d, %Y}" for _, r in out.iterrows()]
    )[["label", "basis", "window", "value", "year_ago", "pct"]]
    st.dataframe(
        table,
        hide_index=True,
        column_config={
            "label": "Group",
            "basis": "What it counts",
            "window": "Reaches market",
            "value": st.column_config.NumberColumn("This report", format="%,.0f"),
            "year_ago": st.column_config.NumberColumn("A year ago", format="%,.0f"),
            "pct": st.column_config.NumberColumn("Change", format="percent"),
        },
    )
