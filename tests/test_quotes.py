"""Lean hog futures from quote exports (Barchart, DTN ProphetX, Excel)."""

import io
from datetime import date

import pandas as pd
import pytest

from hogproj.data.quotes import parse

TODAY = date(2026, 10, 20)


def test_barchart_quote_board():
    csv = (
        "Symbol,Name,Last,Change,High,Low,Volume,Time\n"
        "HEZ26,Lean Hogs (Dec '26),73.425s,-0.300,74.000,73.100,12345,10/19/26\n"
        "HEG27,Lean Hogs (Feb '27),76.150s,-0.250,76.700,75.900,8000,10/19/26\n"
        "HEJ27,Lean Hogs (Apr '27),80.900s,-0.100,81.200,80.500,4000,10/19/26\n"
        "ZCZ26,Corn (Dec '26),467-0s,-2,470,465,99999,10/19/26\n"
        '"Downloaded from Barchart.com as of 10-20-2026 09:15am CDT"\n'
    )
    prices, as_of = parse(csv.encode(), "futures_lean-hogs_quotes.csv", TODAY)
    assert prices == {(2026, 12): 73.425, (2027, 2): 76.15, (2027, 4): 80.9}  # corn ignored
    assert as_of == date(2026, 10, 20)


def test_dtn_style_symbols_and_settle_column():
    rows = [
        "Symbol,Description,Settle,Last",
        "@HEZ6,LEAN HOGS DEC 26,73.43,73.50",
        "@HEJ7,APR 27,80.90,81",
    ]
    csv = "\n".join(rows) + "\n"
    prices, _ = parse(csv.encode(), "prophetx.csv", TODAY)
    assert prices == {(2026, 12): 73.43, (2027, 4): 80.9}  # Settle preferred over Last


def test_single_contract_history_from_file_name():
    csv = ("Time,Open,High,Low,Last,Change,Volume\n"
           "10/16/2026,74.1,74.5,73.0,73.725,-0.4,9000\n"
           "10/19/2026,73.8,74.0,73.1,73.425,-0.3,8000\n")  # fmt: skip
    prices, as_of = parse(csv.encode(), "hez26_price-history-10-20-2026.csv", TODAY)
    assert prices == {(2026, 12): 73.425}
    assert as_of == date(2026, 10, 20)


def test_excel_quote_board():
    buf = io.BytesIO()
    pd.DataFrame({"Contract": ["HEQ27", "HEV27"], "Close": [92.5, 81.0]}).to_excel(buf, index=False)
    prices, _ = parse(buf.getvalue(), "quotes.xlsx", TODAY)
    assert prices == {(2027, 8): 92.5, (2027, 10): 81.0}


def test_rejects_files_without_hog_contracts():
    with pytest.raises(ValueError):
        parse(b"Symbol,Last\nZCZ26,4.67\n", "corn.csv", TODAY)


def test_one_digit_year_picks_the_nearest_year_across_a_decade():
    from hogproj.data.quotes import _contract

    assert _contract("Z", "9", date(2030, 1, 15)) == (2029, 12)
    assert _contract("G", "0", date(2029, 12, 1)) == (2030, 2)
    assert _contract("Z", "6", date(2026, 10, 20)) == (2026, 12)
    assert _contract("J", "8", date(2026, 10, 20)) == (2028, 4)


def test_board_without_footer_uses_its_newest_trade_date():
    csv = "Symbol,Last,Time\nHEZ26,73.4,10/16/26\nHEG27,76.1,10/15/26\n"
    _, as_of = parse(csv.encode(), "quotes.csv", TODAY)
    assert as_of == date(2026, 10, 16)
