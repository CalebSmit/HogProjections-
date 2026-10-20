"""ERS trade and price spreads, sow slaughter, and the summaries built on them."""

import pandas as pd

from hogproj import hogmarket as hm
from hogproj import national as nv
from hogproj.data import ers_trade
from hogproj.data.mars import fi_weekly

TRADE = (
    '"COMMODITY_DESC","TRADE_FLOW","UNIT_DESC","GEOGRAPHY_CODE","GEOGRAPHY_DESC","YEAR_ID",'
    '"TIMEPERIOD_ID","AMOUNT"\n'
    '"Pork","Exports","Carcass weight, 1,000 pounds",2010,"Mexico",2014,1,1\n'
    '"Pork","Exports","Carcass weight, 1,000 pounds",2010,"Mexico",2025,1,100\n'
    '"Pork","Exports","Carcass weight, 1,000 pounds",2010,"Mexico",2025,9,999\n'
    '"Pork","Exports","Carcass weight, 1,000 pounds",,"World total",2025,1,200\n'
    '"Pork","Exports","Carcass weight, 1,000 pounds",2010,"Mexico",2026,1,110\n'
    '"Pork","Exports","Carcass weight, 1,000 pounds",5880,"Japan",2026,1,90\n'
    '"Pork","Exports","Carcass weight, 1,000 pounds",,"World total",2026,1,230\n'
)


def test_trade_parse_and_exports_ytd():
    df = ers_trade.parse_trade(TRADE)
    assert df["month"].min() == pd.Timestamp("2025-01-01")  # 2014 dropped
    ex = hm.exports_ytd(df)
    assert ex is not None
    assert abs(ex["pct"] - 0.15) < 1e-9  # 230 vs 200: Sep 2025 isn't in "so far" for Jan 2026
    assert list(ex["by_country"].index) == ["Mexico", "Japan"]
    assert abs(ex["by_country"].loc["Mexico", "pct"] - 0.10) < 1e-9


def test_hog_imports_and_canada():
    text = TRADE.split("\n")[0] + "\n" + "\n".join([
        '"Hog, less than 7 kilograms (15.4 pounds)","Imports","Head",,"World total",2025,8,100',
        '"Hog, 7 to less than 23 kilograms (50.7 pounds)","Imports","Head",,"World total",'
        "2025,8,50",
        '"Hog, less than 7 kilograms (15.4 pounds)","Imports","Head",,"World total",2026,8,120',
        '"Hog, 7 to less than 23 kilograms (50.7 pounds)","Imports","Head",,"World total",'
        "2026,8,60",
        '"Hog, 50 kilograms (110.2 pounds) or more for immediate slaughter","Imports","Head",,'
        '"World total",2026,8,40',
        '"Hog, total","Imports","Head",1220,"Canada",2026,8,220',
        '"Hog, total","Imports","Head",,"World total",2026,8,220',
        '"Hog, breeding animals","Exports","Head",2010,"Mexico",2026,8,5',
    ]) + "\n"  # fmt: skip
    df = ers_trade.parse_trade(text, hogs=True)
    assert "Hog, breeding animals" not in set(df["commodity"])
    cp = nv.canada_pigs(df)
    assert cp is not None and cp["pigs"] == 180 and abs(cp["pigs_pct"] - 0.2) < 1e-9
    assert cp["canada_share"] == 1.0


def test_spreads_parse_both_files_and_farmer_share():
    cur = ("﻿Year,Period,Period_Number,Data_Item,Value,Units\n"
           "2026,Annual,17,Pork retail value,400,c\n"
           "2026,September,9,Pork retail value,500,c\n"
           "2026,September,9,Pork net farm value,100,c\n"
           "2026,September,9,Pork wholesale value,150,c\n")  # fmt: skip
    hist = ("Year,Month,Month-number,Data_Item,Value,Units\n"
            "2025,September,9,Pork retail value,480,c\n"
            "2025,September,9,Pork net farm value,120,c\n")  # fmt: skip
    df = pd.concat([ers_trade.parse_spreads(hist), ers_trade.parse_spreads(cur)])
    assert len(df) == 5  # annual row dropped
    fs = hm.farmer_share(df)
    assert fs is not None and fs["share"] == 0.2 and fs["year_ago"] == 0.25


def test_sow_slaughter_vs_year_ago():
    weeks = pd.date_range("2025-08-09", "2026-10-03", freq="W-SAT")
    rows = [
        {
            "report_end_date": f"{w:%m/%d/%Y}",
            "commodity": "Slaughter Hogs",
            "class": "Sows",
            "unit": "Head",
            "volume": "55000" if w.year == 2026 else "50000",
        }
        for w in weeks
    ]
    rows.append({"report_end_date": "10/03/2026", "commodity": "Slaughter Hogs",
                 "class": "Sows", "unit": "Pct", "volume": "2.1"})  # fmt: skip
    fw = fi_weekly(rows)
    assert len(fw) == len(weeks)  # the percent row is dropped
    got = hm.sow_slaughter_vs_year_ago(fw)
    assert got is not None and abs(got["pct"] - 0.1) < 1e-9 and got["per_week"] == 55000
    sig = next(s for s in hm.signals(pd.DataFrame(columns=["date", "spread_per_head", "cutout",
                                                           "weight_lb", "head"]), sows=got)
               if s.name == "Sow slaughter")  # fmt: skip
    assert sig.tone == "good"
