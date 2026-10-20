"""Hog market structure: cutout parser, packer spread, weekly roll-up and signal rules."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from hogproj import hogmarket as hm
from hogproj.data import lmr

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_cutout_fixture():
    df = lmr.parse(json.loads((FIXTURES / "lm_pk602_cutout.json").read_text()), lmr.CUTOUT)
    assert list(df["date"]) == list(pd.to_datetime(["2026-10-14", "2026-10-15", "2026-10-16"]))
    last = df.iloc[-1]
    assert last["carcass"] == pytest.approx(80.55)  # USDA LM_PK602 afternoon, Oct 16, 2026
    assert last["belly"] == pytest.approx(91.14)
    assert last["loads"] == pytest.approx(273.44)


def test_cutout_offline_uses_sample(tmp_path, monkeypatch):
    monkeypatch.setattr(lmr, "CACHE_DIR", tmp_path)
    df, source, note = lmr.load(lmr.CUTOUT, offline=True)
    assert source == "sample"
    assert df["date"].min() <= pd.Timestamp("2020-01-10")
    assert "Offline" in note


def _market(
    days: int = 800, weight_shift: float = 0.0, head_shift: float = 0.0, cut_trend: float = 0.0
) -> pd.DataFrame:
    """Synthetic daily market: flat prices; the last 28 days can differ from a year earlier."""
    dates = pd.bdate_range("2024-01-01", periods=days)
    recent = dates > dates[-1] - pd.Timedelta(days=28)
    weight = np.where(recent, 215 + weight_shift, 215.0)
    head = np.where(recent, 250_000 * (1 + head_shift), 250_000.0)
    cutout = 90 + np.where(dates > dates[-1] - pd.Timedelta(days=14), cut_trend, 0.0)
    df = pd.DataFrame(
        {"date": dates, "index": 80.0, "cutout": cutout, "head": head, "weight_lb": weight}
    )
    df["spread"] = df["cutout"] - df["index"]
    df["spread_per_head"] = df["spread"] * df["weight_lb"] / 100
    return df


def test_daily_spread_arithmetic():
    hg = pd.DataFrame(
        {
            "slaughter_date": pd.to_datetime(["2026-10-15"]),
            "purchase_type": [hm.ALL_TYPES],
            "head_count": [200_000.0],
            "avg_weight_lb_carcass": [220.0],
        }
    )
    idx = pd.DataFrame(
        {"index_date": pd.to_datetime(["2026-10-15"]), "lean_hog_index_usd_per_cwt_carcass": [75.0]}
    )
    cut = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-10-15"]),
            "carcass": [85.0],
            "belly": [90.0],
            "loin": [80.0],
            "ham": [70.0],
        }
    )
    d = hm.daily(hg, idx, cut)
    assert d["spread"].iloc[0] == pytest.approx(10.0)
    assert d["spread_per_head"].iloc[0] == pytest.approx(22.0)  # $10/cwt × 220 lb


def test_weekly_is_head_weighted():
    d = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-10-12", "2026-10-13"]),
            "index": [70.0, 80.0],
            "cutout": [80.0, 90.0],
            "spread": [10.0, 10.0],
            "spread_per_head": [21.0, 22.0],
            "head": [100.0, 300.0],
            "weight_lb": [200.0, 220.0],
        }
    )
    w = hm.weekly(d).iloc[0]
    assert w["head"] == 400
    assert w["weight_lb"] == pytest.approx((100 * 200 + 300 * 220) / 400)
    assert w["index"] == pytest.approx(75)


def _tone(sigs: list[hm.Signal], name: str) -> str:
    return next(s.tone for s in sigs if s.name == name)


@pytest.mark.parametrize(("shift", "tone"), [(2.5, "bad"), (-2.5, "good"), (1.0, "neutral")])
def test_weight_signal_thresholds(shift, tone):
    assert _tone(hm.signals(_market(weight_shift=shift)), "Carcass weights") == tone


@pytest.mark.parametrize(("shift", "tone"), [(0.05, "bad"), (-0.05, "good"), (0.01, "neutral")])
def test_slaughter_signal_thresholds(shift, tone):
    assert _tone(hm.signals(_market(head_shift=shift)), "Slaughter") == tone


@pytest.mark.parametrize(("trend", "tone"), [(4.0, "good"), (-4.0, "bad"), (1.0, "neutral")])
def test_cutout_signal_thresholds(trend, tone):
    assert _tone(hm.signals(_market(cut_trend=trend)), "Pork cutout") == tone


@pytest.mark.parametrize(("pct", "tone"), [(0.02, "bad"), (-0.02, "good"), (0.0, "neutral")])
def test_supply_signal(pct, tone):
    assert _tone(hm.signals(_market(), supply_pct=pct), "Supply ahead") == tone


def test_overall_score():
    def s(tone: str) -> hm.Signal:
        return hm.Signal("x", "", "", tone, "")  # type: ignore[arg-type]

    assert hm.overall([s("good"), s("good"), s("neutral")])[0] == "good"
    assert hm.overall([s("bad"), s("bad"), s("good"), s("bad")])[0] == "bad"
    assert hm.overall([s("good"), s("bad")])[0] == "neutral"


def test_vs_year_ago_lines_up_weekdays():
    d = _market(head_shift=0.10)
    y = hm.vs_year_ago(d, "head", how="sum")
    assert y["pct"] == pytest.approx(0.10, abs=1e-9)


# --- WASDE ----------------------------------------------------------------------------------
def test_parse_wasde_october_2026():
    from hogproj.data.wasde import parse

    df = parse((FIXTURES / "wasde1026.txt").read_text(encoding="utf-8", errors="replace"))
    v = df.set_index(["series", "year", "quarter"])["value"]
    assert v[("pork_production_mlb", 2027, 1)] == 6950  # Oct 2026 WASDE, Q1 2027 projection
    assert v[("barrows_gilts_usd_cwt_live", 2026, 4)] == 55.00
    assert v[("barrows_gilts_usd_cwt_live", 2026, 3)] == 67.86
    proj = df.set_index(["series", "year", "quarter"])["projected"]
    assert proj[("pork_production_mlb", 2026, 4)] and not proj[("pork_production_mlb", 2026, 3)]
    assert (df["report"] == "October 2026").all()


def test_wasde_outlook_and_signal():
    from hogproj.data.wasde import parse

    df = parse((FIXTURES / "wasde1026.txt").read_text(encoding="utf-8", errors="replace"))
    o = hm.wasde_outlook(df, pd.Timestamp("2026-10-20"))
    assert o is not None
    assert o["quarters"] == [(2027, 1), (2027, 2)]
    assert o["pct"] == pytest.approx((6950 + 6720) / (7050 + 6755) - 1)  # -1.0%
    assert o["price_next_q"] == 60.0
    sig = next(s for s in hm.signals(_market(), wasde=o) if s.name == "USDA pork outlook")
    assert sig.tone == "neutral"  # -0.98% is inside the ±1% band


def test_wasde_outlook_missing_quarters():
    df = pd.DataFrame(
        {
            "year": [2026],
            "quarter": [1],
            "series": ["pork_production_mlb"],
            "value": [7000.0],
            "projected": [False],
            "report": ["x"],
        }
    )
    assert hm.wasde_outlook(df, pd.Timestamp("2026-10-20")) is None


def test_parse_wasde_rejects_other_text():
    from hogproj.data.wasde import parse

    with pytest.raises(ValueError):
        parse("National Daily Hog Report")


# --- Cold storage (ERS) -------------------------------------------------------------------
def test_ers_parse_pork_cold_storage():
    from hogproj.data.ers import parse

    raw = pd.DataFrame(
        {
            "commodity_desc": ["Pork", "Pork", "Beef", "Pork"],
            "attribute_desc": [
                "Cold storage",
                "Cold storage",
                "Cold storage",
                "Commercial production",
            ],
            "year_id": [2026, 2009, 2026, 2026],
            "timeperiod_id": [9, 9, 9, 9],
            "amount": [436.269, 530.1, 400.0, 2000.0],
        }
    )
    df = parse(raw)
    assert list(df["month"]) == [pd.Timestamp("2026-09-01")]  # pre-2010 and other series dropped
    assert df["pork_stocks_mlb"].iloc[0] == pytest.approx(436.269)


def _storage(last: float) -> pd.DataFrame:
    months = pd.to_datetime([f"{y}-09-01" for y in range(2020, 2027)])
    return pd.DataFrame({"month": months, "pork_stocks_mlb": [500.0] * 6 + [last]})


@pytest.mark.parametrize(("last", "tone"), [(560.0, "bad"), (450.0, "good"), (510.0, "neutral")])
def test_storage_signal(last, tone):
    st = hm.storage_vs_normal(_storage(last))
    assert st is not None and st["years"] == 5 and st["avg"] == pytest.approx(500)
    sig = next(s for s in hm.signals(_market(), storage=st) if s.name == "Cold storage")
    assert sig.tone == tone


def test_wasde_ratio_and_contract_prices():
    from datetime import date

    w = pd.DataFrame(
        {
            "year": [2026, 2026, 2027],
            "quarter": [2, 3, 1],
            "series": ["barrows_gilts_usd_cwt_live"] * 3,
            "value": [60.0, 64.0, 66.0],
            "projected": [False, False, True],
            "report": ["x"] * 3,
        }
    )
    days = pd.bdate_range("2026-04-01", "2026-09-30")
    price = np.where(np.array([d.month for d in days]) <= 6, 81.0, 86.4)
    idx = pd.DataFrame({"index_date": days, "lean_hog_index_usd_per_cwt_carcass": price})
    r = hm.wasde_to_index_ratio(w, idx)
    assert r is not None
    assert r == pytest.approx((81 / 60 + 86.4 / 64) / 2)  # 1.35
    got = hm.wasde_contract_prices(
        [(2027, 2), (2027, 12)], [date(2027, 2, 12), date(2027, 12, 14)], w, r
    )
    assert got == {(2027, 2): round(66 * r * 4) / 4}  # Dec 2027 past the horizon: left out


def test_drop_value_adds_to_the_spread_and_backfills():
    hg = pd.DataFrame(
        {
            "slaughter_date": pd.to_datetime(["2021-06-01", "2026-10-15"]),
            "purchase_type": [hm.ALL_TYPES] * 2,
            "head_count": [1.0, 1.0],
            "avg_weight_lb_carcass": [200.0, 200.0],
        }
    )
    idx = pd.DataFrame(
        {
            "index_date": pd.to_datetime(["2021-06-01", "2026-10-15"]),
            "lean_hog_index_usd_per_cwt_carcass": [100.0, 75.0],
        }
    )
    cut = pd.DataFrame(
        {
            "date": pd.to_datetime(["2021-06-01", "2026-10-15"]),
            "carcass": [110.0, 80.0],
            "belly": 0.0,
            "loin": 0.0,
            "ham": 0.0,
        }
    )
    drop = pd.DataFrame(
        {
            "week_ending": pd.to_datetime(["2022-02-11", "2026-10-09"]),
            "drop_usd_per_cwt_carcass": [8.0, 6.9],
        }
    )
    d = hm.daily(hg, idx, cut, drop).set_index("date")
    assert d.loc["2026-10-15", "spread"] == pytest.approx(80 + 6.9 - 75)
    assert d.loc["2021-06-01", "drop"] == pytest.approx(8.0)  # before the series: first value


@pytest.mark.parametrize(("now", "tone"), [(110, "good"), (90, "bad"), (102, "neutral")])
def test_retail_signal(now, tone):
    weeks = pd.date_range("2026-09-25", periods=4, freq="W-FRI")
    retail = pd.DataFrame(
        {
            "week_ending": weeks,
            "region": "NATIONAL",
            "feature_rate": 0.9,
            "activity_index": float(now),
            "activity_index_last_year": 100.0,
        }
    )
    r = hm.retail_vs_year_ago(retail)
    assert r is not None
    sig = next(s for s in hm.signals(_market(), retail=r) if s.name == "Retail features")
    assert sig.tone == tone


def test_wasde_accuracy_by_horizon():
    s = "barrows_gilts_usd_cwt_live"
    hist = pd.DataFrame(
        [
            # July 2026 report: forecasts Q3 2026 (its own quarter) at 70 and Q4 (1 ahead) at 60
            {"report": "July 2026", "year": 2026, "quarter": 3, "series": s, "value": 70.0,
             "projected": True},
            {"report": "July 2026", "year": 2026, "quarter": 4, "series": s, "value": 60.0,
             "projected": True},
            # October 2026 report: Q3 actual 67.86
            {"report": "October 2026", "year": 2026, "quarter": 3, "series": s, "value": 67.86,
             "projected": False},
        ]
    )  # fmt: skip
    acc = hm.wasde_accuracy(hist).set_index("horizon")
    assert list(acc.index) == [0]  # Q4 has no actual yet
    assert acc.loc[0, "bias"] == pytest.approx(70 - 67.86)
    assert acc.loc[0, "mae"] == pytest.approx(2.14)
