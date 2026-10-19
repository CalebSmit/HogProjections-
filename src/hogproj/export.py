"""Excel report builder. Pure: takes results, returns the workbook as bytes (no disk I/O)."""

import io
from datetime import date, datetime

import pandas as pd
import xlsxwriter

from hogproj.finance import cost_table
from hogproj.herd import pigs_sold_per_sow_yr
from hogproj.outlook import Plan, headline, monthly, summary, synced

# Brand colours, matching src/hogproj/ui.py tokens.
NAVY, GREEN, RED, INK, GRID = "#1f4e8c", "#178a6a", "#c8453a", "#16181d", "#e3e3de"


def _dt(v: object) -> datetime:
    """Timestamp-like -> naive datetime for xlsxwriter."""
    return datetime.fromisoformat(str(v)[:10])


def build_report(
    plan: Plan, weekly: pd.DataFrame, as_of: date, hog_index_note: str, verdict: str
) -> bytes:
    """Workbook with Summary, Monthly, Costs and Weekly sheets for `plan`'s projection."""
    plan = synced(plan)
    hl = headline(plan)
    year = summary(weekly)
    months = monthly(weekly, months=24)
    costs = cost_table(plan.cost).reset_index()
    h, c = plan.herd, plan.cost

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    f = {
        "title": wb.add_format({"bold": True, "font_size": 18, "font_color": INK}),
        "sub": wb.add_format({"italic": True, "font_color": "#5b6b64"}),
        "h": wb.add_format(
            {"bold": True, "bg_color": NAVY, "font_color": "white", "border": 1,
             "border_color": GRID}
        ),
        "label": wb.add_format({"font_color": INK, "border": 1, "border_color": GRID}),
        "usd": wb.add_format({"num_format": "$#,##0.00;[Red]-$#,##0.00", "border": 1,
                              "border_color": GRID}),
        "usd0": wb.add_format({"num_format": "$#,##0;[Red]-$#,##0", "border": 1,
                               "border_color": GRID}),
        "num": wb.add_format({"num_format": "#,##0", "border": 1, "border_color": GRID}),
        "num1": wb.add_format({"num_format": "#,##0.0", "border": 1, "border_color": GRID}),
        "pct": wb.add_format({"num_format": "0%", "border": 1, "border_color": GRID}),
        "date": wb.add_format({"num_format": "mmm yyyy", "border": 1, "border_color": GRID}),
        "day": wb.add_format({"num_format": "yyyy-mm-dd", "border": 1, "border_color": GRID}),
        "text": wb.add_format({"border": 1, "border_color": GRID}),
        "verdict": wb.add_format(
            {"bold": True, "font_size": 12, "font_color": GREEN if hl["profit_usd_per_head"] >= 0
             else RED, "text_wrap": True}
        ),
    }  # fmt: skip

    # --- Summary --------------------------------------------------------------------------
    ws = wb.add_worksheet("Summary")
    ws.hide_gridlines(2)
    ws.set_column(0, 0, 38)
    ws.set_column(1, 1, 18)
    ws.write(0, 0, "Hog Projections — farm outlook", f["title"])
    ws.write(1, 0, f"Prepared {as_of:%B %d, %Y}. {hog_index_note}", f["sub"])
    ws.merge_range(3, 0, 4, 5, verdict, f["verdict"])
    rows = [
        ("Hog price used ($/cwt carcass)", c.lean_hog_usd_per_cwt_carcass, "usd"),
        ("Breakeven ($/cwt carcass)", hl["breakeven_cwt_carcass"], "usd"),
        ("Breakeven ($/cwt live)", hl["breakeven_cwt_live"], "usd"),
        ("Cost per pig (before manure credit)", hl["cost_usd_per_head"], "usd"),
        ("Profit per pig at today's price", hl["profit_usd_per_head"], "usd"),
        ("Pigs sold, next 12 months", year["pigs_sold"], "num"),
        ("Revenue, next 12 months", year["revenue_usd"], "usd0"),
        ("Costs, next 12 months", year["cost_usd"], "usd0"),
        ("Profit, next 12 months", year["profit_usd"], "usd0"),
    ]
    ws.write_row(6, 0, ["Headline", "Value"], f["h"])
    for i, (label, value, fmt) in enumerate(rows, start=7):
        ws.write(i, 0, label, f["label"])
        ws.write(i, 1, value, f[fmt])

    assumptions = [
        ("Sows today", h.sows_start, "num"),
        ("Sows after change", h.sows_target, "num"),
        ("Change starts at week", h.change_week, "num"),
        ("Litters / sow / year", h.litters_per_sow_yr, "num1"),
        ("Born alive / litter", h.born_alive_per_litter, "num1"),
        ("Pre-wean mortality", h.prewean_mortality, "pct"),
        ("Wean-to-market mortality", h.wean_to_market_mortality, "pct"),
        ("Pigs sold / sow / year", pigs_sold_per_sow_yr(h), "num1"),
        ("Market weight (lb live)", h.weight_lb_live_market, "num"),
        ("Carcass yield", h.carcass_yield, "pct"),
        ("Corn ($/bu)", c.corn_usd_per_bu, "usd"),
        ("Soybean meal ($/ton)", c.sbm_usd_per_ton, "usd"),
        ("Price path", "Seasonal" if plan.seasonal else "Flat", "text"),
    ]
    start = 7 + len(rows) + 2
    ws.write_row(start, 0, ["Assumption", "Value"], f["h"])
    for i, (label, value, fmt) in enumerate(assumptions, start=start + 1):
        ws.write(i, 0, label, f["label"])
        ws.write(i, 1, value, f[fmt])

    # --- Monthly --------------------------------------------------------------------------
    wm = wb.add_worksheet("Monthly")
    heads = ["Month", "Pigs sold", "Hog price ($/cwt carcass)", "Revenue", "Costs", "Profit",
             "Profit per pig", "Note"]  # fmt: skip
    wm.write_row(0, 0, heads, f["h"])
    wm.set_column(0, 0, 12)
    wm.set_column(1, 7, 18)
    for i, m in enumerate(months.to_dict("records"), start=1):
        wm.write_datetime(i, 0, _dt(m["month"]), f["date"])
        wm.write(i, 1, m["pigs_sold"], f["num"])
        wm.write(i, 2, m["hog_usd_per_cwt_carcass"], f["usd"])
        wm.write(i, 3, m["revenue_usd"], f["usd0"])
        wm.write(i, 4, m["cost_usd"], f["usd0"])
        wm.write(i, 5, m["profit_usd"], f["usd0"])
        wm.write(i, 6, m["profit_usd_per_head"], f["usd"])
        wm.write(i, 7, "partial month" if m["partial"] else "", f["text"])
    n = len(months)
    chart = wb.add_chart({"type": "column"})
    assert chart is not None
    chart.add_series(
        {
            "name": "Profit",
            "categories": ["Monthly", 1, 0, n, 0],
            "values": ["Monthly", 1, 5, n, 5],
            "fill": {"color": GREEN},
            "invert_if_negative": True,
            "invert_if_negative_color": RED,
        }
    )
    chart.set_title({"name": "Profit by month"})
    chart.set_legend({"none": True})
    chart.set_x_axis({"num_format": "mmm yy"})
    chart.set_y_axis({"num_format": "$#,##0", "major_gridlines": {"visible": True,
                      "line": {"color": GRID}}})  # fmt: skip
    ws.insert_chart(6, 3, chart, {"x_scale": 1.4, "y_scale": 1.3})

    # --- Costs ----------------------------------------------------------------------------
    wc = wb.add_worksheet("Costs")
    wc.write_row(0, 0, ["Cost line", "$ / pig", "$ / cwt carcass", "Share of cost"], f["h"])
    wc.set_column(0, 0, 30)
    wc.set_column(1, 3, 16)
    for i, row in enumerate(costs.to_dict("records"), start=1):
        wc.write(i, 0, row["cost line"], f["label"])
        wc.write(i, 1, row["usd_per_head"], f["usd"])
        wc.write(i, 2, row["usd_per_cwt_carcass"], f["usd"])
        wc.write(i, 3, row["share"], f["pct"])
    wc.write(
        len(costs) + 2,
        0,
        "Structure follows Iowa State University Estimated Livestock Returns (farrow to finish).",
        f["sub"],
    )

    # --- Weekly ---------------------------------------------------------------------------
    ww = wb.add_worksheet("Weekly")
    cols = [
        ("Week", "week", "num"),
        ("Date", "date", "day"),
        ("Pigs sold", "marketed_head", "num"),
        ("Carcass lb sold", "sold_lb_carcass", "num"),
        ("Hog price ($/cwt carcass)", "hog_usd_per_cwt_carcass", "usd"),
        ("Revenue", "revenue_usd", "usd0"),
        ("Costs", "cost_usd", "usd0"),
        ("Profit", "margin_usd", "usd0"),
        ("Running total", "cumulative_margin_usd", "usd0"),
    ]
    ww.write_row(0, 0, [c_[0] for c_ in cols], f["h"])
    ww.set_column(0, len(cols) - 1, 16)
    ww.freeze_panes(1, 0)
    for i, rec in enumerate(weekly.to_dict("records"), start=1):
        for j, (_, key, fmt) in enumerate(cols):
            v = rec[key]
            if key == "date":
                ww.write_datetime(i, j, _dt(v), f[fmt])
            else:
                ww.write(i, j, float(v), f[fmt])

    wb.close()
    return buf.getvalue()
