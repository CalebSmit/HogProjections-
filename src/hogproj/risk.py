"""Price risk: simulate many possible hog and corn price paths and the profit each gives.

Pure model code; randomness takes an explicit `seed` (docs/ARCHITECTURE.md invariant).

Hog price, weekly: price_t = expected_t × exp(x_t), where expected_t is the seasonal path from
today's price and x_t is a mean-reverting shock, x_{t+1} = phi·x_t + sigma·e. phi and sigma are
estimated from USDA index history after removing the seasonal pattern. Corn follows a random
walk with a user-set annual volatility (independent of hogs; a simplification).

A price floor (LRP / put-like) pays max(floor - price, 0) per cwt sold, less a premium per cwt.
"""

from typing import Annotated

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from hogproj.finance import CostInputs, cost_usd_per_head


class HogDynamics(BaseModel):
    phi: Annotated[float, Field(ge=0, lt=1)] = 0.9  # weekly persistence of a price surprise
    sigma: Annotated[float, Field(ge=0)] = 0.04  # weekly log-price shock (std dev)
    weeks_used: int = 0  # history behind the estimate


def estimate_hog_dynamics(index: pd.DataFrame, factors: pd.DataFrame) -> HogDynamics:
    """Fit phi and sigma to weekly, de-seasonalized log Lean Hog Index."""
    s = (
        index.set_index(pd.to_datetime(index["index_date"]))["lean_hog_index_usd_per_cwt_carcass"]
        .resample("W")
        .last()
        .dropna()
    )
    if len(s) < 30:
        return HogDynamics()
    if factors.empty:
        f = np.ones(len(s))
    else:
        by_month = dict(zip(factors["month"], factors["factor"], strict=True))
        f = np.array([by_month[m] for m in pd.Series(s.index).dt.month])
    x = np.log(s.to_numpy(dtype=float) / f)
    x = x - x.mean()
    prev, nxt = x[:-1], x[1:]
    phi = float(np.clip(np.dot(prev, nxt) / np.dot(prev, prev), 0.0, 0.995))
    resid = nxt - phi * prev
    return HogDynamics(phi=phi, sigma=float(resid.std(ddof=1)), weeks_used=len(s))


class RiskInputs(BaseModel):
    n_paths: Annotated[int, Field(ge=100, le=20000)] = 2000
    seed: int = 7
    corn_vol_annual: Annotated[float, Field(ge=0, le=1)] = (
        0.20  # ~20%/yr is typical for corn [VERIFY]
    )
    floor_usd_per_cwt_carcass: float | None = None  # None = no price protection
    premium_usd_per_cwt_carcass: Annotated[float, Field(ge=0)] = 0.0


def simulate_profit(
    marketed_head: np.ndarray,
    sold_cwt_carcass: np.ndarray,
    expected_hog_usd_per_cwt: np.ndarray,
    cost: CostInputs,  # already synced to the herd (see outlook.synced)
    dyn: HogDynamics,
    risk: RiskInputs,
) -> dict[str, np.ndarray]:
    """Return weekly hog price paths and total profit per path, with and without the floor."""
    weeks = len(marketed_head)
    rng = np.random.default_rng(risk.seed)
    shocks = rng.standard_normal((risk.n_paths, weeks)) * dyn.sigma
    x = np.zeros((risk.n_paths, weeks))
    for t in range(1, weeks):
        x[:, t] = dyn.phi * x[:, t - 1] + shocks[:, t]
    hog = expected_hog_usd_per_cwt[None, :] * np.exp(x)

    corn0 = cost.corn_usd_per_bu
    corn_week_vol = risk.corn_vol_annual / np.sqrt(52)
    corn_walk = np.cumsum(rng.standard_normal((risk.n_paths, weeks)) * corn_week_vol, axis=1)
    corn = corn0 * np.exp(corn_walk - 0.5 * corn_week_vol**2 * np.arange(1, weeks + 1))
    base_cost = cost_usd_per_head(cost)["net"]
    corn_bu = cost.corn_bu_per_head * cost.feed_scale
    cost_per_head = base_cost + corn_bu * (corn - corn0)

    revenue = hog * sold_cwt_carcass[None, :]
    profit_weekly = revenue - cost_per_head * marketed_head[None, :]
    out = {
        "hog_paths": hog,
        "profit": profit_weekly.sum(axis=1),
    }
    if risk.floor_usd_per_cwt_carcass is not None:
        payoff = np.maximum(risk.floor_usd_per_cwt_carcass - hog, 0)
        net = (payoff - risk.premium_usd_per_cwt_carcass) * sold_cwt_carcass[None, :]
        out["profit_with_floor"] = (profit_weekly + net).sum(axis=1)
    return out


def distribution_summary(profit: np.ndarray) -> dict[str, float]:
    return {
        "p_profit": float((profit > 0).mean()),
        "p10": float(np.percentile(profit, 10)),
        "p50": float(np.percentile(profit, 50)),
        "p90": float(np.percentile(profit, 90)),
        "mean": float(profit.mean()),
    }
