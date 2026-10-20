"""The book: pigs on feed, the hedges against them, and what's locked versus still open.

For each placement still on feed (from `crush.placements`):

    hog price   = hedged% × hedge price + (1 − hedged%) × today's contract price
    corn, SBM   = hedged% × hedge price + (1 − hedged%) × today's price
    margin/pig  = carcass cwt × (hog price + basis) − cost(pig, corn, SBM)
    exposure    = (1 − hedged%) × carcass cwt   ($ per pig for each $1/cwt the contract moves)

Hedges are entered per lean hog contract (the workbook's "% hedged / hedged price" rows) and
once each for corn and soybean meal. Pure: no Streamlit.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Annotated

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from hogproj.crush import Contract, CrushInputs, contract_for, contract_label, cost_usd
from hogproj.text import ordinal


class Hedge(BaseModel):
    share: Annotated[float, Field(ge=0, le=1)] = 0.0  # 0-1 of the position
    price: float = 0.0  # $/cwt for hogs, $/bu corn, $/ton SBM


def positions(
    on_feed: pd.DataFrame,
    c: CrushInputs,
    futures: Mapping[Contract, float],
    hog_hedges: Mapping[Contract, Hedge],
    head_per_week: float,
    corn: Hedge | None = None,
    sbm: Hedge | None = None,
) -> pd.DataFrame:
    """One row per placement on feed with its hedged and unhedged margin."""
    corn, sbm = corn or Hedge(), sbm or Hedge()
    sbm_px = sbm.share * sbm.price + (1 - sbm.share) * c.sbm_usd_per_ton
    c_hedged = c.model_copy(update={"sbm_usd_per_ton": sbm_px})
    rows = []
    for r in on_feed.to_dict("records"):
        k = contract_for(pd.Timestamp(r["sold"]).date())
        if k not in futures:
            continue
        h = hog_hedges.get(k, Hedge())
        mkt = float(futures[k])
        hog = h.share * h.price + (1 - h.share) * mkt
        pig = float(r["pig_usd"]) - c.adder_usd_per_head
        corn_mkt = float(r.get("corn_usd_per_bu", c.corn_usd_per_bu))  # the row's own corn
        corn_px = corn.share * corn.price + (1 - corn.share) * corn_mkt
        margin = c.carcass_cwt * (hog + c.basis_usd_per_cwt) - cost_usd(c_hedged, pig, corn_px)
        open_margin = c.carcass_cwt * (mkt + c.basis_usd_per_cwt) - cost_usd(c, pig, corn_mkt)
        rows.append(
            {"placed": r["placed"], "sold": r["sold"], "contract": f"{k[0]}-{k[1]:02d}",
             "label": contract_label(k), "head": head_per_week, "market_usd_per_cwt": mkt,
             "hedged_share": h.share, "hedge_usd_per_cwt": h.price if h.share else np.nan,
             "margin_usd": margin, "unhedged_margin_usd": open_margin,
             "exposure_usd_per_cwt": (1 - h.share) * c.carcass_cwt, "cwt": c.carcass_cwt}
        )  # fmt: skip
    return pd.DataFrame(rows)


def by_contract(pos: pd.DataFrame) -> pd.DataFrame:
    """Head-weighted summary per lean hog contract, in contract order."""
    if pos.empty:
        return pd.DataFrame()
    out = []
    for key, g in pos.groupby("contract", sort=True):
        head = g["head"].to_numpy(dtype=float)

        def total(col: str, g: pd.DataFrame = g, head: np.ndarray = head) -> float:
            return float((head * g[col].to_numpy(dtype=float)).sum())

        first = g.iloc[0]
        out.append(
            {"contract": key, "label": first["label"], "weeks": len(g), "head": float(head.sum()),
             "market_usd_per_cwt": float(first["market_usd_per_cwt"]),
             "hedged_share": float(first["hedged_share"]),
             "hedge_usd_per_cwt": float(first["hedge_usd_per_cwt"]),
             "margin_usd_per_head": total("margin_usd") / head.sum(),
             "margin_usd": total("margin_usd"),
             "unhedged_margin_usd": total("unhedged_margin_usd"),
             "exposure_usd": total("exposure_usd_per_cwt")}
        )  # fmt: skip
    return pd.DataFrame(out)


def what_if(pos: pd.DataFrame, shifts: Sequence[float]) -> pd.DataFrame:
    """Book total if every contract moves by `shift` $/cwt, with and without the hedges."""
    head = pos["head"].to_numpy(dtype=float)
    m = pos["margin_usd"].to_numpy(dtype=float)
    m0 = pos["unhedged_margin_usd"].to_numpy(dtype=float)
    expo = pos["exposure_usd_per_cwt"].to_numpy(dtype=float)
    cwt = pos["cwt"].to_numpy(dtype=float)
    return pd.DataFrame(
        {"shift": list(shifts),
         "with_hedges_usd": [float((head * (m + expo * s)).sum()) for s in shifts],
         "without_hedges_usd": [float((head * (m0 + cwt * s)).sum()) for s in shifts]}
    )  # fmt: skip


RULE_MODES = {"rank": "Rank vs history", "margin": "Margin per pig", "off": "No rule"}


@dataclass
class HedgeRule:
    """The user's own hedge rule (never advice). `mode` "rank": hedge `target` once a margin
    ranks at or above the `trigger` percentile of placements since 2020; "margin": once it is at
    least `min_margin` $/pig; "off": no rule."""

    mode: str = "rank"
    trigger: float = 75.0
    target: float = 0.5
    min_margin: float = 10.0

    def label(self) -> str:
        if self.mode == "off":
            return "No hedge rule"
        when = (f"{ordinal(self.trigger)} pct" if self.mode == "rank"
                else f"${self.min_margin:,.0f}/pig")  # fmt: skip
        return f"Hedge rule · {when} → {self.target:.0%}"

    def describe(self) -> str:
        if self.mode == "off":
            return "no hedge rule set"
        if self.mode == "margin":
            return (
                f"hedge {self.target:.0%} once the margin is at least ${self.min_margin:,.2f} a pig"
            )
        return f"hedge {self.target:.0%} at or above the {ordinal(self.trigger)} percentile"


def hedge_rule(rank: float, trigger: float, target: float, current: float,
               rule: HedgeRule | None = None, margin: float = float("nan")
               ) -> tuple[str, str]:  # fmt: skip
    """Apply the rule to one contract. Returns (tone, sentence): "caution" = rule says hedge,
    "good" = rule met, "neutral" = wait (or no rule)."""
    rule = rule or HedgeRule("rank", trigger, target)
    if rule.mode == "off":
        return "neutral", "No hedge rule set (choose one on Hedging)."
    if rule.mode == "margin":
        if np.isnan(margin):
            return "neutral", "No margin to test."
        where = f"Margin ${margin:,.2f} a pig"
        met = margin >= rule.min_margin
        trig = f"your ${rule.min_margin:,.2f} trigger"
    else:
        if np.isnan(rank):
            return "neutral", "Not enough history to rank this margin."
        where = "Ranks at the bottom of history" if rank < 1 else f"Ranks {ordinal(rank)}"
        met = rank >= rule.trigger
        trig = f"your {ordinal(rule.trigger)} trigger"
    if met:
        if current + 1e-9 >= rule.target:
            return "good", f"{where}: your rule's {rule.target:.0%} is in place."
        return "caution", (f"{where}, above {trig}: rule says hedge {rule.target:.0%} "
                           f"(now {current:.0%}).")  # fmt: skip
    return "neutral", f"{where}, below {trig}: rule says wait."


def business_days_since(day: date, today: date) -> int:
    return int(np.busday_count(day, today))
