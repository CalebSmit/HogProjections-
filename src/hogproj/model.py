"""Wean-to-finish group projection: costs, revenue, breakeven. Pure functions, no I/O."""

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from hogproj.inputs import (
    CORN_LB_PER_BU,
    LB_PER_TON,
    BarnCostMode,
    LaborCostMode,
    Projection,
)

# CME Lean Hog (HE) listed contract months. A sale month is priced off the first listed
# contract month on or after it (Jan->Feb, Mar->Apr, Sep->Oct, Nov->Dec).
LEAN_HOG_CONTRACT_MONTHS = (2, 4, 5, 6, 7, 8, 10, 12)


def lean_hog_contract_for(d: date) -> str:
    """Contract code 'YYYY-MM' used to price hogs sold on date d."""
    month = next(m for m in LEAN_HOG_CONTRACT_MONTHS if m >= d.month)
    return f"{d.year}-{month:02d}"


def corn_cash_usd_bu(p: Projection) -> float:
    return p.corn_futures_usd_bu + p.location.corn_basis_usd_bu


def sbm_cash_usd_ton(p: Projection) -> float:
    return p.sbm_futures_usd_ton + p.location.sbm_basis_usd_ton


@dataclass(frozen=True)
class Result:
    summary: dict[str, float]
    costs: pd.DataFrame  # one row per cost line
    feed: pd.DataFrame  # one row per phase
    marketing: pd.DataFrame  # one row per marketing cut


def head_sold(p: Projection) -> float:
    return p.head_placed * (1 - p.mortality_pct / 100)


def feed_table(p: Projection) -> pd.DataFrame:
    deads = p.head_placed - head_sold(p)
    pigs_fed = head_sold(p) + deads * p.dead_feed_share  # full-feed-budget equivalents
    corn_usd_bu = corn_cash_usd_bu(p)
    sbm_usd_ton = sbm_cash_usd_ton(p)
    rows = []
    for ph in p.feed_phases:
        tons = ph.feed_lb_per_pig * pigs_fed / LB_PER_TON
        corn_bu = tons * LB_PER_TON * ph.corn_pct / 100 / CORN_LB_PER_BU
        sbm_tons = tons * ph.sbm_pct / 100
        ddgs_tons = tons * ph.ddgs_pct / 100
        other_tons = tons * ph.other_pct / 100
        cost = (
            corn_bu * corn_usd_bu
            + sbm_tons * sbm_usd_ton
            + ddgs_tons * p.location.ddgs_usd_ton
            + other_tons * ph.other_usd_ton
            + tons * p.feed_mill_usd_ton
        )
        rows.append(
            {
                "phase": ph.name,
                "feed_lb_per_pig": ph.feed_lb_per_pig,
                "tons": tons,
                "corn_bu": corn_bu,
                "sbm_tons": sbm_tons,
                "ddgs_tons": ddgs_tons,
                "other_tons": other_tons,
                "cost_usd": cost,
                "cost_usd_per_ton": cost / tons if tons else 0.0,
            }
        )
    return pd.DataFrame(rows)


def marketing_table(p: Projection) -> pd.DataFrame:
    sold = head_sold(p)
    rows = []
    for cut in p.marketing:
        sale_date = p.placement_date + timedelta(days=cut.days_after_placement)
        contract = lean_hog_contract_for(sale_date)
        if contract not in p.lean_hog_futures_cwt:
            raise KeyError(f"no lean hog futures price for contract {contract}")
        futures = p.lean_hog_futures_cwt[contract]
        basis = p.hog_basis_cwt_by_month.get(sale_date.month, 0.0)
        price = futures + basis + p.carcass_premium_cwt
        head = sold * cut.pct_of_marketed / 100
        carcass_lb = cut.live_weight_lb * p.carcass_yield_pct / 100
        rows.append(
            {
                "sale_date": sale_date,
                "contract": contract,
                "head": head,
                "live_weight_lb": cut.live_weight_lb,
                "carcass_weight_lb": carcass_lb,
                "futures_cwt": futures,
                "basis_cwt": basis,
                "premium_cwt": p.carcass_premium_cwt,
                "price_cwt_carcass": price,
                "revenue_usd": head * carcass_lb / 100 * price,
            }
        )
    return pd.DataFrame(rows)


def project(p: Projection) -> Result:
    feed = feed_table(p)
    mkt = marketing_table(p)
    sold = head_sold(p)
    placed = p.head_placed

    avg_days = sum(c.days_after_placement * c.pct_of_marketed / 100 for c in p.marketing)
    gross = float(mkt["revenue_usd"].to_numpy().sum())
    carcass_cwt = float((mkt["head"] * mkt["carcass_weight_lb"]).to_numpy().sum()) / 100
    live_cwt = float((mkt["head"] * mkt["live_weight_lb"]).to_numpy().sum()) / 100

    pig_cost = placed * (p.wean_pig_usd_hd + p.wean_pig_freight_usd_hd)
    feed_cost = float(feed["cost_usd"].to_numpy().sum())
    if p.barn_mode is BarnCostMode.PER_SPACE_YEAR:
        barn = placed * p.location.barn_rent_usd_space_yr * p.barn_days_occupied / 365
    else:
        barn = placed * p.barn_usd_pig_placed
    if p.labor_mode is LaborCostMode.HOURLY:
        labor = placed * p.labor_hr_per_pig * p.location.labor_wage_usd_hr
    else:
        labor = placed * p.labor_usd_pig_placed
    interest = (
        p.interest_rate_pct / 100 * avg_days / 365 * (pig_cost + 0.5 * feed_cost)
    )  # pig capital outstanding the whole period, feed on average half of it
    checkoff = gross * p.checkoff_pct / 100

    lines = {
        "Weaned pigs": pig_cost,
        "Feed": feed_cost,
        "Barn / facilities": barn,
        "Labor": labor,
        "Vet / med": placed * p.vet_med_usd_hd,
        "Utilities": placed * p.utilities_usd_hd,
        "Trucking to market": sold * p.trucking_usd_hd_sold,
        "Insurance / misc": placed * p.insurance_misc_usd_hd,
        "Interest": interest,
        "Checkoff": checkoff,
    }
    total = sum(lines.values())
    costs = pd.DataFrame(
        {
            "line": list(lines),
            "total_usd": list(lines.values()),
        }
    )
    costs["usd_per_head_placed"] = costs["total_usd"] / placed
    costs["usd_per_head_sold"] = costs["total_usd"] / sold
    costs["usd_per_cwt_carcass"] = costs["total_usd"] / carcass_cwt
    costs["pct_of_total"] = costs["total_usd"] / total * 100

    # Breakeven: price where revenue net of checkoff covers every other cost.
    costs_ex_checkoff = total - checkoff
    breakeven_carcass = costs_ex_checkoff / (carcass_cwt * (1 - p.checkoff_pct / 100))
    net = gross - total
    total_feed_lb = float(feed["tons"].to_numpy().sum()) * LB_PER_TON
    lb_gain = live_cwt * 100 - placed * p.wean_weight_lb

    summary = {
        "head_placed": placed,
        "head_sold": sold,
        "avg_days_on_feed": avg_days,
        "corn_cash_usd_bu": corn_cash_usd_bu(p),
        "sbm_cash_usd_ton": sbm_cash_usd_ton(p),
        "ddgs_usd_ton": p.location.ddgs_usd_ton,
        "wean_pig_usd_hd": p.wean_pig_usd_hd,
        "total_cost_usd": total,
        "gross_revenue_usd": gross,
        "net_usd": net,
        "net_usd_per_head_sold": net / sold,
        "cost_usd_per_head_sold": total / sold,
        "revenue_usd_per_head_sold": gross / sold,
        "cost_usd_per_cwt_carcass": total / carcass_cwt,
        "avg_price_cwt_carcass": gross / carcass_cwt,
        "breakeven_cwt_carcass": breakeven_carcass,
        "breakeven_cwt_live": breakeven_carcass * p.carcass_yield_pct / 100,
        "feed_cost_usd_per_head_sold": feed_cost / sold,
        "feed_conversion": total_feed_lb / lb_gain if lb_gain > 0 else 0.0,
        "carcass_cwt_sold": carcass_cwt,
    }
    return Result(summary=summary, costs=costs, feed=feed, marketing=mkt)


def sensitivity(p: Projection, corn_steps: list[float], hog_steps: list[float]) -> pd.DataFrame:
    """Net $/head sold for corn futures changes (rows, $/bu) x hog price changes (cols, $/cwt)."""
    out = {}
    for dh in hog_steps:
        futures = {k: v + dh for k, v in p.lean_hog_futures_cwt.items()}
        col = []
        for dc in corn_steps:
            q = p.model_copy(
                update={
                    "corn_futures_usd_bu": p.corn_futures_usd_bu + dc,
                    "lean_hog_futures_cwt": futures,
                }
            )
            col.append(project(q).summary["net_usd_per_head_sold"])
        out[f"{dh:+.0f}"] = col
    return pd.DataFrame(out, index=[f"{dc:+.2f}" for dc in corn_steps])
