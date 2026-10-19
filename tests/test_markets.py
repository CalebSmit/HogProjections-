import json
from datetime import date

import httpx
import pandas as pd
import pytest

from hogproj.config import ROOT
from hogproj.data import ams
from hogproj.markets import lean_hog_index, seasonal_factors

FIXTURE = ROOT / "tests" / "fixtures" / "lm_hg201_barrows_gilts.json"


def fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text())


def test_parse_hg201_keeps_index_rows_and_numbers():
    df = ams.parse_hg201(fixture_payload())
    assert set(df["purchase_type"]) == set(ams.KEEP_PURCHASE_TYPES)
    row = df[
        (df["slaughter_date"] == "2026-10-15") & (df["purchase_type"] == "Prod. Sold Negotiated")
    ].iloc[0]
    assert row["head_count"] == 3613  # "3,613" in the JSON
    assert row["avg_net_price_cwt_carcass"] == pytest.approx(72.15)
    assert row["avg_weight_lb_carcass"] == pytest.approx(217.70)


def test_index_matches_cme_published_value():
    # CME Lean Hog Index for Oct 12, 2026 was 75.75 (slaughter days Oct 12 + Oct 13).
    idx = lean_hog_index(ams.parse_hg201(fixture_payload())).set_index("index_date")
    assert idx.loc[pd.Timestamp("2026-10-12"), "lean_hog_index_usd_per_cwt_carcass"] == (
        pytest.approx(75.75, abs=0.005)
    )


def test_index_is_weighted_by_carcass_pounds():
    rows = []
    for day, (h1, p1), (h2, p2) in [
        ("2026-01-05", (100, 80.0), (300, 70.0)),
        ("2026-01-06", (200, 90.0), (0, 0.0)),
    ]:
        for pt, h, p in [
            ("Prod. Sold Negotiated", h1, p1),
            ("Prod. Sold Swine or Pork Market Formula", h2, p2),
            ("Prod. Sold (All Purchase Types)", 9999, 1.0),  # must be ignored
        ]:
            rows.append(
                {
                    "slaughter_date": pd.Timestamp(day),
                    "purchase_type": pt,
                    "head_count": h,
                    "avg_net_price_cwt_carcass": p,
                    "avg_weight_lb_carcass": 200.0,
                }
            )
    idx = lean_hog_index(pd.DataFrame(rows))
    assert len(idx) == 1
    # equal carcass weights -> head-weighted: (100*80 + 300*70 + 200*90) / 600
    assert idx["lean_hog_index_usd_per_cwt_carcass"].iloc[0] == pytest.approx(47000 / 600)
    assert idx["index_date"].iloc[0] == pd.Timestamp("2026-01-05")


def test_fetch_builds_query_and_parses():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=fixture_payload())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    df = ams.fetch_hg201(date(2026, 10, 12), date(2026, 10, 16), client=client)
    assert "/2511/Barrows/Gilts" in seen["url"]
    assert "10%2F12%2F2026%3A10%2F16%2F2026" in seen["url"]
    assert not df.empty


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ams, "CACHE_DIR", tmp_path)
    return tmp_path


def test_offline_uses_bundled_sample(tmp_cache):
    df, source, note = ams.load_hg201(offline=True)
    assert source == "sample"
    assert "sample" in note
    assert len(lean_hog_index(df)) > 500  # ~3 years of trading days


def test_network_failure_falls_back_to_cache_then_sample(tmp_cache, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(ams, "fetch_hg201", boom)
    _, source, note = ams.load_hg201(offline=False)
    assert source == "sample"
    assert "Couldn't reach USDA" in note

    ams.parse_hg201(fixture_payload()).to_csv(tmp_cache / ams.HG201_FILE, index=False)
    df, source, note = ams.load_hg201(offline=False)
    assert source == "cache"
    assert "Oct 16, 2026" in note
    assert df["report_date"].dtype.kind == "M"


def test_live_success_writes_cache(tmp_cache, monkeypatch):
    monkeypatch.setattr(ams, "fetch_hg201", lambda *a, **k: ams.parse_hg201(fixture_payload()))
    _, source, _ = ams.load_hg201(offline=False)
    assert source == "live"
    assert (tmp_cache / ams.HG201_FILE).exists()


def test_seasonal_factors_average_to_one_and_peak_in_summer(tmp_cache):
    df, _, _ = ams.load_hg201(offline=True)
    f = seasonal_factors(lean_hog_index(df))
    assert len(f) == 12
    assert f["factor"].mean() == pytest.approx(1, abs=0.01)
    # domain.md §4: prices peak May-Aug and bottom in Nov
    assert f.set_index("month")["factor"].idxmax() in {5, 6, 7, 8}
    assert f.set_index("month")["factor"].idxmin() in {10, 11, 12, 1}


def test_seasonal_factors_ignore_partial_years():
    days = pd.date_range("2024-01-01", "2025-03-31", freq="D")
    idx = pd.DataFrame(
        {"index_date": days, "lean_hog_index_usd_per_cwt_carcass": [100.0] * len(days)}
    )
    idx.loc[idx["index_date"].dt.year == 2025, "lean_hog_index_usd_per_cwt_carcass"] = 500.0
    f = seasonal_factors(idx)
    assert f["years"].max() == 1
    assert f["factor"].to_numpy() == pytest.approx(1.0)
