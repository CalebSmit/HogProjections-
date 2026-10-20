"""My Market News (MARS API) parsers, key handling and fallback. Fixture: Oct 2026 responses."""

import json
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import pytest

from hogproj.data import mars

FX = json.loads((Path(__file__).parent / "fixtures" / "mars_2026-10.json").read_text())


def test_feeder_composites_match_the_public_report():
    df = mars.feeder(FX["feeder"]).set_index("week_ending")
    w = df.loc[pd.Timestamp("2026-10-16")]
    assert w["ew_cash_usd"] == pytest.approx(20.08)  # same as the AMS_2810 PDF
    assert w["ew_formula_usd"] == pytest.approx(36.94)
    assert w["ew_cash_head"] == 81366
    assert (w["low_usd"], w["high_usd"]) == (10.0, 33.0)
    assert w["pig40_cash_usd"] == pytest.approx(43.10)


def test_iowa_corn_average_and_basis():
    df = mars.iowa_corn(FX["corn"])
    row = df.iloc[0]
    regions = [4.239, 4.19, 4.2671, 4.2886, 4.24, 4.2757]  # country elevators, Oct 19, 2026
    assert row["corn_cash_iowa"] == pytest.approx(sum(regions) / 6, abs=1e-4)
    assert -0.6 < row["corn_basis_iowa"] < -0.3  # cents converted to $/bu, under Dec futures


def test_iowa_feedstuffs():
    df = mars.iowa_feedstuffs(FX["feedstuffs"]).set_index("date")
    w = df.loc[pd.Timestamp("2026-10-16")]
    assert w["sbm_iowa"] == pytest.approx(383.37)  # same as the AMS_3511 PDF
    assert w["ddgs_iowa"] == pytest.approx(190.50)


def test_key_is_scrubbed_from_errors():
    key = "SECRET-KEY-123"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request, text=f"bad key {key}")

    client = httpx.Client(transport=httpx.MockTransport(handler), auth=(key, ""))
    with pytest.raises(httpx.HTTPError) as e:
        mars.fetch(key, 2810, "Report Details", date(2026, 10, 1), date(2026, 10, 16), client)
    assert key not in str(e.value)


def test_no_key_means_no_history(tmp_path, monkeypatch):
    monkeypatch.setattr(mars, "CACHE_DIR", tmp_path)
    df, source, note = mars.load("feeder", "", offline=False)
    assert df.empty and source == "none" and "USDA_MMN_API_KEY" in note
