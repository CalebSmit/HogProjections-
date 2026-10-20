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


def _market(days: int = 800, weight_shift: float = 0.0, head_shift: float = 0.0,
            cut_trend: float = 0.0) -> pd.DataFrame:  # fmt: skip
    """Synthetic daily market: flat prices; the last 28 days can differ from a year earlier."""
    dates = pd.bdate_range("2024-01-01", periods=days)
    recent = dates > dates[-1] - pd.Timedelta(days=28)
    weight = np.where(recent, 215 + weight_shift, 215.0)
    head = np.where(recent, 250_000 * (1 + head_shift), 250_000.0)
    cutout = 90 + np.where(dates > dates[-1] - pd.Timedelta(days=14), cut_trend, 0.0)
    df = pd.DataFrame({"date": dates, "index": 80.0, "cutout": cutout, "head": head,
                       "weight_lb": weight})  # fmt: skip
    df["spread"] = df["cutout"] - df["index"]
    df["spread_per_head"] = df["spread"] * df["weight_lb"] / 100
    return df


def test_daily_spread_arithmetic():
    hg = pd.DataFrame(
        {"slaughter_date": pd.to_datetime(["2026-10-15"]), "purchase_type": [hm.ALL_TYPES],
         "head_count": [200_000.0], "avg_weight_lb_carcass": [220.0]}
    )  # fmt: skip
    idx = pd.DataFrame({"index_date": pd.to_datetime(["2026-10-15"]),
                        "lean_hog_index_usd_per_cwt_carcass": [75.0]})  # fmt: skip
    cut = pd.DataFrame({"date": pd.to_datetime(["2026-10-15"]), "carcass": [85.0],
                        "belly": [90.0], "loin": [80.0], "ham": [70.0]})  # fmt: skip
    d = hm.daily(hg, idx, cut)
    assert d["spread"].iloc[0] == pytest.approx(10.0)
    assert d["spread_per_head"].iloc[0] == pytest.approx(22.0)  # $10/cwt × 220 lb


def test_weekly_is_head_weighted():
    d = pd.DataFrame({"date": pd.to_datetime(["2026-10-12", "2026-10-13"]), "index": [70.0, 80.0],
                      "cutout": [80.0, 90.0], "spread": [10.0, 10.0],
                      "spread_per_head": [21.0, 22.0], "head": [100.0, 300.0],
                      "weight_lb": [200.0, 220.0]})  # fmt: skip
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
