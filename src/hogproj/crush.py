"""Weekly crush: margin per pig for a run of weekly placements, side by side. Pure.

Mirrors the owner's "USDA Wean Pig Crush" workbook. Each column is one weekly USDA weaned pig
report: placement = report date + N days, one sale at placement + M days and a set weight.
Every column runs through `model.project()` with the group's settings (costs, ration, hedges,
mortality, debt), so the crush and the single-group projection can never disagree.
"""

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from hogproj.basis import basis_period, lean_hog_contract_for
from hogproj.inputs import MarketingCut, Projection, WeanPigPriceSource
from hogproj.model import project

# Rows of the crush table, in display order: (label, summary key or cost line, kind)
ROWS: list[tuple[str, str, str]] = [
    ("Corn $/bu paid", "corn_cash_usd_bu", "summary"),
    ("Soybean meal $/ton paid", "sbm_cash_usd_ton", "summary"),
    ("DDGS $/ton", "ddgs_usd_ton", "summary"),
    ("Lean hog futures $/cwt", "futures_cwt", "sale"),
    ("Hog basis $/cwt", "basis_cwt", "sale"),
    ("Price $/cwt carcass", "price_cwt_carcass", "sale"),
    ("Revenue $/pig", "revenue_usd_per_head_sold", "summary"),
    ("Weaned pig $/pig", "Weaned pigs", "cost"),
    ("Feed $/pig", "Feed", "cost"),
    ("Barn / facilities $/pig", "Barn / facilities", "cost"),
    ("Labor $/pig", "Labor", "cost"),
    ("Animal health $/pig", "Vet / med", "cost"),
    ("Utilities $/pig", "Utilities", "cost"),
    ("Freight out $/pig", "Trucking to market", "cost"),
    ("Insurance / misc $/pig", "Insurance / misc", "cost"),
    ("G&A $/pig", "G&A", "cost"),
    ("Mortality $/pig", "Mortality ($/pig)", "cost"),
    ("Other / (premiums) $/pig", "Other / (premiums)", "cost"),
    ("Interest $/pig", "Interest", "cost"),
    ("Checkoff $/pig", "Checkoff", "cost"),
    ("Cost of production $/pig", "cost_usd_per_head_sold", "summary"),
    ("Margin $/pig", "net_usd_per_head_sold", "summary"),
    ("Margin after debt service $/pig", "net_after_debt_usd_per_head_sold", "summary"),
    ("Breakeven $/cwt carcass", "breakeven_cwt_carcass", "summary"),
]


@dataclass(frozen=True)
class Week:
    report_date: date
    wean_usd_hd: float  # USDA price before the adder
    corn_usd_bu: float
    sbm_usd_ton: float
    ddgs_usd_ton: float
    hog_futures_cwt: float  # for the contract that prices the sale
    hog_basis_cwt: float


def placement_for(report: date, placement_lag_days: int) -> date:
    return report + timedelta(days=placement_lag_days)


def sale_for(report: date, placement_lag_days: int, days_to_market: int) -> date:
    return placement_for(report, placement_lag_days) + timedelta(days=days_to_market)


def week_projection(
    base: Projection,
    w: Week,
    placement_lag_days: int,
    days_to_market: int,
    sale_weight_lb: float,
    corn_is_cash: bool,
) -> Projection:
    """The group's settings with this week's dates and prices and a single sale."""
    placed = placement_for(w.report_date, placement_lag_days)
    sold = placed + timedelta(days=days_to_market)
    loc = base.location.model_copy(
        update={
            "ddgs_usd_ton": w.ddgs_usd_ton,
            # a cash corn series already includes basis
            **({"corn_basis_usd_bu": 0.0} if corn_is_cash else {}),
        }
    )
    return base.model_copy(
        update={
            "placement_date": placed,
            "wean_pig_source": WeanPigPriceSource.USDA_CASH,
            "wean_pig_usda_cash_usd_hd": w.wean_usd_hd,
            "location": loc,
            "corn_futures_usd_bu": w.corn_usd_bu,
            "sbm_futures_usd_ton": w.sbm_usd_ton,
            "marketing": [
                MarketingCut(
                    days_after_placement=days_to_market,
                    pct_of_marketed=100,
                    live_weight_lb=sale_weight_lb,
                )
            ],
            "lean_hog_futures_cwt": {lean_hog_contract_for(sold): w.hog_futures_cwt},
            "hog_basis_cwt_by_period": {basis_period(sold): w.hog_basis_cwt},
        }
    )


def crush_table(
    base: Projection,
    weeks: list[Week],
    placement_lag_days: int = 1,
    days_to_market: int = 160,
    sale_weight_lb: float = 290.0,
    corn_is_cash: bool = False,
) -> pd.DataFrame:
    """Rows = ROWS labels (plus dates/contract), columns = one per week, in the given order."""
    columns: dict[str, dict[str, object]] = {}
    for w in weeks:
        p = week_projection(
            base, w, placement_lag_days, days_to_market, sale_weight_lb, corn_is_cash
        )
        r = project(p)
        sale = r.marketing.iloc[0]
        sold = float(r.summary["head_sold"])
        costs = dict(zip(r.costs["line"], r.costs["total_usd"], strict=True))
        col: dict[str, object] = {
            "USDA report date": w.report_date,
            "Placement date": p.placement_date,
            "Avg marketing date": sale["sale_date"],
            "CME contract": sale["contract"],
            "USDA weaned pig $/hd": w.wean_usd_hd,
        }
        for label, key, kind in ROWS:
            if kind == "summary":
                col[label] = float(r.summary[key])
            elif kind == "sale":
                col[label] = float(sale[key])
            else:
                col[label] = costs[key] / sold
        columns[w.report_date.isoformat()] = col
    return pd.DataFrame(columns)


def value_on(series: pd.Series | None, d: date) -> float | None:
    """Last value on or before d (prices are as of that day); None if nothing that early."""
    if series is None or series.empty:
        return None
    s = series.sort_index()
    upto = s.loc[s.index <= pd.Timestamp(d)]
    return float(upto.iloc[-1]) if len(upto) else None


def report_dates(anchor: date, weeks_back: int, weeks_forward: int) -> list[date]:
    """Weekly dates: `weeks_back` up to and including anchor, then `weeks_forward` after it.
    Newest first, like the owner's workbook."""
    dates = [anchor + timedelta(weeks=k) for k in range(-(weeks_back - 1), weeks_forward + 1)]
    return sorted(dates, reverse=True)


def build_weeks(
    dates: list[date],
    placement_lag_days: int,
    days_to_market: int,
    *,
    wean: pd.Series | None,
    corn: pd.Series | None,
    sbm: pd.Series | None,
    fallback_wean: float,
    fallback_corn: float,
    fallback_sbm: float,
    ddgs_usd_ton: float,
    hog_curve: dict[str, float],
    hog_contract_history: dict[str, pd.Series],
    basis_by_period: dict[int, float],
) -> tuple[list[Week], list[str]]:
    """One Week per report date, using price history where it exists.

    Weaned pig: the report's own week. Corn/SBM: as of placement. Lean hog futures: the pricing
    contract as of placement (history) or today's curve (nearest contract if missing).
    Returns notes listing anything that fell back to today's prices.
    """
    weeks, notes = [], set()
    for d in dates:
        placed = placement_for(d, placement_lag_days)
        sold = placed + timedelta(days=days_to_market)
        contract = lean_hog_contract_for(sold)
        w = value_on(wean, d)
        c = value_on(corn, placed)
        s = value_on(sbm, placed)
        hog = value_on(hog_contract_history.get(contract), placed)
        if w is None:
            notes.add("weaned pig price")
        if c is None:
            notes.add("corn")
        if s is None:
            notes.add("soybean meal")
        if hog is None:
            if contract in hog_curve:
                hog = hog_curve[contract]
            elif hog_curve:
                near = min(hog_curve, key=lambda k: abs(_months(k) - _months(contract)))
                hog = hog_curve[near]
                notes.add(f"{contract} futures (copied from {near})")
            notes.add("lean hog futures history")
        weeks.append(
            Week(
                report_date=d,
                wean_usd_hd=w if w is not None else fallback_wean,
                corn_usd_bu=c if c is not None else fallback_corn,
                sbm_usd_ton=s if s is not None else fallback_sbm,
                ddgs_usd_ton=ddgs_usd_ton,
                hog_futures_cwt=hog if hog is not None else 0.0,
                hog_basis_cwt=basis_by_period.get(basis_period(sold), 0.0),
            )
        )
    return weeks, sorted(notes)


def _months(code: str) -> int:
    y, m = (int(x) for x in code.split("-"))
    return y * 12 + m


def latest_date(series: pd.Series | None) -> date | None:
    """Date of the newest non-missing value."""
    if series is None or series.dropna().empty:
        return None
    return date.fromisoformat(str(series.dropna().index.max())[:10])


def current_report_date(latest_known: date, today: date) -> date:
    """Step the last known weekly report date forward in whole weeks up to today, so 'weeks
    ahead' really means after today even when the price history is a few weeks old."""
    d = latest_known
    while d + timedelta(weeks=1) <= today:
        d += timedelta(weeks=1)
    return d
