"""Cost of production, breakeven and margins for a farrow-to-finish operation.

Pure model code. The cost structure follows the CIH Hog Margin Watch shortcut
(docs/research/domain.md §2): per 100 lb carcass, 5.3 bu corn + 73 lb SBM + $44 other costs.
All prices are $/cwt carcass unless the name says `live`.
"""

from typing import Annotated

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

LB_PER_TON = 2000


class CostInputs(BaseModel):
    # Dec 2026 corn futures traded $5.23-5.50 in early Oct 2026 (thepigsite weekly report)
    corn_usd_per_bu: Annotated[float, Field(ge=0)] = 5.25
    sbm_usd_per_ton: Annotated[float, Field(ge=0)] = 300.0  # ISU B1-21: $0.15/lb [VERIFY]
    # CME Lean Hog Index, Oct 12 2026 (Dec 2026 futures settled 66.93 on Oct 16)
    lean_hog_usd_per_cwt_carcass: Annotated[float, Field(ge=0)] = 75.75

    corn_bu_per_cwt_carcass: Annotated[float, Field(ge=0)] = 5.3  # CIH Hog Margin Watch [VERIFY]
    sbm_lb_per_cwt_carcass: Annotated[float, Field(ge=0)] = 73.0  # CIH Hog Margin Watch [VERIFY]
    other_usd_per_cwt_carcass: Annotated[float, Field(ge=0)] = 44.0  # CIH non-feed costs [VERIFY]

    weight_lb_live_market: Annotated[float, Field(gt=0)] = 283.0  # MetaFarms PAS W2F out-weight
    carcass_yield: Annotated[float, Field(gt=0, le=1)] = 0.75  # ISU: $64.04 live ≙ $85.39 carcass

    @property
    def weight_lb_carcass(self) -> float:
        return self.weight_lb_live_market * self.carcass_yield


def cost_usd_per_cwt_carcass(c: CostInputs) -> dict[str, float]:
    corn = c.corn_bu_per_cwt_carcass * c.corn_usd_per_bu
    sbm = c.sbm_lb_per_cwt_carcass * c.sbm_usd_per_ton / LB_PER_TON
    other = c.other_usd_per_cwt_carcass
    return {"corn": corn, "sbm": sbm, "other": other, "total": corn + sbm + other}


def breakeven(c: CostInputs) -> dict[str, float]:
    """Hog price that covers all costs, on carcass and live bases."""
    total = cost_usd_per_cwt_carcass(c)["total"]
    return {
        "price_cwt_carcass": total,
        "price_cwt_live": total * c.carcass_yield,
        "cost_usd_per_head": total * c.weight_lb_carcass / 100,
    }


def cost_table(c: CostInputs) -> pd.DataFrame:
    """Cost lines per cwt carcass, per head and as a share of the total."""
    lines = cost_usd_per_cwt_carcass(c)
    df = pd.DataFrame(
        {"usd_per_cwt_carcass": [lines["corn"], lines["sbm"], lines["other"], lines["total"]]},
        index=pd.Index(["Corn", "Soybean meal", "Other (non-feed)", "Total"], name="cost line"),
    )
    df["usd_per_head"] = df["usd_per_cwt_carcass"] * c.weight_lb_carcass / 100
    df["share"] = df["usd_per_cwt_carcass"] / lines["total"]
    return df


def margin_usd_per_head(c: CostInputs) -> float:
    m_cwt = c.lean_hog_usd_per_cwt_carcass - cost_usd_per_cwt_carcass(c)["total"]
    return m_cwt * c.weight_lb_carcass / 100


def sensitivity(
    c: CostInputs, hog_usd_per_cwt_carcass: np.ndarray, corn_usd_per_bu: np.ndarray
) -> pd.DataFrame:
    """Margin $/head on a grid: rows are corn prices, columns are lean hog prices."""
    data = [
        [
            margin_usd_per_head(
                c.model_copy(update={"corn_usd_per_bu": corn, "lean_hog_usd_per_cwt_carcass": hog})
            )
            for hog in hog_usd_per_cwt_carcass
        ]
        for corn in corn_usd_per_bu
    ]
    return pd.DataFrame(
        data,
        index=pd.Index(np.round(corn_usd_per_bu, 2), name="corn_usd_per_bu"),
        columns=pd.Index(np.round(hog_usd_per_cwt_carcass, 2), name="lean_hog_usd_per_cwt_carcass"),
    )


def weekly_returns(herd: pd.DataFrame, c: CostInputs) -> pd.DataFrame:
    """Revenue, cost and margin for each week's marketings (from `herd.simulate`).

    Uses the herd's carcass pounds sold, so a different market weight in the herd model
    flows through. Costs are booked when the pigs are sold.
    """
    cwt = herd["sold_lb_carcass"] / 100
    out = pd.DataFrame(herd, columns=["week", "marketed_head", "sold_lb_carcass"])
    out["revenue_usd"] = cwt * c.lean_hog_usd_per_cwt_carcass
    out["cost_usd"] = cwt * cost_usd_per_cwt_carcass(c)["total"]
    out["margin_usd"] = out["revenue_usd"] - out["cost_usd"]
    out["cumulative_margin_usd"] = out["margin_usd"].cumsum()
    return out
