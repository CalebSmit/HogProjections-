import json

import httpx
import pandas as pd
import pytest

from hogproj import supply
from hogproj.config import ROOT
from hogproj.data import nass

FIXTURE = ROOT / "tests" / "fixtures" / "nass_hogs_2025_2026.json"


def data() -> pd.DataFrame:
    return nass.parse(json.loads(FIXTURE.read_text()))


def test_parse_maps_periods_and_intentions():
    df = data()
    sep = pd.Timestamp("2026-09-01")
    all_hogs = df[(df.series == "all_hogs") & (df.period_start == sep)]
    assert all_hogs["value"].iloc[0] == 74_301_700  # Sep 1, 2026 report
    # Dec-Feb 2026 production starts in December 2025
    assert ((df.series == "pig_crop") & (df.period_start == pd.Timestamp("2025-12-01"))).any()
    intents = df[(df.series == "sows_farrowed") & df.kind.str.startswith("intentions")]
    assert pd.Timestamp("2026-09-01") in set(intents.period_start)


def test_outlook_compares_like_with_like():
    df = data()
    o = supply.outlook(df).set_index("label")
    row = o.loc["180 lb and up"]
    assert row["pct"] == pytest.approx(row["value"] / row["year_ago"] - 1)
    assert row["start"] == pd.Timestamp("2026-09-01")
    # weight classes in marketing order, then the pig crop, then intentions further out
    o2 = supply.outlook(df)
    classes = list(o2["start"].iloc[:4])
    assert classes == sorted(classes)
    assert o2["basis"].iloc[4] == "Pigs born last quarter"
    assert (o2["start"].iloc[5:] > o2["start"].iloc[4]).all()


def test_next_six_months_is_sum_of_weight_classes():
    df = data()
    s = supply.next_six_months(df)
    ref = supply.latest_report(df)
    market = df[(df.series == "market") & (df.period_start == ref)]["value"].iloc[0]
    assert s["value"] == pytest.approx(market, rel=0.001)  # classes add up to market hogs


def test_load_without_key_uses_sample(tmp_path, monkeypatch):
    monkeypatch.setattr(nass, "CACHE_DIR", tmp_path)
    df, source, note = nass.load("", offline=False)
    assert source == "sample"
    assert "NASS_API_KEY" in note
    assert supply.latest_report(df) >= pd.Timestamp("2026-09-01")


def test_fetch_scrubs_key_from_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": ["unauthorized"]}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPError) as e:
        nass.fetch("SECRET-KEY-123", 2020, client=client)
    assert "SECRET-KEY-123" not in str(e.value)


def test_lowest_since():
    df = pd.DataFrame(
        {
            "series": "breeding",
            "kind": "actual",
            "period_start": pd.to_datetime(
                ["2012-09-01", "2013-09-01", "2014-09-01", "2015-09-01"]
            ),
            "value": [5.0, 6.0, 7.0, 5.5],
        }
    )
    assert supply.lowest_since(df, "breeding") == 2012
