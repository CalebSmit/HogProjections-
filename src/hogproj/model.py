"""Wean-to-finish group projection: costs, revenue, breakeven. Pure functions, no I/O."""

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

from hogproj.basis import basis_period, lean_hog_contract_for
from hogproj.inputs import (
    CORN_LB_PER_BU,
    LB_PER_TON,
    BarnCostMode,
    InterestMode,
    LaborCostMode,
    MortalityMode,
    Projection,
)


def _blend(open_price: float, hedged_price: float, hedged_pct: float) -> float:
    """Price paid when hedged_pct of the need is locked at hedged_price."""
    h = hedged_pct / 100
    return open_price * (1 - h) + hedged_price * h


def corn_cash_usd_bu(p: Projection) -> float:
    open_price = p.corn_futures_usd_bu + p.location.corn_basis_usd_bu + p.corn_carry_usd_bu
    return _blend(open_price, p.corn_hedged_usd_bu, p.corn_hedged_pct)


def sbm_cash_usd_ton(p: Projection) -> float:
    open_price = p.sbm_futures_usd_ton + p.location.sbm_basis_usd_ton
    return _blend(open_price, p.sbm_hedged_usd_ton, p.sbm_hedged_pct)


@dataclass(frozen=True)
class Result:
    summary: dict[str, float]
    costs: pd.DataFrame  # one row per cost line
    feed: pd.DataFrame  # one row per phase
    marketing: pd.DataFrame  # one row per marketing cut


def head_sold(p: Projection) -> float:
    if p.mortality_mode is MortalityMode.USD_PER_PIG:
        return float(p.head_placed)
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
        period = basis_period(sale_date)
        if cut.pct_of_marketed == 0:  # nothing sold: no price needed
            futures = basis = premium = 0.0
        else:
            if contract not in p.lean_hog_futures_cwt:
                raise KeyError(f"no lean hog futures price for contract {contract}")
            futures = _blend(p.lean_hog_futures_cwt[contract], p.hog_hedged_cwt, p.hog_hedged_pct)
            basis = p.hog_basis_cwt_by_period.get(period, 0.0)
            premium = p.carcass_premium_cwt
        price = futures + basis + premium
        head = sold * cut.pct_of_marketed / 100
        carcass_lb = cut.live_weight_lb * p.carcass_yield_pct / 100
        rows.append(
            {
                "sale_date": sale_date,
                "contract": contract,
                "basis_period": period,
                "head": head,
                "live_weight_lb": cut.live_weight_lb,
                "carcass_weight_lb": carcass_lb,
                "futures_cwt": futures,
                "basis_cwt": basis,
                "premium_cwt": premium,
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
    if p.interest_mode is InterestMode.RATE:
        # pig capital is outstanding the whole period, feed on average half of it
        interest = p.interest_rate_pct / 100 * avg_days / 365 * (pig_cost + 0.5 * feed_cost)
    else:
        interest = placed * p.interest_usd_hd
    mortality = (
        placed * p.mortality_cost_usd_hd if p.mortality_mode is MortalityMode.USD_PER_PIG else 0.0
    )
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
        "G&A": placed * p.ga_usd_hd,
        "Mortality ($/pig)": mortality,
        "Other / (premiums)": sold * p.other_usd_hd_sold,
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
    debt_service = sold * (p.principal_usd_hd + p.term_interest_usd_hd)
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
        "feed_conversion": total_feed_lb / lb_gain if lb_gain > 0 else float("nan"),
        "carcass_cwt_sold": carcass_cwt,
        "debt_service_usd": debt_service,
        "net_after_debt_usd": net - debt_service,
        "net_after_debt_usd_per_head_sold": (net - debt_service) / sold,
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
        out[f"{dh:+g}"] = col
    return pd.DataFrame(out, index=[f"{dc:+g}" for dc in corn_steps])


def cash_flow(p: Projection, r: Result) -> pd.DataFrame:
    """Monthly cash out (by cost line) and cash in, reconciling to `project()` totals.

    Timing assumptions:
    - Weaned pigs, freight and vet/med are paid in the placement month (vaccines up front).
    - Feed is spread by daily intake, taken as proportional to live weight x head on feed.
      Weight grows linearly from wean weight to the average sale weight.
    - Barn is spread over placement to last sale plus downtime.
    - Labor, utilities, insurance, G&A and $/pig mortality are spread evenly over feeding.
    - Revenue, trucking, checkoff and other/(premiums) fall on each sale date.
    - Interest is paid at the last sale.
    """
    costs = dict(zip(r.costs["line"], r.costs["total_usd"], strict=True))
    last_sale = max(c.days_after_placement for c in p.marketing)
    feeding = range(last_sale + 1)
    barn_days = range(p.barn_days_occupied)
    avg_wt = sum(c.live_weight_lb * c.pct_of_marketed / 100 for c in p.marketing)
    sold_frac = {c.days_after_placement: 0.0 for c in p.marketing}
    for c in p.marketing:
        sold_frac[c.days_after_placement] += c.pct_of_marketed / 100

    # Head on feed each day: deaths spread evenly to the average sale day, sales leave on
    # their day. Intake weight = head x weight.
    avg_day = sum(c.days_after_placement * c.pct_of_marketed / 100 for c in p.marketing)
    # In $-per-pig mode every pig placed counts as sold, so none die off the feed curve.
    mort = 0.0 if p.mortality_mode is MortalityMode.USD_PER_PIG else p.mortality_pct / 100
    intake: list[float] = []
    sold_so_far = 0.0
    for d in feeding:
        alive = 1 - mort * min(d / avg_day, 1) if avg_day else 1 - mort
        head = max(alive * (1 - sold_so_far), 0.0)
        weight = p.wean_weight_lb + (avg_wt - p.wean_weight_lb) * d / max(avg_day, 1)
        intake.append(head * weight)
        sold_so_far += sold_frac.get(d, 0.0)
    total_intake = sum(intake) or 1.0

    out: dict[str, dict[str, float]] = {}

    def add(day: int, line: str, usd: float) -> None:
        month = (p.placement_date + timedelta(days=day)).strftime("%Y-%m")
        out.setdefault(month, {})
        out[month][line] = out[month].get(line, 0.0) + usd

    for line in ("Weaned pigs", "Vet / med"):
        add(0, line, costs[line])
    for d in feeding:
        add(d, "Feed", costs["Feed"] * intake[d] / total_intake)
        for line in ("Labor", "Utilities", "Insurance / misc", "G&A", "Mortality ($/pig)"):
            add(d, line, costs[line] / len(feeding))
    for d in barn_days:
        add(d, "Barn / facilities", costs["Barn / facilities"] / len(barn_days))
    gross = float(r.marketing["revenue_usd"].to_numpy().sum())
    head_total = float(r.marketing["head"].to_numpy().sum())
    for cut, row in zip(p.marketing, r.marketing.to_dict("records"), strict=True):
        day = cut.days_after_placement
        add(day, "Revenue", float(row["revenue_usd"]))
        if head_total:
            add(day, "Trucking to market", costs["Trucking to market"] * row["head"] / head_total)
        if gross:
            add(day, "Checkoff", costs["Checkoff"] * float(row["revenue_usd"]) / gross)
        if head_total:
            other = costs["Other / (premiums)"] * row["head"] / head_total
            add(day, "Other / (premiums)", other)
    add(last_sale, "Interest", costs["Interest"])

    lines = list(costs)
    rows = []
    for month in sorted(out):
        rec: dict[str, float | str] = {"month": month}
        rec.update({line: out[month].get(line, 0.0) for line in lines})
        rec["cash_out_usd"] = sum(out[month].get(line, 0.0) for line in lines)
        rec["cash_in_usd"] = out[month].get("Revenue", 0.0)
        rec["net_usd"] = rec["cash_in_usd"] - rec["cash_out_usd"]  # type: ignore[operator]
        rows.append(rec)
    df = pd.DataFrame(rows)
    df["cumulative_usd"] = df["net_usd"].cumsum()
    return df
