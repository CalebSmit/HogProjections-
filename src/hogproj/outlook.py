"""Whole-farm projection: herd flow + costs + hog price path, and what moves the result.

Pure model code that ties `herd`, `finance` and `markets` together for the Overview,
Scenarios and Risk pages.
"""

from datetime import date

import pandas as pd
from pydantic import BaseModel

from hogproj.finance import CostInputs, breakeven, margin_usd_per_head, weekly_returns
from hogproj.herd import HerdInputs, pigs_sold_per_sow_yr, simulate
from hogproj.markets import seasonal_price_path


class Plan(BaseModel):
    """Everything one projection needs. `factors` empty or `seasonal=False` -> flat price."""

    herd: HerdInputs = HerdInputs()
    cost: CostInputs = CostInputs()
    seasonal: bool = True


def synced(plan: Plan) -> Plan:
    """Copy herd facts the cost model needs (weight, yield, productivity) into `cost`."""
    h = plan.herd
    cost = plan.cost.model_copy(
        update={
            "weight_lb_live_market": h.weight_lb_live_market,
            "carcass_yield": h.carcass_yield,
            "pigs_sold_per_sow_yr": pigs_sold_per_sow_yr(h),
        }
    )
    return plan.model_copy(update={"cost": cost})


def project(plan: Plan, factors: pd.DataFrame, start: date) -> pd.DataFrame:
    """Weekly marketings, hog price, revenue, cost and margin from `start`."""
    plan = synced(plan)
    herd = simulate(plan.herd)
    path = (
        seasonal_price_path(start, len(herd), plan.cost.lean_hog_usd_per_cwt_carcass, factors)
        if plan.seasonal
        else None
    )
    r = weekly_returns(herd, plan.cost, path)
    r["date"] = pd.to_datetime(start) + pd.to_timedelta(r["week"] * 7, unit="D")
    return r


def summary(r: pd.DataFrame, weeks: int = 52) -> dict[str, float]:
    """Totals for the first `weeks` of a projection."""
    head = r.iloc[:weeks]
    pigs = float(head["marketed_head"].sum())
    profit = float(head["margin_usd"].sum())
    cwt = float(head["sold_lb_carcass"].sum()) / 100
    revenue = float(head["revenue_usd"].sum())
    return {
        "pigs_sold": pigs,
        "revenue_usd": revenue,
        "cost_usd": float(head["cost_usd"].sum()),
        "profit_usd": profit,
        "profit_usd_per_head": profit / pigs if pigs else 0.0,
        "avg_price_cwt_carcass": revenue / cwt if cwt else 0.0,
    }


def monthly(r: pd.DataFrame, months: int = 12) -> pd.DataFrame:
    """Projection rolled up by calendar month (first `months` months)."""
    m = (
        r.assign(month=r["date"].dt.to_period("M").dt.to_timestamp())
        .groupby("month", as_index=False)
        .agg(
            pigs_sold=("marketed_head", "sum"),
            revenue_usd=("revenue_usd", "sum"),
            cost_usd=("cost_usd", "sum"),
            profit_usd=("margin_usd", "sum"),
            hog_usd_per_cwt_carcass=("hog_usd_per_cwt_carcass", "mean"),
        )
    )
    return pd.DataFrame(m.head(months))


def _with_weaned_change(h: HerdInputs, pigs_per_sow_yr: float) -> HerdInputs:
    """Shift pigs weaned per sow per year by changing born alive per litter."""
    per_litter = pigs_per_sow_yr / (h.litters_per_sow_yr * (1 - h.prewean_mortality))
    return h.model_copy(update={"born_alive_per_litter": h.born_alive_per_litter + per_litter})


def drivers(plan: Plan, factors: pd.DataFrame, start: date) -> pd.DataFrame:
    """Next-52-week profit when each input moves down/up by a typical amount, one at a time.

    Sorted biggest swing first, for a tornado chart.
    """
    base = summary(project(plan, factors, start))["profit_usd"]
    c, h = plan.cost, plan.herd

    def cost(**kw: float) -> Plan:
        return plan.model_copy(update={"cost": c.model_copy(update=kw)})

    def herd(new: HerdInputs) -> Plan:
        return plan.model_copy(update={"herd": new, "cost": c})

    hog = c.lean_hog_usd_per_cwt_carcass
    weight = h.weight_lb_live_market

    def weight_plan(w: float) -> Plan:
        return herd(h.model_copy(update={"weight_lb_live_market": w}))

    # (driver, label when lower, label when higher, plan lower, plan higher)
    cases = [
        ("Hog price", "-$5/cwt", "+$5/cwt",
         cost(lean_hog_usd_per_cwt_carcass=hog - 5), cost(lean_hog_usd_per_cwt_carcass=hog + 5)),
        ("Corn", "-50¢/bu", "+50¢/bu",
         cost(corn_usd_per_bu=max(0.0, c.corn_usd_per_bu - 0.5)),
         cost(corn_usd_per_bu=c.corn_usd_per_bu + 0.5)),
        ("Soybean meal", "-$50/ton", "+$50/ton",
         cost(sbm_usd_per_ton=max(0.0, c.sbm_usd_per_ton - 50)),
         cost(sbm_usd_per_ton=c.sbm_usd_per_ton + 50)),
        ("Pigs weaned / sow / yr", "-1", "+1",
         herd(_with_weaned_change(h, -1)), herd(_with_weaned_change(h, 1))),
        ("Non-feed cost", "-$10/pig", "+$10/pig",
         cost(nonfeed_usd_per_head=max(0.0, c.nonfeed_usd_per_head - 10)),
         cost(nonfeed_usd_per_head=c.nonfeed_usd_per_head + 10)),
        ("Market weight", "-10 lb", "+10 lb", weight_plan(weight - 10), weight_plan(weight + 10)),
    ]  # fmt: skip

    def delta(p: Plan) -> float:
        return summary(project(p, factors, start))["profit_usd"] - base

    out = pd.DataFrame(
        [
            {
                "driver": name,
                "low_label": low_label,
                "high_label": high_label,
                "low_usd": delta(lo),
                "high_usd": delta(hi),
            }
            for name, low_label, high_label, lo, hi in cases
        ]
    )
    out["swing_usd"] = (out["high_usd"] - out["low_usd"]).abs()
    return out.sort_values("swing_usd", ascending=False).reset_index(drop=True)


def headline(plan: Plan) -> dict[str, float]:
    """Per-pig numbers at today's price (no seasonality)."""
    plan = synced(plan)
    be = breakeven(plan.cost)
    return {
        "breakeven_cwt_carcass": be["price_cwt_carcass"],
        "breakeven_cwt_live": be["price_cwt_live"],
        "cost_usd_per_head": be["cost_usd_per_head"],
        "profit_usd_per_head": margin_usd_per_head(plan.cost),
        "gap_cwt_carcass": plan.cost.lean_hog_usd_per_cwt_carcass - be["price_cwt_carcass"],
    }
