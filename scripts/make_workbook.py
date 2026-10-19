"""Regenerate W2F_Projection.xlsx in the repo root from the bundled defaults.

Usage: uv run python scripts/make_workbook.py [YYYY-MM-DD placement date]

This is for people who only want Excel: open the file, pick a location from the dropdown on
the Inputs sheet, and change any yellow cell.
"""

import sys
from datetime import date, timedelta

from hogproj.basis import basis_period, lean_hog_contract_for
from hogproj.config import ROOT
from hogproj.crush import CrushSpec, Week, report_dates, sale_for
from hogproj.data.defaults import default_projection, load_locations
from hogproj.excel import build_workbook
from hogproj.tables import fill_curve

placed = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2026, 10, 19)
locations = load_locations()
p = default_projection(locations[0], placement_date=placed)
out = ROOT / "W2F_Projection.xlsx"
# Weekly crush template: 12 weekly reports, every week at today's default prices (type over).
weeks = []
for d in report_dates(placed - timedelta(days=1), 12, 0):
    sold = sale_for(d, 1, 160)
    contract = lean_hog_contract_for(sold)
    curve, _ = fill_curve(p.lean_hog_futures_cwt, [contract])  # nearest if not listed
    weeks.append(
        Week(
            d,
            p.wean_pig_usda_cash_usd_hd,
            p.corn_futures_usd_bu,
            p.sbm_futures_usd_ton,
            p.location.ddgs_usd_ton,
            curve[contract],
            p.hog_basis_cwt_by_period.get(basis_period(sold), 0.0),
        )
    )
out.write_bytes(build_workbook(p, locations, crush=CrushSpec(weeks)))
print(f"wrote {out} (placed {placed}, {len(locations)} locations)")
