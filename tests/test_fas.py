"""USDA FAS weekly pork export sales: parsing and the weekly summary."""

import pandas as pd

from hogproj import hogmarket as hm
from hogproj.data import fas


def _row(week: str, code: int, net: float, ship: float) -> dict:
    return {"commodityCode": 1702, "countryCode": code, "weeklyExports": ship,
            "accumulatedExports": 0, "outstandingSales": 0, "currentMYNetSales": net,
            "weekEndingDate": f"{week}T00:00:00"}  # fmt: skip


def test_parse_names_countries_and_drops_empty_rows():
    countries = {2010: "Mexico", 5880: "Japan"}
    df = fas.parse([_row("2026-10-08", 2010, 15362, 15708), _row("2026-10-08", 5880, 0, 0),
                    _row("2026-10-08", 9999, 5, 0)], countries)  # fmt: skip
    assert list(df["country"]) == ["Mexico", "9999"]  # Japan's all-zero row dropped
    assert df["net_sales_mt"].iloc[0] == 15362


def test_weekly_summary_ytd_and_four_weeks():
    weeks = pd.date_range("2025-01-02", "2026-10-08", freq="7D")  # Thursdays
    rows = []
    for w in weeks:
        k = 1.1 if w.year == 2026 else 1.0
        rows += [{"week_ending": w, "country": "Mexico", "net_sales_mt": 100 * k,
                  "exports_mt": 100 * k, "accumulated_mt": 0, "outstanding_mt": 0},
                 {"week_ending": w, "country": "Unknown", "net_sales_mt": 10,
                  "exports_mt": 10, "accumulated_mt": 0, "outstanding_mt": 0}]  # fmt: skip
    got = hm.export_sales_weekly(pd.DataFrame(rows))
    assert got is not None
    assert abs(got["pct"] - (110 / 100 * 100 + 10) / 110 + 1) < 0.02  # ~+9% incl. Unknown
    assert list(got["by_country"].index) == ["Mexico"]  # "Unknown" isn't a buyer
    assert abs(got["by_country"].loc["Mexico", "pct"] - 0.1) < 1e-9
    assert got["label"] == "week ending Oct 8"
    assert hm.export_sales_weekly(pd.DataFrame()) is None
