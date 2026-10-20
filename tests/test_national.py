"""National view: regional prices, purchase mix, state corn, flows, origin, weights, sows."""

import numpy as np
import pandas as pd
import pytest

from hogproj import national as nv


def _prices() -> pd.DataFrame:
    days = pd.bdate_range("2026-10-05", periods=10)
    rows = []
    for i, d in enumerate(days):
        for region, base in (("National", 70.0), ("Iowa/Minnesota", 69.0)):
            rows.append(
                {
                    "date": d,
                    "region": region,
                    "purchase": "Negotiated",
                    "head": 1000.0,
                    "price": base + i,
                }
            )
            rows.append({"date": d, "region": region, "purchase": "Pork market formula",
                         "head": 3000.0, "price": base + 2})  # fmt: skip
    return pd.DataFrame(rows)


def test_regional_latest_is_head_weighted_over_recent_days():
    got = nv.regional_latest(_prices(), days=2).set_index(["region", "purchase"])
    assert got.loc[("National", "Negotiated"), "price"] == pytest.approx(70 + 8.5)
    assert got.loc[("National", "Negotiated"), "head"] == 2000


def test_purchase_mix_shares_sum_to_one():
    mix = nv.purchase_mix(_prices(), "National", days=5).set_index("purchase")
    assert mix["share"].sum() == pytest.approx(1)
    assert mix.loc["Pork market formula", "share"] == pytest.approx(0.75)


def test_regional_weekly_has_a_column_per_region():
    w = nv.regional_weekly(_prices(), "Negotiated")
    assert set(w.columns) == {"National", "Iowa/Minnesota"}
    assert (w["National"] - w["Iowa/Minnesota"]).dropna().round(6).eq(1).all()


def test_state_corn_snapshot_with_year_ago():
    days = pd.date_range("2025-10-01", "2026-10-19", freq="D")
    n = len(days)
    sc = pd.DataFrame({"date": np.tile(days, 2), "state": ["Iowa"] * n + ["Texas"] * n,
                       "cash": [4.0] * n + [5.2] * n, "basis": -0.4})  # fmt: skip
    snap = nv.state_corn_snapshot(sc)
    assert list(snap["state"]) == ["Iowa", "Texas"]  # sorted cheapest first
    assert snap.loc[0, "code"] == "IA" and snap.loc[0, "cash_year_ago"] == 4.0


def test_origin_share_and_weights_and_sows():
    origin = pd.DataFrame({"date": pd.to_datetime(["2026-10-16"] * 2), "state": ["Iowa", "Ohio"],
                           "head": [300.0, 100.0]})  # fmt: skip
    share = nv.origin_share(origin).set_index("state")
    assert share.loc["Iowa", "share"] == pytest.approx(0.75)
    weights = pd.DataFrame({"date": pd.to_datetime(["2025-10-16", "2026-10-16"]),
                            "band_lb": [175, 175], "discount": [-4.0, -2.85]})  # fmt: skip
    sched = nv.weight_schedule(weights).iloc[0]
    assert (sched["now"], sched["year_ago"]) == (-2.85, -4.0)
    sows = pd.DataFrame({"date": pd.to_datetime(["2026-10-16"] * 3),
                         "weight_range": ["300-399 pounds", "400-449 pounds", "450-499 pounds"],
                         "head": [100.0, 100.0, 300.0], "price": [50.0, 60.0, 70.0]})  # fmt: skip
    assert nv.sow_price(sows).iloc[0] == pytest.approx((60 * 100 + 70 * 300) / 400)
