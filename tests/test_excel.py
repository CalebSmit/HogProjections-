"""The Excel workbook must compute the same numbers as the Python model.

The workbook is recalculated with LibreOffice (headless). The test is skipped if
LibreOffice isn't installed; CI installs it on Linux.
"""

import shutil
import subprocess
from datetime import date
from pathlib import Path

import openpyxl
import pytest

from hogproj.excel import build_workbook
from hogproj.inputs import LaborCostMode, MarketingCut, WeanPigPriceSource
from hogproj.model import project
from tests.test_model import make

SOFFICE = shutil.which("soffice") or shutil.which("libreoffice")


# LibreOffice keeps cached formula results on load unless told to always recalculate.
RECALC_XCU = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry"
  xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Calc/Formula/Load">
  <prop oor:name="OOXMLRecalcMode" oor:op="fuse"><value>0</value></prop>
</item>
</oor:items>
"""


def recalc(xlsx_bytes: bytes, tmp_path: Path) -> openpyxl.Workbook:
    src = tmp_path / "in.xlsx"
    src.write_bytes(xlsx_bytes)
    out = tmp_path / "out"
    profile = tmp_path / "lo_profile"
    (profile / "user").mkdir(parents=True)
    (profile / "user" / "registrymodifications.xcu").write_text(RECALC_XCU)
    assert SOFFICE
    subprocess.run(
        [
            SOFFICE,
            f"-env:UserInstallation={profile.as_uri()}",
            "--headless",
            "--calc",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(out),
            str(src),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return openpyxl.load_workbook(out / "in.xlsx", data_only=True)


def costs_by_line(wb: openpyxl.Workbook) -> dict[str, float]:
    ws = wb["Costs"]
    out: dict[str, float] = {}
    r = 2
    while ws.cell(r, 1).value not in (None, "Total cost"):
        out[str(ws.cell(r, 1).value)] = float(ws.cell(r, 2).value or 0)  # type: ignore[arg-type]
        r += 1
    return out


needs_lo = pytest.mark.skipif(SOFFICE is None, reason="LibreOffice not installed")


@needs_lo
@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {
            "checkoff_pct": 0.35,
            "interest_rate_pct": 8.0,
            "dead_feed_share": 0.3,
            "wean_pig_source": WeanPigPriceSource.MANUAL,
            "wean_pig_manual_usd_hd": 55.0,
            "labor_mode": LaborCostMode.PER_PIG_PLACED,
            "labor_usd_pig_placed": 3.0,
            "lean_hog_futures_cwt": {"2026-06": 100.0, "2026-07": 104.0},
            "hog_basis_cwt_by_period": {10: -2.0, 12: 1.5},
            "marketing": [
                MarketingCut(days_after_placement=140, pct_of_marketed=40, live_weight_lb=280),
                MarketingCut(days_after_placement=165, pct_of_marketed=60, live_weight_lb=290),
            ],
        },
    ],
)
def test_workbook_matches_model(tmp_path, overrides):
    p = make(**overrides)
    check_workbook(p, [p.location], tmp_path)


@needs_lo
def test_workbook_edge_cases(tmp_path):
    """Stale copy of the selected location in the list, an unselected location sorted first,
    a 0% cut with no futures price, and a Dec 20 sale rolling to next year's Feb contract."""
    p = make(
        placement_date=date(2026, 7, 23),
        marketing=[
            MarketingCut(days_after_placement=150, pct_of_marketed=100, live_weight_lb=285),
            MarketingCut(days_after_placement=200, pct_of_marketed=0, live_weight_lb=300),
        ],
        lean_hog_futures_cwt={"2027-02": 90.0},
        hog_basis_cwt_by_period={24: 4.0},
    )
    assert project(p).marketing.loc[0, "contract"] == "2027-02"
    stale = p.location.model_copy(update={"corn_basis_usd_bu": -9.0})
    other = p.location.model_copy(update={"name": "AAA first", "ddgs_usd_ton": 999.0})
    check_workbook(p, [other, stale], tmp_path)


@needs_lo
def test_default_projection_workbook(tmp_path):
    from hogproj.data.defaults import default_projection, load_locations

    locs = load_locations()
    p = default_projection(locs[1], placement_date=date(2026, 10, 19))
    check_workbook(p, locs, tmp_path)


@needs_lo
def test_workbook_matches_crush_layout_inputs(tmp_path):
    """Every new input (adder, hedges, carry, $/pig mortality and interest, G&A, other, debt)."""
    from tests.test_crush_parity import app_projection

    p = app_projection()
    check_workbook(p, [p.location], tmp_path)


@needs_lo
def test_workbook_rate_interest_and_pct_mortality_with_new_lines(tmp_path):
    p = make(
        ga_usd_hd=2.0,
        other_usd_hd_sold=-1.5,
        wean_pig_adder_usd_hd=6.0,
        corn_carry_usd_bu=0.2,
        corn_hedged_pct=30,
        corn_hedged_usd_bu=4.1,
        hog_hedged_pct=50,
        hog_hedged_cwt=105.0,
        interest_rate_pct=7.0,
        principal_usd_hd=3.0,
        term_interest_usd_hd=1.0,
    )
    check_workbook(p, [p.location], tmp_path)


def check_workbook(p, locations, tmp_path):
    expected = project(p)
    wb = recalc(build_workbook(p, locations), tmp_path)

    got = costs_by_line(wb)
    for line, total in expected.costs.set_index("line")["total_usd"].items():
        assert got[str(line)] == pytest.approx(total, rel=1e-9, abs=1e-6), line

    dash = wb["Dashboard"]
    assert dash["C4"].value == pytest.approx(expected.summary["net_usd"])
    assert dash["C6"].value == pytest.approx(expected.summary["gross_revenue_usd"])
    assert dash["C10"].value == pytest.approx(expected.summary["debt_service_usd"])
    assert dash["C11"].value == pytest.approx(expected.summary["net_after_debt_usd_per_head_sold"])
    assert dash["F4"].value == pytest.approx(expected.summary["breakeven_cwt_carcass"])
    assert dash["F9"].value == pytest.approx(expected.summary["feed_conversion"])
