"""The Excel workbook must compute the same numbers as the Python model.

The workbook is recalculated with LibreOffice (headless). The test is skipped if
LibreOffice isn't installed; CI installs it on Linux.
"""

import shutil
import subprocess
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
    return {
        str(ws.cell(r, 1).value): float(ws.cell(r, 2).value or 0)  # type: ignore[arg-type]
        for r in range(2, 12)
    }


@pytest.mark.skipif(SOFFICE is None, reason="LibreOffice not installed")
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
    expected = project(p)
    wb = recalc(build_workbook(p, [p.location]), tmp_path)

    got = costs_by_line(wb)
    for line, total in expected.costs.set_index("line")["total_usd"].items():
        assert got[str(line)] == pytest.approx(total, rel=1e-9, abs=1e-6), line

    dash = wb["Dashboard"]
    assert dash["C4"].value == pytest.approx(expected.summary["net_usd"])
    assert dash["C6"].value == pytest.approx(expected.summary["gross_revenue_usd"])
    assert dash["F4"].value == pytest.approx(expected.summary["breakeven_cwt_carcass"])
    assert dash["F9"].value == pytest.approx(expected.summary["feed_conversion"])
