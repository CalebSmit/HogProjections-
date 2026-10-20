"""Wean-to-finish margin (the "wean pig crush"): buy a weaned pig, feed it, sell it ~160 days on.

    margin per pig = carcass cwt × (hog price at sale + your basis)
                     − (USDA weaned pig price + your adder) − feed − non-feed − debt service

Hog price at sale: for pigs already sold, the Lean Hog Index around the sale date; for pigs still
on feed, the lean hog futures contract the sale falls in (the first contract expiring on or after
the sale date), since futures converge to the index at expiry. `basis` is your price relative to
the index (grid premiums, sorting losses), so realized and projected margins are on one footing.

Pure: DataFrames and models in, DataFrames and numbers out.
"""

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Annotated, cast

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from hogproj.markets import seasonal_price_on

# CME lean hog contract months; each expires on the 10th business day of its month.
LH_MONTHS = {2: "Feb", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 10: "Oct", 12: "Dec"}
Contract = tuple[int, int]  # (year, month)


def _easter(y: int) -> date:
    """Gregorian Easter Sunday (anonymous algorithm)."""
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month = (h + m - 7 * n + 114) // 31
    return date(y, month, (h + m - 7 * n + 114) % 31 + 1)


def _nth_weekday(y: int, month: int, weekday: int, n: int) -> date:
    d = date(y, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(y: int, month: int, weekday: int) -> date:
    d = date(y, month + 1, 1) - timedelta(days=1) if month < 12 else date(y, 12, 31)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    return (
        d - timedelta(days=1)
        if d.weekday() == 5
        else d + timedelta(days=1)
        if d.weekday() == 6
        else d
    )


def exchange_holidays(y: int) -> set[date]:
    """CME livestock trading holidays: the US federal set plus Good Friday, minus Columbus and
    Veterans Day (markets open)."""
    return {
        _observed(date(y, 1, 1)), _nth_weekday(y, 1, 0, 3), _nth_weekday(y, 2, 0, 3),
        _easter(y) - timedelta(days=2), _last_weekday(y, 5, 0), _observed(date(y, 6, 19)),
        _observed(date(y, 7, 4)), _nth_weekday(y, 9, 0, 1), _nth_weekday(y, 11, 3, 4),
        _observed(date(y, 12, 25)),
    }  # fmt: skip


def contract_expiry(year: int, month: int) -> date:
    """10th business day of the month (weekends and exchange holidays skipped)."""
    holidays = exchange_holidays(year)
    d, n = date(year, month, 1), 0
    while True:
        if d.weekday() < 5 and d not in holidays:
            n += 1
            if n == 10:
                return d
        d += timedelta(days=1)


def contract_for(day: date) -> Contract:
    """The lean hog contract a sale on `day` is priced against."""
    y, m = day.year, day.month
    while True:
        if m in LH_MONTHS and contract_expiry(y, m) >= day:
            return y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def contract_label(c: Contract) -> str:
    return f"{LH_MONTHS[c[1]]} {c[0]}"


def model_contract_prices(
    contracts: list[Contract], today: date, index_now: float, factors: pd.DataFrame
) -> dict[Contract, float]:
    """Seasonal-model stand-in for futures: today's index carried to each contract's expiry."""
    days = [contract_expiry(*c) for c in contracts]
    prices = seasonal_price_on(days, today, index_now, factors)
    return {c: round(float(p) * 4) / 4 for c, p in zip(contracts, prices, strict=True)}


Money = Annotated[float, Field(ge=0)]


class CrushInputs(BaseModel):
    """One wean-to-finish pig. Defaults are typical round numbers: replace them with yours."""

    pig_usd_per_head: Money = 20.0  # USDA early weaned 10-12 lb cash composite (live at runtime)
    adder_usd_per_head: float = 0.0  # your premium/discount to the USDA price
    days_on_feed: Annotated[int, Field(ge=60, le=300)] = 160
    weight_lb_live: Annotated[float, Field(gt=0)] = 290.0
    carcass_yield: Annotated[float, Field(gt=0, le=1)] = 0.75
    basis_usd_per_cwt: float = 0.0  # your carcass price minus the Lean Hog Index

    corn_usd_per_bu: Money = 4.25
    sbm_usd_per_ton: Money = 320.0
    ddgs_usd_per_ton: Money = 155.0
    corn_lb: Money = 500.0
    sbm_lb: Money = 90.0
    ddgs_lb: Money = 90.0
    other_feed_lb: Money = 30.0
    other_feed_usd_per_lb: Money = 0.70

    health_usd: Money = 5.0
    facilities_labor_usd: Money = 30.0
    mortality_usd: Money = 7.0
    overhead_usd: Money = 3.0
    freight_usd: Money = 6.0
    interest_usd: Money = 4.0
    other_usd: Money = 1.0
    principal_usd: Money = 0.0
    term_interest_usd: Money = 0.0

    @property
    def carcass_cwt(self) -> float:
        return self.weight_lb_live * self.carcass_yield / 100


def feed_lines(c: CrushInputs, corn_usd_per_bu: float | None = None) -> dict[str, float]:
    corn = c.corn_usd_per_bu if corn_usd_per_bu is None else corn_usd_per_bu
    return {
        "Corn": c.corn_lb * corn / 56,
        "Soybean meal": c.sbm_lb * c.sbm_usd_per_ton / 2000,
        "DDGS": c.ddgs_lb * c.ddgs_usd_per_ton / 2000,
        "Other feed": c.other_feed_lb * c.other_feed_usd_per_lb,
    }


def other_lines(c: CrushInputs) -> dict[str, float]:
    return {
        "Animal health": c.health_usd,
        "Barn and labor": c.facilities_labor_usd,
        "Mortality": c.mortality_usd,
        "Overhead": c.overhead_usd,
        "Freight out": c.freight_usd,
        "Operating interest": c.interest_usd,
        "Other": c.other_usd,
        "Debt payments": c.principal_usd + c.term_interest_usd,
    }


def cost_usd(c: CrushInputs, pig: float | None = None, corn: float | None = None) -> float:
    """Everything a pig costs, including the weaned pig itself."""
    pig_cost = (c.pig_usd_per_head if pig is None else pig) + c.adder_usd_per_head
    return pig_cost + sum(feed_lines(c, corn).values()) + sum(other_lines(c).values())


def cost_table(c: CrushInputs) -> pd.DataFrame:
    """Cost per pig by line: $/pig, $/cwt carcass and share of the total."""
    lines = {"Weaned pig": c.pig_usd_per_head + c.adder_usd_per_head, **feed_lines(c),
             **other_lines(c)}  # fmt: skip
    lines = {k: v for k, v in lines.items() if abs(v) > 0.005}
    total = sum(lines.values())
    df = pd.DataFrame({"usd_per_head": lines})
    df.loc["Total cost"] = total
    df["usd_per_cwt_carcass"] = df["usd_per_head"] / c.carcass_cwt
    df["share"] = df["usd_per_head"] / total
    return df


def margin_usd(c: CrushInputs, hog_cwt: float, pig: float | None = None,
               corn: float | None = None) -> float:  # fmt: skip
    """Profit per pig at an index-equivalent hog price ($/cwt carcass)."""
    return c.carcass_cwt * (hog_cwt + c.basis_usd_per_cwt) - cost_usd(c, pig, corn)


def breakeven_pig(c: CrushInputs, hog_cwt: float) -> float:
    """The most you can pay for a weaned pig (USDA price, before your adder) and break even."""
    return c.pig_usd_per_head + margin_usd(c, hog_cwt)


def breakeven_hog(c: CrushInputs, pig: float | None = None) -> float:
    """The Lean Hog Index price (at sale) that covers every cost."""
    return cost_usd(c, pig) / c.carcass_cwt - c.basis_usd_per_cwt


# CBOT corn contract months. Feed bought in a month is priced off the first contract at or after
# it, the way the workbook priced corn off futures (plus carry) rather than today's cash.
CORN_MONTHS = (3, 5, 7, 9, 12)


def corn_contract_for(year: int, month: int) -> Contract:
    for m in CORN_MONTHS:
        if m >= month:
            return year, m
    return year + 1, CORN_MONTHS[0]


def forward_corn(placed: pd.Timestamp, sold: pd.Timestamp, curve: Mapping[Contract, float],
                 basis: float) -> float:  # fmt: skip
    """Average corn price over the months on feed from the futures curve, plus your basis.
    Months past the last listed contract use the last one."""
    if not curve:
        raise ValueError("empty corn curve")
    last = max(curve)
    months = pd.date_range(placed.to_period("M").to_timestamp(), sold, freq="MS")
    prices = []
    for mo in months:
        k = corn_contract_for(mo.year, mo.month)
        prices.append(curve[k] if k in curve else curve[last] if k > last else
                      curve[min(c for c in curve if c >= k)])  # fmt: skip
    return float(np.mean(prices)) + basis


def _ts(x: object) -> pd.Timestamp:
    return cast(pd.Timestamp, pd.Timestamp(str(x)))


def _corn_on_feed(corn: pd.DataFrame | None, placed: pd.Timestamp, sold: pd.Timestamp,
                  fallback: float) -> float:  # fmt: skip
    """Average monthly corn price over the months on feed; months not reported use `fallback`."""
    months = pd.date_range(placed.to_period("M").to_timestamp(), sold, freq="MS")
    if corn is None or corn.empty or len(months) == 0:
        return fallback
    by_month = dict(zip(pd.to_datetime(corn["month"]), corn["usd_per_bu"], strict=True))
    return float(np.mean([by_month.get(m, fallback) for m in months]))


def placements(
    pigs: pd.DataFrame,
    index: pd.DataFrame,
    c: CrushInputs,
    futures: Mapping[Contract, float],
    corn: pd.DataFrame | None = None,
    corn_curve: Mapping[Contract, float] | None = None,
    corn_basis: float = 0.0,
) -> pd.DataFrame:
    """Margin for each week's placement at that week's USDA weaned pig price.

    Pigs are placed the Monday of the report week and sold `days_on_feed` later. Sold already:
    status "sold", priced at the index averaged over the sale week. Still on feed: status
    "on feed", priced at its contract from `futures` (rows with no contract price are dropped).
    Realized rows use Iowa corn over the months on feed when `corn` is given; rows on feed use
    the CBOT corn curve plus your basis when `corn_curve` is given, else today's corn. Soybean
    meal, DDGS and other costs are today's inputs throughout.
    """
    days = pd.to_datetime(index["index_date"]).to_numpy(dtype="datetime64[D]")
    prices = index["lean_hog_index_usd_per_cwt_carcass"].to_numpy(dtype=float)
    weeks = pd.to_datetime(pigs["week_ending"]).to_numpy(dtype="datetime64[D]")
    cash = pigs["cash_usd_per_head"].to_numpy(dtype=float)
    rows = []
    for week, pig in zip(weeks, cash, strict=True):
        placed = week - np.timedelta64(4, "D")
        sold = placed + np.timedelta64(c.days_on_feed, "D")
        if sold <= days.max():
            near = prices[
                (days > sold - np.timedelta64(4, "D")) & (days <= sold + np.timedelta64(3, "D"))
            ]
            if len(near) == 0 or sold < days.min():
                continue
            hog, status, label = float(near.mean()), "sold", "Index"
            corn_px = _corn_on_feed(corn, _ts(placed), _ts(sold), c.corn_usd_per_bu)
        else:
            k = contract_for(_ts(sold).date())
            if k not in futures:
                continue
            hog, status, label = float(futures[k]), "on feed", contract_label(k)
            corn_px = (
                forward_corn(_ts(placed), _ts(sold), corn_curve, corn_basis)
                if corn_curve
                else c.corn_usd_per_bu
            )
        pig = float(pig)
        cost = cost_usd(c, pig, corn_px)
        revenue = c.carcass_cwt * (hog + c.basis_usd_per_cwt)
        rows.append(
            {"placed": _ts(placed), "sold": _ts(sold), "status": status, "priced_on": label,
             "pig_usd": pig + c.adder_usd_per_head, "hog_usd_per_cwt": hog,
             "corn_usd_per_bu": corn_px, "revenue_usd": revenue, "cost_usd": cost,
             "margin_usd": revenue - cost, "worth_usd": pig + c.adder_usd_per_head + revenue - cost}
        )  # fmt: skip
    return pd.DataFrame(rows)


# --- History ----------------------------------------------------------------------------------
# `worth_usd` on each placement row is what the pig turned out to be worth: the price (including
# your adder) at which that placement would have broken even, given the hog price it sold at and
# the corn it ate. worth − paid = margin.

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _sold(rows: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(rows[rows["status"] == "sold"])


def _year_month(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    months = pd.to_datetime(df["placed"]).to_numpy(dtype="datetime64[M]").astype(int)
    return months // 12 + 1970, months % 12 + 1


def margin_rank(value: float, history: Sequence[float] | np.ndarray) -> float:
    """Percentile (0-100) of `value` among past margins: share below, ties counted half."""
    h = np.asarray(history, dtype=float)
    h = h[~np.isnan(h)]
    if len(h) == 0:
        return float("nan")
    return float(((h < value).sum() + 0.5 * (h == value).sum()) / len(h) * 100)


def by_month(rows: pd.DataFrame) -> pd.DataFrame:
    """Average realized margin per pig by placement year (rows) and month (columns Jan..Dec)."""
    sold = _sold(rows)
    year, month = _year_month(sold)
    grid = (
        pd.DataFrame({"year": year, "month": month,
                      "margin": sold["margin_usd"].to_numpy(dtype=float)})
        .pivot_table(index="year", columns="month", values="margin", aggfunc="mean")
        .reindex(columns=range(1, 13))
    )  # fmt: skip
    grid.columns = MONTHS
    return grid


def month_average(rows: pd.DataFrame) -> pd.Series:
    """Average realized margin by placement month across all years (each week counts once)."""
    sold = _sold(rows)
    _, month = _year_month(sold)
    m = sold["margin_usd"].to_numpy(dtype=float)
    return pd.Series([float(m[month == k].mean()) if (month == k).any() else float("nan")
                      for k in range(1, 13)], index=MONTHS)  # fmt: skip


def annual_summary(rows: pd.DataFrame) -> pd.DataFrame:
    """Per placement year: weeks, average paid / worth / margin, share of weeks that made money,
    and the best and worst week's margin."""
    sold = _sold(rows)
    year, _ = _year_month(sold)
    out = []
    for y in sorted(set(year.tolist())):
        part = pd.DataFrame(sold[year == y])
        m = part["margin_usd"].to_numpy(dtype=float)
        out.append({"year": int(y), "weeks": len(part),
                    "paid_usd": float(part["pig_usd"].to_numpy(dtype=float).mean()),
                    "worth_usd": float(part["worth_usd"].to_numpy(dtype=float).mean()),
                    "margin_usd": float(m.mean()), "profitable": float((m > 0).mean()),
                    "best_usd": float(m.max()), "worst_usd": float(m.min())})  # fmt: skip
    return pd.DataFrame(out)


def contracts_needed(
    pigs: pd.DataFrame, c: CrushInputs, today: date, last_index: date
) -> list[Contract]:
    """Contracts that price pigs still on feed, plus a pig placed today."""
    weeks = pd.to_datetime(pigs["week_ending"]).to_numpy(dtype="datetime64[D]")
    sold = [_ts(w).date() + timedelta(days=c.days_on_feed - 4) for w in weeks]
    sold.append(today + timedelta(days=c.days_on_feed))
    return sorted({contract_for(d) for d in sold if d > last_index})
