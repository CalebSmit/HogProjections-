"""Build a live-formula Excel workbook of the projection. Every yellow cell is an input.

The workbook recalculates on its own in Excel. It holds formulas, not pasted numbers, and
`tests/test_excel.py` checks that it agrees with `model.project`.
"""

import io
from collections.abc import Sequence

import pandas as pd
import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell

from hogproj.basis import PERIODS, period_label
from hogproj.inputs import BarnCostMode, LaborCostMode, Location, Projection, WeanPigPriceSource

MAX_LOCATIONS = 40
MAX_PHASES = 12
MAX_CUTS = 8
MAX_CONTRACTS = 24


def build_workbook(
    p: Projection,
    locations: Sequence[Location],
    basis_history: pd.DataFrame | None = None,
    wean_pig_history: pd.DataFrame | None = None,
) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    f = _formats(wb)

    dash = wb.add_worksheet("Dashboard")
    inp = wb.add_worksheet("Inputs")
    loc = wb.add_worksheet("Locations")
    feed = wb.add_worksheet("Feed")
    mkt = wb.add_worksheet("Marketing")
    prices = wb.add_worksheet("Market Data")
    costs = wb.add_worksheet("Costs")

    _inputs_sheet(wb, inp, p, f)
    _locations_sheet(wb, loc, locations, f)
    _feed_sheet(wb, feed, p, f)
    _market_data_sheet(wb, prices, p, basis_history, wean_pig_history, f)
    _marketing_sheet(wb, mkt, p, f)
    _costs_sheet(wb, costs, f)
    _dashboard_sheet(wb, dash, f)

    dash.activate()
    wb.close()
    return buf.getvalue()


# --------------------------------------------------------------------------------------
# formats


def _formats(wb: xlsxwriter.Workbook) -> dict:
    base = {"font_name": "Calibri", "font_size": 11}
    inp = {**base, "bg_color": "#FFF2CC", "border": 1, "border_color": "#BFBFBF"}
    return {
        "title": wb.add_format({**base, "bold": True, "font_size": 16, "font_color": "#1F3864"}),
        "h": wb.add_format({**base, "bold": True, "bg_color": "#1F3864", "font_color": "white"}),
        "sub": wb.add_format({**base, "bold": True, "font_color": "#1F3864", "bottom": 1}),
        "label": wb.add_format(base),
        "note": wb.add_format({**base, "italic": True, "font_color": "#7F7F7F"}),
        "in_num": wb.add_format({**inp, "num_format": "#,##0.00"}),
        "in_int": wb.add_format({**inp, "num_format": "#,##0"}),
        "in_pct": wb.add_format({**inp, "num_format": "0.00"}),
        "in_date": wb.add_format({**inp, "num_format": "yyyy-mm-dd"}),
        "in_txt": wb.add_format(inp),
        "num": wb.add_format({**base, "num_format": "#,##0.00"}),
        "int": wb.add_format({**base, "num_format": "#,##0"}),
        "usd": wb.add_format({**base, "num_format": "$#,##0"}),
        "usd2": wb.add_format({**base, "num_format": "$#,##0.00"}),
        "pct": wb.add_format({**base, "num_format": "0.0%"}),
        "date": wb.add_format({**base, "num_format": "yyyy-mm-dd"}),
        "txt": wb.add_format(base),
        "kpi": wb.add_format(
            {**base, "bold": True, "font_size": 14, "num_format": "$#,##0.00", "border": 1}
        ),
        "kpi_label": wb.add_format({**base, "bold": True, "bg_color": "#D9E1F2", "border": 1}),
        "total": wb.add_format({**base, "bold": True, "num_format": "$#,##0", "top": 1}),
        "total2": wb.add_format({**base, "bold": True, "num_format": "$#,##0.00", "top": 1}),
    }


# --------------------------------------------------------------------------------------
# Inputs sheet: one named cell per scalar input


def _inputs_sheet(wb, ws, p: Projection, f) -> dict[str, str]:
    ws.set_column("A:A", 3)
    ws.set_column("B:B", 44)
    ws.set_column("C:C", 22)
    ws.set_column("D:D", 18)
    ws.set_column("E:E", 70)
    ws.write("B1", "Inputs — yellow cells are editable", f["title"])
    ws.write("B2", "Change any yellow cell; every other sheet recalculates.", f["note"])

    rows: list[tuple] = [
        ("Group", None),
        ("HeadPlaced", "Head placed", p.head_placed, "in_int", "head", ""),
        ("PlacementDate", "Placement date", p.placement_date, "in_date", "date", ""),
        ("WeanWeight", "Weaned pig weight", p.wean_weight_lb, "in_num", "lb", ""),
        ("MortalityPct", "Mortality (wean to market)", p.mortality_pct, "in_pct", "%", ""),
        (
            "DeadFeedShare",
            "Feed eaten by a dead pig (share of full budget)",
            p.dead_feed_share,
            "in_num",
            "0-1",
            "Most death loss is early, so deads eat little",
        ),
        ("YieldPct", "Carcass yield", p.carcass_yield_pct, "in_pct", "%", "Hot carcass / live"),
        (
            "Location",
            "Feeding location",
            p.location.name,
            "in_txt",
            "",
            "Pick from list; prices come from the Locations sheet",
        ),
        ("Weaned pig", None),
        (
            "WeanSource",
            "Weaned pig price source",
            p.wean_pig_source.value,
            "in_txt",
            "",
            "USDA cash = open market, lots of 2,400+ head",
        ),
        (
            "WeanCash",
            "USDA weaned pig cash price",
            p.wean_pig_usda_cash_usd_hd,
            "in_num",
            "$/head",
            "USDA AMS National Direct Delivered Feeder Pig Report (NW_LS255)",
        ),
        (
            "WeanFormula",
            "USDA weaned pig formula price",
            p.wean_pig_usda_formula_usd_hd,
            "in_num",
            "$/head",
            "Same report, formula purchases",
        ),
        ("WeanManual", "Manual weaned pig price", p.wean_pig_manual_usd_hd, "in_num", "$/head", ""),
        ("WeanFreight", "Weaned pig freight", p.wean_pig_freight_usd_hd, "in_num", "$/head", ""),
        ("Feed prices", None),
        ("CornFutures", "CBOT corn futures", p.corn_futures_usd_bu, "in_num", "$/bu", ""),
        ("SbmFutures", "CBOT soybean meal futures", p.sbm_futures_usd_ton, "in_num", "$/ton", ""),
        ("FeedMill", "Feed mill grind/mix/delivery", p.feed_mill_usd_ton, "in_num", "$/ton", ""),
        ("Barn, labor and other", None),
        ("BarnMode", "Barn cost method", p.barn_mode.value, "in_txt", "", ""),
        (
            "BarnDays",
            "Barn days occupied (feeding + downtime)",
            p.barn_days_occupied,
            "in_int",
            "days",
            "Used with $/space/year",
        ),
        ("BarnPerPig", "Barn cost if $/pig placed", p.barn_usd_pig_placed, "in_num", "$/pig", ""),
        ("LaborMode", "Labor cost method", p.labor_mode.value, "in_txt", "", ""),
        (
            "LaborHours",
            "Labor hours per pig placed",
            p.labor_hr_per_pig,
            "in_num",
            "hr/pig",
            "Wage comes from the Locations sheet",
        ),
        (
            "LaborPerPig",
            "Labor cost if $/pig placed",
            p.labor_usd_pig_placed,
            "in_num",
            "$/pig",
            "",
        ),
        ("VetMed", "Vet / med / vaccine", p.vet_med_usd_hd, "in_num", "$/head placed", ""),
        ("Utilities", "Utilities / fuel", p.utilities_usd_hd, "in_num", "$/head placed", ""),
        ("Trucking", "Trucking to market", p.trucking_usd_hd_sold, "in_num", "$/head sold", ""),
        ("InsMisc", "Insurance / misc", p.insurance_misc_usd_hd, "in_num", "$/head placed", ""),
        (
            "InterestPct",
            "Operating interest rate",
            p.interest_rate_pct,
            "in_pct",
            "%/yr",
            "On pig cost + half of feed, for the feeding period",
        ),
        ("Revenue", None),
        ("Premium", "Carcass merit premium", p.carcass_premium_cwt, "in_num", "$/cwt carcass", ""),
        ("CheckoffPct", "Pork checkoff", p.checkoff_pct, "in_pct", "% of gross", ""),
    ]
    names: dict[str, str] = {}
    r = 3
    for row in rows:
        if row[1] is None:
            r += 1
            ws.write(r, 1, row[0], f["sub"])
            r += 1
            continue
        name, label, value, fmt, unit, note = row
        ws.write(r, 1, label, f["label"])
        if fmt == "in_date":
            ws.write_datetime(r, 2, pd.Timestamp(value).to_pydatetime(), f[fmt])
        else:
            ws.write(r, 2, value, f[fmt])
        ws.write(r, 3, unit, f["note"])
        ws.write(r, 4, note, f["note"])
        ref = f"=Inputs!$C${r + 1}"
        wb.define_name(name, ref)
        names[name] = ref
        r += 1

    def validate(name: str, options: list[str]) -> None:
        row_idx = int(names[name].split("$")[-1]) - 1
        ws.data_validation(row_idx, 2, row_idx, 2, {"validate": "list", "source": options})

    validate("WeanSource", [s.value for s in WeanPigPriceSource])
    validate("BarnMode", [m.value for m in BarnCostMode])
    validate("LaborMode", [m.value for m in LaborCostMode])
    loc_row = int(names["Location"].split("$")[-1]) - 1
    ws.data_validation(
        loc_row,
        2,
        loc_row,
        2,
        {"validate": "list", "source": f"=Locations!$A$2:$A${MAX_LOCATIONS + 1}"},
    )

    # Derived values shown on the inputs page for transparency
    r += 1
    ws.write(r, 1, "From selected location (edit on Locations sheet)", f["sub"])
    r += 1
    derived = [
        ("LocRow", "Location row", "=MATCH(Location,Locations!$A$2:$A$41,0)", "int"),
        ("CornBasis", "Corn basis", "=INDEX(Locations!$C$2:$C$41,LocRow)", "num"),
        ("SbmBasis", "Soybean meal basis", "=INDEX(Locations!$D$2:$D$41,LocRow)", "num"),
        ("DdgsPrice", "DDGS price", "=INDEX(Locations!$E$2:$E$41,LocRow)", "num"),
        ("BarnRent", "Barn rent $/space/year", "=INDEX(Locations!$F$2:$F$41,LocRow)", "num"),
        ("LaborWage", "Labor wage $/hr", "=INDEX(Locations!$G$2:$G$41,LocRow)", "num"),
        ("CornCash", "Corn cash price (futures + basis)", "=CornFutures+CornBasis", "num"),
        ("SbmCash", "Soybean meal cash price (futures + basis)", "=SbmFutures+SbmBasis", "num"),
        (
            "WeanPrice",
            "Weaned pig price used",
            f'=IF(WeanSource="{WeanPigPriceSource.USDA_CASH.value}",WeanCash,'
            f'IF(WeanSource="{WeanPigPriceSource.USDA_FORMULA.value}",WeanFormula,WeanManual))',
            "num",
        ),
        ("HeadSold", "Head sold", "=HeadPlaced*(1-MortalityPct/100)", "num"),
        (
            "PigsFed",
            "Full-feed-budget pig equivalents",
            "=HeadSold+(HeadPlaced-HeadSold)*DeadFeedShare",
            "num",
        ),
    ]
    for name, label, formula, fmt in derived:
        ws.write(r, 1, label, f["label"])
        ws.write_formula(r, 2, formula, f[fmt])
        wb.define_name(name, f"=Inputs!$C${r + 1}")
        r += 1
    return names


def _locations_sheet(wb, ws, locations: Sequence[Location], f) -> None:
    headers = [
        "Location",
        "State",
        "Corn basis $/bu",
        "SBM basis $/ton",
        "DDGS $/ton",
        "Barn rent $/space/yr",
        "Labor wage $/hr",
        "Source / notes",
    ]
    widths = [28, 8, 16, 16, 12, 20, 16, 80]
    for c, (h, w) in enumerate(zip(headers, widths, strict=True)):
        ws.write(0, c, h, f["h"])
        ws.set_column(c, c, w)
    for i in range(MAX_LOCATIONS):
        r = i + 1
        if i < len(locations):
            lo = locations[i]
            vals = [
                lo.name,
                lo.state,
                lo.corn_basis_usd_bu,
                lo.sbm_basis_usd_ton,
                lo.ddgs_usd_ton,
                lo.barn_rent_usd_space_yr,
                lo.labor_wage_usd_hr,
                lo.source,
            ]
        else:
            vals = [None] * 8
        for c, v in enumerate(vals):
            fmt = f["in_txt"] if c in (0, 1, 7) else f["in_num"]
            if v is None:
                ws.write_blank(r, c, None, fmt)
            else:
                ws.write(r, c, v, fmt)
    ws.write(
        MAX_LOCATIONS + 2,
        0,
        "Add a location in any empty yellow row; it appears in the Inputs location dropdown.",
        f["note"],
    )
    ws.freeze_panes(1, 1)


def _feed_sheet(wb, ws, p: Projection, f) -> None:
    headers = [
        "Phase",
        "Feed lb/pig",
        "Corn %",
        "SBM %",
        "DDGS %",
        "Other %",
        "Other $/ton",
        "Tons",
        "Corn bu",
        "SBM tons",
        "DDGS tons",
        "Other tons",
        "Cost $",
        "$/ton",
    ]
    for c, h in enumerate(headers):
        ws.write(0, c, h, f["h"])
    ws.set_column(0, 0, 18)
    ws.set_column(1, 13, 12)
    for i in range(MAX_PHASES):
        r = i + 1
        x = r + 1  # excel row number
        if i < len(p.feed_phases):
            ph = p.feed_phases[i]
            ws.write(r, 0, ph.name, f["in_txt"])
            for c, v in enumerate(
                [ph.feed_lb_per_pig, ph.corn_pct, ph.sbm_pct, ph.ddgs_pct], start=1
            ):
                ws.write(r, c, v, f["in_num"])
            ws.write(r, 6, ph.other_usd_ton, f["in_num"])
        else:
            for c in range(0, 5):
                ws.write_blank(r, c, None, f["in_txt"] if c == 0 else f["in_num"])
            ws.write_blank(r, 6, None, f["in_num"])
        ws.write_formula(r, 5, f'=IF(B{x}="",0,MAX(0,100-C{x}-D{x}-E{x}))', f["num"])
        ws.write_formula(r, 7, f"=N(B{x})*PigsFed/2000", f["num"])
        ws.write_formula(r, 8, f"=H{x}*2000*N(C{x})/100/56", f["num"])
        ws.write_formula(r, 9, f"=H{x}*N(D{x})/100", f["num"])
        ws.write_formula(r, 10, f"=H{x}*N(E{x})/100", f["num"])
        ws.write_formula(r, 11, f"=H{x}*F{x}/100", f["num"])
        ws.write_formula(
            r,
            12,
            f"=I{x}*CornCash+J{x}*SbmCash+K{x}*DdgsPrice+L{x}*N(G{x})+H{x}*FeedMill",
            f["usd"],
        )
        ws.write_formula(r, 13, f"=IF(H{x}=0,0,M{x}/H{x})", f["usd2"])
    tr = MAX_PHASES + 1
    ws.write(tr, 0, "Total", f["sub"])
    for c in (1, 7, 8, 9, 10, 11):
        col = xl_rowcol_to_cell(0, c)[:-1]
        ws.write_formula(tr, c, f"=SUM({col}2:{col}{tr})", f["num"])
    ws.write_formula(tr, 12, f"=SUM(M2:M{tr})", f["total"])
    ws.write_formula(tr, 13, f"=IF(H{tr + 1}=0,0,M{tr + 1}/H{tr + 1})", f["usd2"])
    wb.define_name("FeedCost", f"=Feed!$M${tr + 1}")
    wb.define_name("FeedTons", f"=Feed!$H${tr + 1}")
    ws.write(
        tr + 2,
        0,
        "Other % = premix, fat, amino acids, minerals; priced by the Other $/ton "
        "column. Feed lb/pig is per pig marketed.",
        f["note"],
    )
    ws.freeze_panes(1, 1)


def _market_data_sheet(wb, ws, p: Projection, basis_history, wean_hist, f) -> None:
    ws.set_column("A:A", 14)
    ws.set_column("B:B", 16)
    ws.set_column("D:D", 10)
    ws.set_column("E:E", 16)
    ws.write("A1", "Lean hog futures curve", f["sub"])
    ws.write("A2", "Contract", f["h"])
    ws.write("B2", "$/cwt carcass", f["h"])
    items = sorted(p.lean_hog_futures_cwt.items())
    for i in range(MAX_CONTRACTS):
        r = i + 2
        if i < len(items):
            ws.write(r, 0, items[i][0], f["in_txt"])
            ws.write(r, 1, items[i][1], f["in_num"])
        else:
            ws.write_blank(r, 0, None, f["in_txt"])
            ws.write_blank(r, 1, None, f["in_num"])
    wb.define_name("FutContracts", f"='Market Data'!$A$3:$A${MAX_CONTRACTS + 2}")
    wb.define_name("FutPrices", f"='Market Data'!$B$3:$B${MAX_CONTRACTS + 2}")

    ws.set_column("F:F", 14)
    ws.write("D1", "Avg hog basis (CME Index − nearby futures)", f["sub"])
    ws.write("D2", "Period", f["h"])
    ws.write("E2", "Half-month", f["h"])
    ws.write("F2", "$/cwt carcass", f["h"])
    for period in PERIODS:
        ws.write(period + 1, 3, period, f["int"])
        ws.write(period + 1, 4, period_label(period), f["txt"])
        ws.write(period + 1, 5, p.hog_basis_cwt_by_period.get(period, 0.0), f["in_num"])
    wb.define_name("BasisByPeriod", "='Market Data'!$F$3:$F$26")

    row = 28
    if basis_history is not None and not basis_history.empty:
        ws.write(row, 3, "Basis history by year (CME Index − nearby futures, $/cwt)", f["sub"])
        row += 1
        ws.write(row, 3, "Year", f["h"])
        for period in PERIODS:
            ws.write(row, 3 + period, period_label(period), f["h"])
        for year, vals in basis_history.iterrows():
            row += 1
            ws.write(row, 3, int(year), f["int"])  # type: ignore[arg-type]
            for period in PERIODS:
                v = vals.get(period)
                if v is not None and pd.notna(v):
                    ws.write(row, 3 + period, float(v), f["num"])
        row += 2

    if wean_hist is not None and not wean_hist.empty:
        ws.write(row, 3, "USDA weaned pig prices (weekly)", f["sub"])
        row += 1
        for c, col in enumerate(wean_hist.columns):
            ws.write(row, 3 + c, str(col), f["h"])
        for rec in wean_hist.itertuples(index=False):
            row += 1
            for c, v in enumerate(rec):
                if isinstance(v, pd.Timestamp):
                    ws.write_datetime(row, 3 + c, v.to_pydatetime(), f["date"])
                elif pd.notna(v):
                    ws.write(row, 3 + c, v)


def _marketing_sheet(wb, ws, p: Projection, f) -> None:
    headers = [
        "Days after placement",
        "% of marketed",
        "Live wt lb",
        "Sale date",
        "Contract",
        "Basis period",
        "Futures $/cwt",
        "Basis $/cwt",
        "Premium $/cwt",
        "Price $/cwt carcass",
        "Head",
        "Carcass lb",
        "Revenue $",
    ]
    for c, h in enumerate(headers):
        ws.write(0, c, h, f["h"])
    ws.set_column(0, 12, 15)
    for i in range(MAX_CUTS):
        r = i + 1
        x = r + 1
        if i < len(p.marketing):
            cut = p.marketing[i]
            ws.write(r, 0, cut.days_after_placement, f["in_int"])
            ws.write(r, 1, cut.pct_of_marketed, f["in_pct"])
            ws.write(r, 2, cut.live_weight_lb, f["in_num"])
        else:
            for c in range(3):
                ws.write_blank(r, c, None, f["in_num"])
        on = f'A{x}<>""'
        ws.write_formula(r, 3, f'=IF({on},PlacementDate+A{x},"")', f["date"])
        m, dd = f"MONTH(D{x})", f"DAY(D{x})"
        listed = f"ISNUMBER(MATCH({m},{{2,4,5,6,7,8,10,12}},0))"
        nxt = f"IF({m}<2,2,IF({m}<4,4,IF({m}<8,{m}+1,IF({m}<10,10,IF({m}<12,12,14)))))"
        cm = f"IF(AND({listed},{dd}<=14),{m},{nxt})"
        code = f'(YEAR(D{x})+({cm}>12))&"-"&TEXT({cm}-12*({cm}>12),"00")'
        ws.write_formula(r, 4, f'=IF({on},{code},"")', f["txt"])
        ws.write_formula(r, 5, f"=IF({on},({m}-1)*2+IF({dd}<=14,1,2),0)", f["int"])
        ws.write_formula(r, 6, f"=IF({on},INDEX(FutPrices,MATCH(E{x},FutContracts,0)),0)", f["num"])
        ws.write_formula(r, 7, f"=IF({on},INDEX(BasisByPeriod,F{x}),0)", f["num"])
        ws.write_formula(r, 8, f"=IF({on},Premium,0)", f["num"])
        ws.write_formula(r, 9, f"=G{x}+H{x}+I{x}", f["usd2"])
        ws.write_formula(r, 10, f"=HeadSold*N(B{x})/100", f["num"])
        ws.write_formula(r, 11, f"=N(C{x})*YieldPct/100", f["num"])
        ws.write_formula(r, 12, f"=K{x}*L{x}/100*J{x}", f["usd"])
    tr = MAX_CUTS + 1
    end = tr  # last data row number in excel terms is tr
    ws.write(tr, 0, "Total", f["sub"])
    ws.write_formula(tr, 1, f"=SUM(B2:B{end})", f["num"])
    ws.write_formula(tr, 10, f"=SUM(K2:K{end})", f["num"])
    ws.write_formula(tr, 12, f"=SUM(M2:M{end})", f["total"])
    wb.define_name("GrossRevenue", f"=Marketing!$M${tr + 1}")
    wb.define_name(
        "CarcassCwt", f"=SUMPRODUCT(Marketing!$K$2:$K${end},Marketing!$L$2:$L${end})/100"
    )
    wb.define_name("LiveCwt", f"=SUMPRODUCT(Marketing!$K$2:$K${end},Marketing!$C$2:$C${end})/100")
    wb.define_name("AvgDays", f"=SUMPRODUCT(Marketing!$A$2:$A${end},Marketing!$B$2:$B${end})/100")
    ws.write(
        tr + 2,
        0,
        "% of marketed must total 100. Contract: days 1-14 of a contract month (Feb Apr May "
        "Jun Jul Aug Oct Dec) use that month; otherwise the next contract (ISU B2-41).",
        f["note"],
    )
    ws.conditional_format(
        tr,
        1,
        tr,
        1,
        {
            "type": "cell",
            "criteria": "!=",
            "value": 100,
            "format": wb.add_format({"bg_color": "#F8CBAD"}),
        },
    )


def _costs_sheet(wb, ws, f) -> None:
    ws.set_column("A:A", 24)
    ws.set_column("B:F", 16)
    for c, h in enumerate(
        ["Cost line", "Total $", "$/head placed", "$/head sold", "$/cwt carcass", "% of total"]
    ):
        ws.write(0, c, h, f["h"])
    lines = [
        ("Weaned pigs", "=HeadPlaced*(WeanPrice+WeanFreight)"),
        ("Feed", "=FeedCost"),
        (
            "Barn / facilities",
            f'=IF(BarnMode="{BarnCostMode.PER_SPACE_YEAR.value}",'
            "HeadPlaced*BarnRent*BarnDays/365,HeadPlaced*BarnPerPig)",
        ),
        (
            "Labor",
            f'=IF(LaborMode="{LaborCostMode.HOURLY.value}",'
            "HeadPlaced*LaborHours*LaborWage,HeadPlaced*LaborPerPig)",
        ),
        ("Vet / med", "=HeadPlaced*VetMed"),
        ("Utilities", "=HeadPlaced*Utilities"),
        ("Trucking to market", "=HeadSold*Trucking"),
        ("Insurance / misc", "=HeadPlaced*InsMisc"),
        ("Interest", "=InterestPct/100*AvgDays/365*(B2+0.5*B3)"),
        ("Checkoff", "=GrossRevenue*CheckoffPct/100"),
    ]
    n = len(lines)
    tot = n + 2  # excel row of total
    for i, (label, formula) in enumerate(lines):
        r = i + 1
        x = r + 1
        ws.write(r, 0, label, f["label"])
        ws.write_formula(r, 1, formula, f["usd"])
        ws.write_formula(r, 2, f"=B{x}/HeadPlaced", f["usd2"])
        ws.write_formula(r, 3, f"=B{x}/HeadSold", f["usd2"])
        ws.write_formula(r, 4, f"=B{x}/CarcassCwt", f["usd2"])
        ws.write_formula(r, 5, f"=B{x}/$B${tot}", f["pct"])
    r = n + 1
    ws.write(r, 0, "Total cost", f["sub"])
    ws.write_formula(r, 1, f"=SUM(B2:B{n + 1})", f["total"])
    ws.write_formula(r, 2, f"=B{tot}/HeadPlaced", f["total2"])
    ws.write_formula(r, 3, f"=B{tot}/HeadSold", f["total2"])
    ws.write_formula(r, 4, f"=B{tot}/CarcassCwt", f["total2"])
    wb.define_name("TotalCost", f"=Costs!$B${tot}")
    wb.define_name("CheckoffCost", f"=Costs!$B${n + 1}")


def _dashboard_sheet(wb, ws, f) -> None:
    ws.set_column("A:A", 3)
    ws.set_column("B:B", 34)
    ws.set_column("C:C", 18)
    ws.set_column("D:D", 3)
    ws.set_column("E:E", 34)
    ws.set_column("F:F", 18)
    ws.write("B1", "Wean-to-Finish Group Projection", f["title"])
    ws.write_formula(
        "B2",
        '="Location: "&Location&"   |   Placed: "&TEXT(PlacementDate,'
        '"mmm d, yyyy")&"   |   Head placed: "&TEXT(HeadPlaced,"#,##0")',
        f["note"],
    )
    left = [
        ("Net profit (group)", "=GrossRevenue-TotalCost", "usd"),
        ("Net $/head sold", "=(GrossRevenue-TotalCost)/HeadSold", "usd2"),
        ("Total revenue", "=GrossRevenue", "usd"),
        ("Total cost", "=TotalCost", "usd"),
        ("Revenue $/head sold", "=GrossRevenue/HeadSold", "usd2"),
        ("Cost $/head sold", "=TotalCost/HeadSold", "usd2"),
    ]
    right = [
        (
            "Breakeven $/cwt carcass",
            "=(TotalCost-CheckoffCost)/(CarcassCwt*(1-CheckoffPct/100))",
            "usd2",
        ),
        ("Breakeven $/cwt live", "=F4*YieldPct/100", "usd2"),
        ("Avg sale price $/cwt carcass", "=GrossRevenue/CarcassCwt", "usd2"),
        ("Cost $/cwt carcass", "=TotalCost/CarcassCwt", "usd2"),
        ("Head sold", "=HeadSold", "int"),
        (
            "Feed conversion (lb feed / lb gain)",
            "=FeedTons*2000/(LiveCwt*100-HeadPlaced*WeanWeight)",
            "num",
        ),
    ]
    for i, (label, formula, fmt) in enumerate(left):
        ws.write(3 + i, 1, label, f["kpi_label"])
        ws.write_formula(3 + i, 2, formula, f[fmt])
    for i, (label, formula, fmt) in enumerate(right):
        ws.write(3 + i, 4, label, f["kpi_label"])
        ws.write_formula(3 + i, 5, formula, f[fmt])

    ws.write("B11", "Key prices", f["sub"])
    prices = [
        ("Corn cash $/bu (futures + basis)", "=CornCash"),
        ("Corn basis $/bu", "=CornBasis"),
        ("Soybean meal cash $/ton", "=SbmCash"),
        ("Soybean meal basis $/ton", "=SbmBasis"),
        ("DDGS $/ton", "=DdgsPrice"),
        ("Weaned pig $/head", "=WeanPrice"),
    ]
    for i, (label, formula) in enumerate(prices):
        ws.write(11 + i, 1, label, f["label"])
        ws.write_formula(11 + i, 2, formula, f["usd2"])

    chart = wb.add_chart({"type": "bar"})
    chart.add_series(
        {
            "name": "Cost $/head sold",
            "categories": "=Costs!$A$2:$A$11",
            "values": "=Costs!$D$2:$D$11",
            "fill": {"color": "#2F5597"},
            "data_labels": {"value": True, "num_format": "$#,##0.00"},
        }
    )
    chart.set_title({"name": "Cost per head sold"})
    chart.set_legend({"none": True})
    chart.set_y_axis({"reverse": True})
    chart.set_size({"width": 620, "height": 360})
    ws.insert_chart("E11", chart)
