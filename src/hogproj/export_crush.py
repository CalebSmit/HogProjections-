"""The wean pig crush as a live Excel workbook, laid out like the workbook Pipestone staff use:
one column per placement week, inputs in their own sheet, every margin a formula.

Sheets: Read me · Inputs (named cells) · Contracts (futures, hedges → effective price) ·
Crush (placements on feed + a pig placed today) · History (placements already sold) ·
USDA data. Each formula is written with the value the app computed, so the file opens with the
right numbers before Excel recalculates; change any input or contract price and it updates.
Pure: returns bytes.
"""

import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd
import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell

from hogproj.config import get_settings
from hogproj.crush import CrushInputs

GREEN, RED, INK, GRID, INPUT = "#178a6a", "#c8453a", "#16181d", "#e3e3de", "#fff7d6"


@dataclass
class ContractRow:
    label: str
    expiry: date
    futures: float  # $/cwt lean, today's price (entered or estimate)
    hedged: float = 0.0  # 0-1
    hedge_price: float = 0.0

    @property
    def effective(self) -> float:
        return self.hedged * self.hedge_price + (1 - self.hedged) * self.futures


@dataclass
class Placement:
    week_ending: date
    placed: date
    sold: date
    contract: str  # label, must match a ContractRow
    usda_pig: float
    corn: float  # $/bu delivered for its months on feed
    head: float


INPUTS = [  # (name, label, CrushInputs field or None, unit, format)
    ("Adder", "Adder over USDA weaned pig", "adder_usd_per_head", "$/head", "usd"),
    ("DaysOnFeed", "Days on feed", "days_on_feed", "days", "num"),
    ("WeightLive", "Market weight", "weight_lb_live", "lb live", "num"),
    ("Yield", "Carcass yield", "carcass_yield", "", "pct"),
    ("Basis", "Your basis to the index", "basis_usd_per_cwt", "$/cwt", "usd"),
    ("CornLb", "Corn fed", "corn_lb", "lb/pig", "num"),
    ("SbmLb", "Soybean meal fed", "sbm_lb", "lb/pig", "num"),
    ("DdgsLb", "DDGS fed", "ddgs_lb", "lb/pig", "num"),
    ("OtherLb", "Other feed", "other_feed_lb", "lb/pig", "num"),
    ("OtherPrice", "Other feed price", "other_feed_usd_per_lb", "$/lb", "usd"),
    ("SbmPrice", "Soybean meal price", "sbm_usd_per_ton", "$/ton", "usd"),
    ("DdgsPrice", "DDGS price", "ddgs_usd_per_ton", "$/ton", "usd"),
    ("Health", "Animal health", "health_usd", "$/pig", "usd"),
    ("Barn", "Barn and labor", "facilities_labor_usd", "$/pig", "usd"),
    ("Mortality", "Mortality", "mortality_usd", "$/pig", "usd"),
    ("Overhead", "Overhead (G&A)", "overhead_usd", "$/pig", "usd"),
    ("Freight", "Freight out", "freight_usd", "$/pig", "usd"),
    ("OpInterest", "Operating interest", "interest_usd", "$/pig", "usd"),
    ("OtherCost", "Other / sales premiums", "other_usd", "$/pig", "usd"),
    ("Principal", "Principal payment", "principal_usd", "$/pig", "usd"),
    ("TermInterest", "Term interest", "term_interest_usd", "$/pig", "usd"),
    ("CornHedgePct", "Corn hedged", None, "", "pct"),
    ("CornHedgePrice", "Corn hedge price, delivered", None, "$/bu", "usd"),
]


def _dt(v: object) -> datetime:
    return datetime.fromisoformat(str(v)[:10])


def _serial(v: object) -> int:
    """Excel's date number, for the cached value of a date formula."""
    return (_dt(v) - datetime(1899, 12, 30)).days


def margins(
    c: CrushInputs, p: Placement, contracts: dict[str, ContractRow], corn_hedge: tuple[float, float]
) -> dict[str, float]:
    """The same arithmetic the formulas do, for their cached values and for tests."""
    share, price = corn_hedge
    corn = share * price + (1 - share) * p.corn
    feed = (
        c.corn_lb * corn / 56
        + c.sbm_lb * c.sbm_usd_per_ton / 2000
        + c.ddgs_lb * c.ddgs_usd_per_ton / 2000
        + c.other_feed_lb * c.other_feed_usd_per_lb
    )
    hog = contracts[p.contract].effective
    rev_cwt = hog + c.basis_usd_per_cwt
    revenue = rev_cwt * c.weight_lb_live * c.carcass_yield / 100
    nonfeed = (
        c.health_usd
        + c.facilities_labor_usd
        + c.mortality_usd
        + c.overhead_usd
        + c.freight_usd
        + c.interest_usd
        + c.other_usd
    )
    pig = p.usda_pig + c.adder_usd_per_head
    total = pig + feed + nonfeed
    debt = c.principal_usd + c.term_interest_usd
    return {
        "pig": pig,
        "corn": corn,
        "feed": feed,
        "hog": hog,
        "rev_cwt": rev_cwt,
        "revenue": revenue,
        "nonfeed": nonfeed,
        "total": total,
        "margin": revenue - total,
        "debt": debt,
        "after_debt": revenue - total - debt,
    }


def build_crush_workbook(
    c: CrushInputs,
    placements: Sequence[Placement],
    contracts: Sequence[ContractRow],
    corn_hedge: tuple[float, float],
    history: pd.DataFrame,
    usda: pd.DataFrame,
    as_of: date,
    notes: str = "",
) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    base = {"border": 1, "border_color": GRID}
    f = {
        "title": wb.add_format({"bold": True, "font_size": 16, "font_color": INK}),
        "sub": wb.add_format({"italic": True, "font_color": "#5b6b64", "text_wrap": True}),
        "h": wb.add_format({**base, "bold": True, "bg_color": GREEN, "font_color": "white"}),
        "label": wb.add_format({**base}),
        "bold": wb.add_format({**base, "bold": True}),
        "usd": wb.add_format({**base, "num_format": "$#,##0.00;[Red]-$#,##0.00"}),
        "usd0": wb.add_format({**base, "num_format": "$#,##0;[Red]-$#,##0"}),
        "num": wb.add_format({**base, "num_format": "#,##0.##"}),
        "pct": wb.add_format({**base, "num_format": "0%"}),
        "date": wb.add_format({**base, "num_format": "mmm d, yyyy"}),
        "text": wb.add_format({**base}),
        "in_usd": wb.add_format({**base, "num_format": "$#,##0.00", "bg_color": INPUT}),
        "in_num": wb.add_format({**base, "num_format": "#,##0.##", "bg_color": INPUT}),
        "in_pct": wb.add_format({**base, "num_format": "0%", "bg_color": INPUT}),
        "key_usd": wb.add_format(
            {**base, "bold": True, "num_format": "$#,##0.00;[Red]-$#,##0.00", "top": 2}
        ),
    }
    who = get_settings().prepared_by.strip()

    # --- Read me ---------------------------------------------------------------------------
    rm = wb.add_worksheet("Read me")
    rm.hide_gridlines(2)
    rm.set_column(0, 0, 110)
    lines = [
        ("Hog Projections — wean pig crush", "title"),
        (
            f"Prepared{' by ' + who if who else ''} {as_of:%B %d, %Y} from public USDA data. "
            "Projections, not financial advice.",
            "sub",
        ),
        ("", "sub"),
        ("How to use it", "bold"),
        (
            "Yellow cells are inputs. Change them on Inputs (costs, ration, corn hedge) or "
            "Contracts (lean hog futures, hedged share and price) and every margin on Crush "
            "recalculates.",
            "sub",
        ),
        (
            "Crush has one column per USDA weekly placement still on feed, newest first, plus a "
            "pig placed today. Each sells into the lean hog contract for its marketing date.",
            "sub",
        ),
        (
            "Hog price = hedged share × hedge price + the rest at the contract's futures price; "
            "revenue adds your basis to the index. Corn per column is delivered corn for its "
            "months on feed (CBOT curve plus your Iowa basis, or today's cash).",
            "sub",
        ),
        (
            "History lists placements already sold, priced at the actual Lean Hog Index and the "
            "Iowa feed prices of the time. USDA data has the weekly prices behind it.",
            "sub",
        ),
        (notes, "sub"),
    ]
    for i, (text, fmt) in enumerate(lines):
        rm.write(i, 0, text, f[fmt])

    # --- Inputs ----------------------------------------------------------------------------
    wi = wb.add_worksheet("Inputs")
    wi.set_column(0, 0, 32)
    wi.set_column(1, 1, 14)
    wi.set_column(2, 2, 10)
    wi.write_row(0, 0, ["Input", "Value", "Unit"], f["h"])
    values = {"CornHedgePct": corn_hedge[0], "CornHedgePrice": corn_hedge[1]}
    for i, (name, label, field, unit, fmt) in enumerate(INPUTS, start=1):
        v = values[name] if field is None else getattr(c, field)
        wi.write(i, 0, label, f["label"])
        wi.write(i, 1, v, f[f"in_{fmt}"] if fmt in ("usd", "num", "pct") else f["in_num"])
        wi.write(i, 2, unit, f["text"])
        wb.define_name(name, f"=Inputs!$B${i + 1}")

    # --- Contracts -------------------------------------------------------------------------
    wk = wb.add_worksheet("Contracts")
    wk.set_column(0, 0, 14)
    wk.set_column(1, 5, 16)
    wk.write_row(
        0,
        0,
        ["Contract", "Expires", "Futures $/cwt", "Hedged", "Hedge price", "Effective $/cwt"],
        f["h"],
    )
    for i, k in enumerate(contracts, start=1):
        r = i + 1
        wk.write(i, 0, k.label, f["bold"])
        wk.write_datetime(i, 1, _dt(k.expiry), f["date"])
        wk.write(i, 2, k.futures, f["in_usd"])
        wk.write(i, 3, k.hedged, f["in_pct"])
        wk.write(i, 4, k.hedge_price, f["in_usd"])
        wk.write_formula(i, 5, f"=D{r}*E{r}+(1-D{r})*C{r}", f["usd"], k.effective)
    n_k = len(contracts)
    wb.define_name("ContractTable", f"=Contracts!$A$2:$F${n_k + 1}")
    wk.write(
        n_k + 2,
        0,
        "Futures are what you entered in the app, or the app's seasonal "
        "estimate where you entered none. Replace them with today's CME settlements.",
        wb.add_format({"italic": True, "font_color": "#5b6b64"}),
    )

    # --- Crush -----------------------------------------------------------------------------
    ws = wb.add_worksheet("Crush")
    ws.freeze_panes(1, 1)
    ws.set_column(0, 0, 30)
    ws.set_column(1, len(placements) + 1, 13)
    kmap = {k.label: k for k in contracts}
    labels = [
        ("USDA report week ending", "date"),
        ("Placed", "date"),
        ("Avg marketing date", "date"),
        ("Sells into", "text"),
        ("USDA weaned pig ($/head)", "in_usd"),
        ("Pig cost", "usd"),
        ("Corn, delivered ($/bu)", "in_usd"),
        ("Corn after hedge", "usd"),
        ("Feed cost / pig", "usd"),
        ("Hog price ($/cwt, after hedges)", "usd"),
        ("Revenue / cwt (+ basis)", "usd"),
        ("Revenue / pig", "usd"),
        ("Non-feed / pig", "usd"),
        ("Cost of production / pig", "usd"),
        ("Margin / pig", "key_usd"),
        ("Debt payments / pig", "usd"),
        ("Margin / pig after debt", "key_usd"),
        ("Head", "in_num"),
        ("Total margin after debt", "usd0"),
    ]
    for r, (label, _) in enumerate(labels, start=1):
        ws.write(r, 0, label, f["bold"] if label.startswith("Margin") else f["label"])
    ws.write(0, 0, "Placement", f["h"])
    for j, p in enumerate(placements, start=1):
        m = margins(c, p, kmap, corn_hedge)

        def cell(row: int, col: int = j) -> str:
            return xl_rowcol_to_cell(row, col)

        ws.write(0, j, "Today" if p.week_ending >= as_of else f"{p.placed:%b %d}", f["h"])
        ws.write_datetime(1, j, _dt(p.week_ending), f["date"])
        ws.write_formula(2, j, f"={cell(1)}-4", f["date"], _serial(p.placed))
        ws.write_formula(3, j, f"={cell(2)}+DaysOnFeed", f["date"], _serial(p.sold))
        ws.write(4, j, p.contract, f["text"])
        ws.write(5, j, p.usda_pig, f["in_usd"])
        ws.write_formula(6, j, f"={cell(5)}+Adder", f["usd"], m["pig"])
        ws.write(7, j, p.corn, f["in_usd"])
        ws.write_formula(
            8, j, f"=CornHedgePct*CornHedgePrice+(1-CornHedgePct)*{cell(7)}", f["usd"], m["corn"]
        )
        ws.write_formula(
            9,
            j,
            f"=CornLb*{cell(8)}/56+SbmLb*SbmPrice/2000+DdgsLb*DdgsPrice/2000+OtherLb*OtherPrice",
            f["usd"],
            m["feed"],
        )
        ws.write_formula(10, j, f"=VLOOKUP({cell(4)},ContractTable,6,FALSE)", f["usd"], m["hog"])
        ws.write_formula(11, j, f"={cell(10)}+Basis", f["usd"], m["rev_cwt"])
        ws.write_formula(12, j, f"={cell(11)}*WeightLive*Yield/100", f["usd"], m["revenue"])
        ws.write_formula(
            13,
            j,
            "=Health+Barn+Mortality+Overhead+Freight+OpInterest+OtherCost",
            f["usd"],
            m["nonfeed"],
        )
        ws.write_formula(14, j, f"={cell(6)}+{cell(9)}+{cell(13)}", f["usd"], m["total"])
        ws.write_formula(15, j, f"={cell(12)}-{cell(14)}", f["key_usd"], m["margin"])
        ws.write_formula(16, j, "=Principal+TermInterest", f["usd"], m["debt"])
        ws.write_formula(17, j, f"={cell(15)}-{cell(16)}", f["key_usd"], m["after_debt"])
        ws.write(18, j, p.head, f["in_num"])
        ws.write_formula(19, j, f"={cell(17)}*{cell(18)}", f["usd0"], m["after_debt"] * p.head)
    # Totals column.
    t = len(placements) + 1
    first, last = xl_rowcol_to_cell(18, 1), xl_rowcol_to_cell(18, t - 1)
    tf, tl = xl_rowcol_to_cell(19, 1), xl_rowcol_to_cell(19, t - 1)
    total_head = sum(p.head for p in placements)
    total_margin = sum(margins(c, p, kmap, corn_hedge)["after_debt"] * p.head for p in placements)
    ws.write(0, t, "All columns", f["h"])
    ws.write_formula(18, t, f"=SUM({first}:{last})", f["num"], total_head)
    ws.write_formula(19, t, f"=SUM({tf}:{tl})", f["usd0"], total_margin)
    ws.write_formula(
        17,
        t,
        f"=IF({xl_rowcol_to_cell(18, t)}=0,0,{xl_rowcol_to_cell(19, t)}/"
        f"{xl_rowcol_to_cell(18, t)})",
        f["key_usd"],
        total_margin / total_head if total_head else 0,
    )
    ws.conditional_format(
        15,
        1,
        17,
        t,
        {"type": "cell", "criteria": "<", "value": 0, "format": wb.add_format({"font_color": RED})},
    )
    chart = wb.add_chart({"type": "column"})
    assert chart is not None
    chart.add_series(
        {
            "name": "Margin / pig after debt",
            "categories": ["Crush", 0, 1, 0, t - 1],
            "values": ["Crush", 17, 1, 17, t - 1],
            "fill": {"color": GREEN},
            "invert_if_negative": True,
            "invert_if_negative_color": RED,
        }
    )
    chart.set_title({"name": "Projected margin by placement"})
    chart.set_legend({"none": True})
    chart.set_y_axis(
        {"num_format": "$#,##0", "major_gridlines": {"visible": True, "line": {"color": GRID}}}
    )
    ws.insert_chart(22, 1, chart, {"x_scale": 2.0, "y_scale": 1.2})

    # --- History ---------------------------------------------------------------------------
    wh = wb.add_worksheet("History")
    cols = [
        ("placed", "Placed", "date"),
        ("sold", "Sold", "date"),
        ("pig_usd", "Paid", "usd"),
        ("worth_usd", "Worth", "usd"),
        ("hog_usd_per_cwt", "Index at sale $/cwt", "usd"),
        ("corn_usd_per_bu", "Corn $/bu", "usd"),
        ("cost_usd", "Cost / pig", "usd"),
        ("margin_usd", "Margin / pig", "usd"),
    ]
    wh.freeze_panes(1, 0)
    wh.set_column(0, len(cols), 14)
    wh.write_row(0, 0, [h for _, h, _ in cols], f["h"])
    hist = history.sort_values("placed").to_dict("records")
    for i, r in enumerate(hist, start=1):
        for j, (key, _, fmt) in enumerate(cols):
            v = r.get(key)
            if fmt == "date":
                wh.write_datetime(i, j, _dt(v), f["date"])
            else:
                wh.write(i, j, float(v), f[fmt])
    if hist:
        hc = wb.add_chart({"type": "line"})
        assert hc is not None
        n = len(hist)
        for col, name, color in ((3, "Worth", GREEN), (2, "Paid", "#3a423d")):
            hc.add_series(
                {
                    "name": name,
                    "categories": ["History", 1, 0, n, 0],
                    "values": ["History", 1, col, n, col],
                    "line": {"color": color, "width": 1.75},
                }
            )
        hc.set_title({"name": "What weaned pigs cost vs what they were worth"})
        hc.set_x_axis({"num_format": "mmm yy", "date_axis": True})
        hc.set_y_axis({"num_format": "$#,##0"})
        wh.insert_chart(1, len(cols) + 1, hc, {"x_scale": 1.8, "y_scale": 1.3})

    # --- USDA data -------------------------------------------------------------------------
    wu = wb.add_worksheet("USDA data")
    wu.freeze_panes(1, 0)
    wu.set_column(0, len(usda.columns), 16)
    wu.write_row(0, 0, [str(x) for x in usda.columns], f["h"])
    for i, row in enumerate(usda.itertuples(index=False), start=1):
        for j, v in enumerate(row):
            if isinstance(v, pd.Timestamp | datetime | date):
                wu.write_datetime(i, j, _dt(v), f["date"])
            elif isinstance(v, float) and pd.isna(v):
                wu.write_blank(i, j, None)
            else:
                wu.write(i, j, v)

    wb.close()
    return buf.getvalue()
