"""Weekly cohort herd flow: sows -> farrowings -> weaned -> wean-to-finish -> marketed.

Pure model code: inputs in, DataFrame out. Defaults come from docs/research/domain.md §1.
The pipeline before week 0 is in steady state at `sows_start`, so a constant herd gives
constant marketings and a herd change shows up after the biological lags.
"""

from typing import Annotated

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class HerdInputs(BaseModel):
    sows_start: Annotated[float, Field(ge=0)] = 1000.0
    sows_target: Annotated[float, Field(ge=0)] = 1000.0  # herd size from `change_week` onward
    change_week: Annotated[int, Field(ge=0)] = 0  # first week bred at `sows_target`
    weeks: Annotated[int, Field(ge=52, le=520)] = 104  # >= 52 so annual totals are whole years

    litters_per_sow_yr: Annotated[float, Field(gt=0, le=3)] = (
        2.35  # 2.3-2.45, domain.md §1 [VERIFY]
    )
    # 14.3 born alive x (1 - 0.154) x 2.35 ≈ 28.5 weaned/sow/yr, the PigCHAMP NA 2025 mean
    born_alive_per_litter: Annotated[float, Field(gt=0, le=25)] = 14.3  # derived, [VERIFY]
    prewean_mortality: Annotated[float, Field(ge=0, lt=1)] = 0.154  # PigCHAMP 2025
    wean_to_market_mortality: Annotated[float, Field(ge=0, lt=1)] = (
        0.065  # MetaFarms PAS W2F 6.2-6.8%
    )

    gestation_days: Annotated[float, Field(gt=0)] = 114.0  # standard
    lactation_days: Annotated[float, Field(gt=0)] = 21.0  # 19-24 days, US typical
    wean_to_market_days: Annotated[float, Field(gt=0)] = 156.0  # MetaFarms PAS W2F

    weight_lb_live_market: Annotated[float, Field(gt=0)] = 283.0  # MetaFarms PAS W2F out-weight
    carcass_yield: Annotated[float, Field(gt=0, le=1)] = 0.75  # ISU: $64.04 live ≙ $85.39 carcass


def pigs_sold_per_sow_yr(inp: HerdInputs) -> float:
    return (
        inp.litters_per_sow_yr
        * inp.born_alive_per_litter
        * (1 - inp.prewean_mortality)
        * (1 - inp.wean_to_market_mortality)
    )


def _weeks(days: float) -> int:
    return max(1, round(days / 7))


def lags_weeks(inp: HerdInputs) -> dict[str, int]:
    return {
        "gestation": _weeks(inp.gestation_days),
        "lactation": _weeks(inp.lactation_days),
        "wean_to_market": _weeks(inp.wean_to_market_days),
    }


def simulate(inp: HerdInputs) -> pd.DataFrame:
    """One row per week (0 .. weeks-1). Head counts are floats (expected values)."""
    lag = lags_weeks(inp)
    pre = lag["gestation"] + lag["lactation"] + lag["wean_to_market"]
    t = np.arange(-pre, inp.weeks)  # warm-up history so week 0 is already in steady state
    i0 = pre  # index of week 0

    sows = np.where(t >= inp.change_week, inp.sows_target, inp.sows_start)

    def shift(x: np.ndarray, k: int) -> np.ndarray:
        """x[t - k], holding the earliest value for indices before the series starts."""
        return np.concatenate([np.full(k, x[0]), x[:-k]]) if k else x

    bred_sows = shift(sows, lag["gestation"])
    farrowings = bred_sows * inp.litters_per_sow_yr / 52
    born_alive = farrowings * inp.born_alive_per_litter
    at_weaning = shift(born_alive, lag["lactation"])  # litters reaching weaning age this week
    weaned = at_weaning * (1 - inp.prewean_mortality)
    prewean_deaths = at_weaning * inp.prewean_mortality
    at_market = shift(weaned, lag["wean_to_market"])
    marketed = at_market * (1 - inp.wean_to_market_mortality)
    w2f_deaths = at_market * inp.wean_to_market_mortality

    def in_phase(entered: np.ndarray, k: int) -> np.ndarray:
        """Head in a phase at the end of week t: everyone who entered in (t-k, t].

        Each cohort leaves (alive or dead) exactly k weeks after entering, so
        inventory[t] - inventory[t-1] = entered[t] - left[t]. Deaths are booked at exit.
        """
        return np.convolve(entered, np.ones(k))[: len(entered)]

    suckling = in_phase(born_alive, lag["lactation"])
    growing = in_phase(weaned, lag["wean_to_market"])

    lb_live = marketed * inp.weight_lb_live_market
    df = pd.DataFrame(
        {
            "week": t,
            "sows": sows,
            "farrowings": farrowings,
            "born_alive_head": born_alive,
            "weaned_head": weaned,
            "prewean_deaths_head": prewean_deaths,
            "marketed_head": marketed,
            "wean_to_market_deaths_head": w2f_deaths,
            "suckling_inventory_head": suckling,
            "growing_inventory_head": growing,
            "sold_lb_live": lb_live,
            "sold_lb_carcass": lb_live * inp.carcass_yield,
        }
    )
    return df.iloc[i0:].reset_index(drop=True)
