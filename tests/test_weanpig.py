"""Parser and lot-size selection for the USDA weekly feeder pig report (slug 2810).

The rows are hand-made, with field names guessed from other MARS livestock reports. The real
names for 2810 are unverified, so the parser matches by keyword. Swap in a recorded response
(tests/fixtures/) once one is captured on a machine that can reach USDA.
"""

import pytest

from hogproj.data.weanpig import lot_min_head, parse_feeder_pig, weekly_price


def rec(day: str, cls: str, kind: str, lot: str, head: str, price: str) -> dict:
    return {
        "report_end_date": day,
        "class": cls,
        "purchase_type": kind,
        "lot_desc": lot,
        "head_count": head,
        "wtd_avg": price,
    }


ROWS = [
    rec("10/09/2026", "Early Weaned", "Cash", "Under 600 Head", "5,000", "30.00"),
    rec("10/09/2026", "Early Weaned", "Cash", "600-1,200 Head", "10,000", "28.00"),
    rec("10/09/2026", "Early Weaned", "Cash", "1,200 Head and Over", "60,000", "25.00"),
    rec("10/09/2026", "Early Weaned", "Formula", "1,200 Head and Over", "20,000", "35.00"),
    rec("10/09/2026", "Feeder Pigs", "Cash", "1,200 Head and Over", "9,000", "45.00"),
    rec("10/16/2026", "Early Weaned", "Cash", "1,200 Head and Over", "50,000", "22.00"),
    rec("10/16/2026", "Early Weaned", "Cash", "2,400 Head and Over", "30,000", "21.00"),
]


def test_lot_min_head():
    assert lot_min_head("Under 600 Head") == 0
    assert lot_min_head("600-1,200 Head") == 600
    assert lot_min_head("1,200 Head and Over") == 1200
    assert lot_min_head("2,400+ head") == 2400


def test_parse_keeps_early_weaned_only():
    df = parse_feeder_pig(ROWS)
    assert len(df) == 6
    assert set(df["purchase"]) == {"cash", "formula"}


def test_weekly_cash_prefers_2400_else_largest_lot():
    w = weekly_price(parse_feeder_pig(ROWS), "cash", min_lot_head=2400)
    assert list(w["price_usd_hd"]) == pytest.approx([25.00, 21.00])
    assert w.iloc[0]["lot"] == "1,200 Head and Over"  # no 2,400 bucket that week
    assert w.iloc[1]["lot"] == "2,400 Head and Over"


def test_weekly_formula():
    w = weekly_price(parse_feeder_pig(ROWS), "formula")
    assert list(w["price_usd_hd"]) == pytest.approx([35.00])


def test_negotiated_formula_is_formula():
    df = parse_feeder_pig(
        [rec("10/09/2026", "Early Weaned", "Negotiated Formula", "1,200 Head and Over", "10", "30")]
    )
    assert list(df["purchase"]) == ["formula"]
