"""Regenerate W2F_Projection.xlsx in the repo root from the bundled defaults.

Usage: uv run python scripts/make_workbook.py [YYYY-MM-DD placement date]

This is for people who only want Excel: open the file, pick a location from the dropdown on
the Inputs sheet, and change any yellow cell.
"""

import sys
from datetime import date

from hogproj.config import ROOT
from hogproj.data.defaults import default_projection, load_locations
from hogproj.excel import build_workbook

placed = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2026, 10, 19)
locations = load_locations()
p = default_projection(locations[0], placement_date=placed)
out = ROOT / "W2F_Projection.xlsx"
out.write_bytes(build_workbook(p, locations))
print(f"wrote {out} (placed {placed}, {len(locations)} locations)")
