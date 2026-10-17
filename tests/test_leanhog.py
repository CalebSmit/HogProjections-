"""Index rebuild and parsers, on hand-made rows shaped like the documented LM_HG201 JSON.

The schema follows LMR Datamart report 2511 (fields are strings, with thousands commas).
"""

import pandas as pd
import pytest

from hogproj.data.leanhog import (
    cme_index,
    parse_lm_hg201,
    parse_yahoo_chart,
    yahoo_contract_symbol,
)


def row(day: str, ptype: str, head: str, wt: str, price: str) -> dict:
    return {
        "report_date": day,
        "purchase_type": ptype,
        "head_count": head,
        "avg_carcass_weight": wt,
        "avg_net_price": price,
    }


ROWS = [
    row("10/14/2026", "Prod. Sold Negotiated", "5,000", "200.00", "70.00"),
    row("10/14/2026", "Prod. Sold Swine or Pork Market Formula", "10,000", "210.00", "80.00"),
    row("10/14/2026", "Prod. Sold Negotiated Formula", "1,000", "200.00", "75.00"),
    row("10/14/2026", "Prod. Sold Other Market Formula", "50,000", "210.00", "99.00"),
    row("10/14/2026", "Pack. Sold Negotiated", "9,999", "200.00", "10.00"),
    row("10/15/2026", "Prod. Sold Negotiated", "4,000", "205.00", "72.00"),
    row("10/15/2026", "Prod. Sold Swine or Pork Market Formula", "9,000", "212.00", "79.00"),
]


def test_parse_keeps_only_index_purchase_types():
    df = parse_lm_hg201(ROWS)
    assert set(df["bucket"]) == {"negotiated", "spmf", "negotiated_formula"}
    assert len(df) == 5
    assert df["head"].iloc[0] == 5000


def test_two_day_weighted_index():
    idx = cme_index(parse_lm_hg201(ROWS))
    assert len(idx) == 1  # needs two report days
    lbs = [5000 * 200, 10000 * 210, 1000 * 200, 4000 * 205, 9000 * 212]
    px = [70, 80, 75, 72, 79]
    expected = sum(lb * p for lb, p in zip(lbs, px, strict=True)) / sum(lbs)
    assert idx.iloc[0] == pytest.approx(expected)
    assert idx.index[0] == pd.Timestamp("2026-10-15")


def test_negotiated_formula_excluded_before_oct_2016():
    rows = [
        row("10/03/2016", "Prod. Sold Negotiated", "100", "200", "60"),
        row("10/03/2016", "Prod. Sold Negotiated Formula", "100", "200", "90"),
        row("10/04/2016", "Prod. Sold Negotiated", "100", "200", "60"),
    ]
    assert cme_index(parse_lm_hg201(rows)).iloc[0] == pytest.approx(60.0)


def test_yahoo_chart_parse():
    data = {
        "chart": {
            "result": [
                {
                    "timestamp": [1760572800, 1760659200, 1760745600],
                    "indicators": {"quote": [{"close": [66.5, None, 66.925]}]},
                }
            ]
        }
    }
    s = parse_yahoo_chart(data)
    assert list(s.values) == [66.5, 66.925]


def test_yahoo_contract_symbol():
    assert yahoo_contract_symbol("2027-04") == "HEJ27.CME"
    assert yahoo_contract_symbol("2026-12") == "HEZ26.CME"
