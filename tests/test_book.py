"""The hedging book: locked vs open margin, exposure, what-if and the user's hedge rule."""

from datetime import date

import pandas as pd
import pytest

from hogproj.book import Hedge, business_days_since, by_contract, hedge_rule, positions, what_if
from hogproj.crush import CrushInputs, margin_usd

C = CrushInputs(pig_usd_per_head=30.0, corn_usd_per_bu=4.25, sbm_usd_per_ton=320.0)
APR = (2027, 4)
DEC = (2026, 12)


def _on_feed() -> pd.DataFrame:
    # Sold Feb 21 -> Apr contract; sold Nov 30 -> Dec contract.
    return pd.DataFrame(
        {"placed": pd.to_datetime(["2026-09-14", "2026-06-23"]),
         "sold": pd.to_datetime(["2027-02-21", "2026-11-30"]),
         "pig_usd": [30.0, 30.0]}
    )  # fmt: skip


FUT = {APR: 80.0, DEC: 70.0}


def test_unhedged_equals_open_margin():
    pos = positions(_on_feed(), C, FUT, {}, head_per_week=1000)
    apr = pos[pos["contract"] == "2027-04"].iloc[0]
    assert apr["margin_usd"] == pytest.approx(margin_usd(C, 80.0))
    assert apr["margin_usd"] == pytest.approx(apr["unhedged_margin_usd"])
    assert apr["exposure_usd_per_cwt"] == pytest.approx(C.carcass_cwt)


def test_fully_hedged_locks_the_hedge_price():
    pos = positions(_on_feed(), C, FUT, {APR: Hedge(share=1.0, price=90.0)}, 1000)
    apr = pos[pos["contract"] == "2027-04"].iloc[0]
    assert apr["margin_usd"] == pytest.approx(margin_usd(C, 90.0))
    assert apr["exposure_usd_per_cwt"] == 0


def test_partial_hedge_is_linear():
    full = positions(_on_feed(), C, FUT, {APR: Hedge(share=1.0, price=90.0)}, 1000)
    half = positions(_on_feed(), C, FUT, {APR: Hedge(share=0.5, price=90.0)}, 1000)
    none = positions(_on_feed(), C, FUT, {}, 1000)
    f, h, n = (p[p["contract"] == "2027-04"]["margin_usd"].iloc[0] for p in (full, half, none))
    assert h == pytest.approx((f + n) / 2)


def test_corn_hedge_changes_cost_only():
    base = positions(_on_feed(), C, FUT, {}, 1000)
    hedged = positions(_on_feed(), C, FUT, {}, 1000, corn=Hedge(share=1.0, price=3.25))
    saved = C.corn_lb * (4.25 - 3.25) / 56  # $ per pig
    diff = hedged["margin_usd"].to_numpy() - base["margin_usd"].to_numpy()
    assert diff == pytest.approx([saved, saved])


def test_by_contract_totals_and_order():
    pos = positions(_on_feed(), C, FUT, {APR: Hedge(share=0.25, price=85.0)}, 1000)
    s = by_contract(pos)
    assert list(s["contract"]) == ["2026-12", "2027-04"]
    assert s["head"].sum() == 2000
    assert s["margin_usd"].sum() == pytest.approx(1000 * pos["margin_usd"].sum())
    assert s.set_index("contract").loc["2027-04", "hedged_share"] == 0.25


def test_what_if_hedges_reduce_sensitivity():
    pos = positions(_on_feed(), C, FUT, {APR: Hedge(share=1.0, price=80.0),
                                         DEC: Hedge(share=1.0, price=70.0)}, 1000)  # fmt: skip
    w = what_if(pos, [-10, 0, 10]).set_index("shift")
    # Fully hedged at market: the book doesn't move; unhedged moves 2000 head × cwt × $10.
    assert w.loc[-10, "with_hedges_usd"] == pytest.approx(w.loc[10, "with_hedges_usd"])
    swing = w.loc[10, "without_hedges_usd"] - w.loc[-10, "without_hedges_usd"]
    assert swing == pytest.approx(2000 * C.carcass_cwt * 20)
    assert w.loc[0, "with_hedges_usd"] == pytest.approx(w.loc[0, "without_hedges_usd"])


def test_rows_without_a_contract_price_are_skipped():
    pos = positions(_on_feed(), C, {APR: 80.0}, {}, 1000)
    assert list(pos["contract"]) == ["2027-04"]


@pytest.mark.parametrize(
    ("rank", "current", "tone"),
    [(80, 0.0, "caution"), (80, 0.5, "good"), (40, 0.0, "neutral"), (float("nan"), 0, "neutral")],
)
def test_hedge_rule(rank, current, tone):
    got, sentence = hedge_rule(rank, trigger=75, target=0.5, current=current)
    assert got == tone
    assert sentence


def test_business_days_since():
    assert business_days_since(date(2026, 10, 16), date(2026, 10, 20)) == 2  # Fri -> Tue


def test_positions_use_each_rows_own_corn():
    on = _on_feed().assign(corn_usd_per_bu=[5.25, 4.25])
    pos = positions(on, C, FUT, {}, 1000)
    apr = pos[pos["contract"] == "2027-04"].iloc[0]
    assert apr["margin_usd"] == pytest.approx(margin_usd(C, 80.0, corn=5.25))


def test_hedge_rule_modes():
    from hogproj.book import HedgeRule

    by_margin = HedgeRule(mode="margin", target=0.5, min_margin=10)
    tone, text = hedge_rule(20, 75, 0.5, 0.0, by_margin, margin=12.0)
    assert tone == "caution" and "$10.00 trigger" in text
    assert hedge_rule(99, 75, 0.5, 0.0, by_margin, margin=8.0)[0] == "neutral"  # rank ignored
    assert hedge_rule(20, 75, 0.5, 0.6, by_margin, margin=12.0)[0] == "good"
    off = HedgeRule(mode="off")
    assert hedge_rule(99, 75, 0.5, 0.0, off, margin=50.0)[0] == "neutral"
    assert off.label() == "No hedge rule"
    assert HedgeRule().label() == "Hedge rule · 75th pct → 50%"
