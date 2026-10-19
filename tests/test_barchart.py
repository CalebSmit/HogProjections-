"""Barchart import: both download layouts, unit fixes, storage. Synthetic files only."""

import io

import openpyxl
import pytest

from hogproj.data import barchart
from hogproj.data.barchart import Kind, guess_kind, hog_contract_from_symbol, read_upload

WEBSITE_CSV = """Time,Open,High,Low,Latest,Change,%Change,Volume,Open Int
09/22/2026,82.47,82.47,82.47,82.47,-0.45,-0.54%,0,0
09/21/2026,82.92,82.92,82.92,82.92,-0.50,-0.60%,0,0
"Downloaded from Barchart.com as of 09-25-2026 01:03pm CDT"
"""


def excel_layout(symbol: str, rows: list[tuple]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Data"
    ws.append(["1 Day", symbol])
    ws.append(["Date", "Open", "High", "Low", "Close"])
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_website_csv_with_footer():
    (s,) = read_upload("lean-hog-index_price-history.csv", WEBSITE_CSV.encode())
    assert s.kind is Kind.CME_INDEX
    assert list(s.data.values) == [82.92, 82.47]  # sorted by date
    assert str(s.data.index[0])[:10] == "2026-09-21"


def test_excel_layout_skips_dashes_and_reads_symbol():
    import datetime as dt

    content = excel_layout(
        "LS255_CPEW10_12LTC_PR",
        [
            (dt.datetime(2026, 9, 13), 1, 1, 1, 28.5),
            (dt.datetime(2026, 9, 6), " --- ", "", "", " --- "),
        ],
    )
    (s,) = read_upload("weaned.xlsx", content)
    assert s.kind is Kind.WEAN_PIG
    assert s.symbol == "LS255_CPEW10_12LTC_PR"
    assert list(s.data.values) == [28.5]


def test_corn_in_cents_becomes_dollars_on_save_whatever_was_guessed(tmp_path, monkeypatch):
    import datetime as dt

    monkeypatch.setattr(barchart, "STORE", tmp_path)
    content = excel_layout("ZCZ26", [(dt.datetime(2026, 10, 16), 1, 1, 1, "474-2")])
    (s,) = read_upload("prices.xlsx", content)
    assert s.data.iloc[0] == pytest.approx(474.25)  # grain eighths parsed; still cents
    barchart.save(s.data, Kind.CORN_FUTURES)  # user picked the kind by hand
    assert barchart.load(Kind.CORN_FUTURES).iloc[0] == pytest.approx(4.7425)
    assert barchart.implausible(s.data, Kind.CORN_FUTURES) is None
    corn_dollars = barchart.load(Kind.CORN_FUTURES)
    assert "looks wrong" in (barchart.implausible(corn_dollars, Kind.SBM) or "")  # $4.74 meal


def test_contract_box_is_validated():
    assert barchart.normalise_contract("HEJ27") == "2027-04"
    assert barchart.normalise_contract(" 2026-12 ") == "2026-12"
    with pytest.raises(ValueError):
        barchart.normalise_contract("2027-03")  # not a listed month
    with pytest.raises(ValueError):
        barchart.normalise_contract("../../x")


def test_contract_and_kind_guessing():
    assert hog_contract_from_symbol("@HEJ27") == "2027-04"
    assert hog_contract_from_symbol("hez26_daily.csv") == "2026-12"
    assert guess_kind("HEJ27") is Kind.HOG_FUTURES
    assert guess_kind("@SMV26") is Kind.SBM
    assert guess_kind("CORN$.5328") is Kind.CORN_CASH
    assert guess_kind("Corn Spot Price - CF") is Kind.CORN_CASH
    assert guess_kind("ZCZ26") is Kind.CORN_FUTURES
    assert guess_kind("Smith farm prices") is None
    assert guess_kind("Delhi grain") is None
    assert guess_kind("CME Index") is Kind.CME_INDEX
    assert guess_kind("something else") is None


def test_save_merges_and_loads(tmp_path, monkeypatch):
    monkeypatch.setattr(barchart, "STORE", tmp_path)
    (s,) = read_upload("idx.csv", WEBSITE_CSV.encode())
    barchart.save(s.data, Kind.CME_INDEX)
    barchart.save(s.data.iloc[:1] + 1, Kind.CME_INDEX)  # newer value for one date wins
    got = barchart.load(Kind.CME_INDEX)
    assert list(got.values) == [83.92, 82.47]
    assert barchart.inventory()["rows"].tolist() == [2]
    with pytest.raises(ValueError):
        barchart.save(s.data, Kind.HOG_FUTURES)
    barchart.save(s.data, Kind.HOG_FUTURES, "2027-04")
    assert list(barchart.hog_contracts()) == ["2027-04"]


def test_sheet_name_beats_workbook_file_name():
    import datetime as dt

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Corn Spot Price - CF"
    ws.append(["1 Day", "CORN$.5328"])
    ws.append(["Date", "Open", "High", "Low", "Close"])
    ws.append([dt.datetime(2026, 9, 24), 4.73, 4.73, 4.73, 4.73])
    buf = io.BytesIO()
    wb.save(buf)
    (s,) = read_upload("My_Wean_Pig_Crush.xlsx", buf.getvalue())
    assert s.kind is Kind.CORN_CASH
