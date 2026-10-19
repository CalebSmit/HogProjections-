"""Cost of production, breakeven and margins for a farrow-to-finish operation.

Pure model code. The cost lines follow the Iowa State University Estimated Livestock Returns
(ISU ELR) farrow-to-finish budget, per finished pig sold, so results can be checked against
ISU's monthly table (docs/research/domain.md §2, tests/fixtures/isu_f2f_2026.csv):
    total cost = feed + nonfeed + death loss
    breakeven  = total cost / cwt sold           (ISU leaves the manure credit out)
    profit     = sales - total cost + manure credit
Defaults are ISU's Sep 2026 sale month. Prices are $/cwt carcass unless the name says `live`.
"""

from typing import Annotated

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

LB_PER_TON = 2000
ISU_WEIGHT_LB_LIVE = 270.0  # ISU ELR budgets a 270 lb finished pig


class CostInputs(BaseModel):
    # Dec 2026 corn futures traded $5.23-5.50 in early Oct 2026 (thepigsite weekly report)
    corn_usd_per_bu: Annotated[float, Field(ge=0)] = 5.25
    sbm_usd_per_ton: Annotated[float, Field(ge=0)] = 300.0  # ISU B1-21: $0.15/lb [VERIFY]
    # CME Lean Hog Index, Oct 12 2026 (the app replaces this with the latest USDA value)
    lean_hog_usd_per_cwt_carcass: Annotated[float, Field(ge=0)] = 75.75

    # Whole-herd feed per pig sold at 270 lb. ISU publishes $/head, not quantities, so these
    # are ISU Sep 2026 corn $40.78 and SBM $15.54 ÷ ~$4.00/bu corn and ~$300/ton SBM [VERIFY:
    # calibrate against USDA NW_GR110/NW_GR116 once a My Market News key is available].
    corn_bu_per_head: Annotated[float, Field(ge=0)] = 10.2
    sbm_lb_per_head: Annotated[float, Field(ge=0)] = 104.0
    # ISU Sep 2026: DDGS 10.25 + complete feeds & other 18.10 + feed processing 5.92
    other_feed_usd_per_head: Annotated[float, Field(ge=0)] = 34.27
    # ISU Sep 2026: variable 48.99 + operating interest 4.47 + fixed 23.30
    nonfeed_usd_per_head: Annotated[float, Field(ge=0)] = 76.76
    death_loss_usd_per_head: Annotated[float, Field(ge=0)] = 8.36  # ISU Sep 2026
    # Part of the cost per pig is really cost per sow (sow feed, genetics, farrowing barns), so
    # it falls as each sow produces more pigs. ISU farrow-to-wean, Sep 2026: $43.91 per weaned
    # pig ÷ (1 - 0.065 wean-to-market deaths) = $46.96 per pig sold.
    breeding_herd_usd_per_head: Annotated[float, Field(ge=0)] = 46.96
    # Productivity the ISU per-pig costs correspond to: the app's default herd (28.4 weaned,
    # 26.6 sold per sow per year) [VERIFY against ISU's NASS/FINBIN inputs].
    ref_pigs_sold_per_sow_yr: Annotated[float, Field(gt=0)] = 26.58
    pigs_sold_per_sow_yr: Annotated[float, Field(gt=0)] = 26.58  # set from the herd
    manure_credit_usd_per_head: Annotated[float, Field(ge=0)] = 5.59  # ISU Sep 2026

    weight_lb_live_market: Annotated[float, Field(gt=0)] = 283.0  # MetaFarms PAS W2F out-weight
    carcass_yield: Annotated[float, Field(gt=0, le=1)] = 0.75  # ISU: $64.04 live ≙ $85.39 carcass

    @property
    def weight_lb_carcass(self) -> float:
        return self.weight_lb_live_market * self.carcass_yield

    @property
    def cwt_carcass(self) -> float:
        return self.weight_lb_carcass / 100

    @property
    def feed_scale(self) -> float:
        """Feed grows with market weight; ISU's quantities are for a 270 lb pig."""
        return self.weight_lb_live_market / ISU_WEIGHT_LB_LIVE


def cost_usd_per_head(c: CostInputs) -> dict[str, float]:
    corn = c.corn_bu_per_head * c.corn_usd_per_bu * c.feed_scale
    sbm = c.sbm_lb_per_head * c.sbm_usd_per_ton / LB_PER_TON * c.feed_scale
    other_feed = c.other_feed_usd_per_head * c.feed_scale
    productivity = c.breeding_herd_usd_per_head * (
        c.ref_pigs_sold_per_sow_yr / c.pigs_sold_per_sow_yr - 1
    )
    total = (
        corn + sbm + other_feed + c.nonfeed_usd_per_head + c.death_loss_usd_per_head + productivity
    )
    return {
        "corn": corn,
        "sbm": sbm,
        "other_feed": other_feed,
        "nonfeed": c.nonfeed_usd_per_head,
        "death_loss": c.death_loss_usd_per_head,
        "productivity": productivity,
        "total": total,
        "manure_credit": c.manure_credit_usd_per_head,
        "net": total - c.manure_credit_usd_per_head,
    }


def breakeven(c: CostInputs) -> dict[str, float]:
    """Hog price that covers total cost (ISU convention: before the manure credit)."""
    total = cost_usd_per_head(c)["total"]
    carcass = total / c.cwt_carcass
    return {
        "price_cwt_carcass": carcass,
        "price_cwt_live": carcass * c.carcass_yield,
        "cost_usd_per_head": total,
    }


def cost_table(c: CostInputs) -> pd.DataFrame:
    """Cost lines per head, per cwt carcass and as a share of total cost."""
    lines = cost_usd_per_head(c)
    labels = {
        "corn": "Corn",
        "sbm": "Soybean meal",
        "other_feed": "Other feed",
        "nonfeed": "Non-feed",
        "death_loss": "Death loss",
        "productivity": "Sow productivity",
        "total": "Total cost",
        "manure_credit": "Less manure credit",
        "net": "Net cost",
    }
    usd = [-lines[k] if k == "manure_credit" else lines[k] for k in labels]
    df = pd.DataFrame(
        {"usd_per_head": usd},
        index=pd.Index(list(labels.values()), name="cost line"),
    )
    df["usd_per_cwt_carcass"] = df["usd_per_head"] / c.cwt_carcass
    df["share"] = df["usd_per_head"] / lines["total"]
    return df


def margin_usd_per_head(c: CostInputs) -> float:
    """Profit per pig sold, including the manure credit (ISU 'total profit')."""
    return c.lean_hog_usd_per_cwt_carcass * c.cwt_carcass - cost_usd_per_head(c)["net"]


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


def weekly_returns(
    herd: pd.DataFrame, c: CostInputs, hog_usd_per_cwt_carcass: np.ndarray | None = None
) -> pd.DataFrame:
    """Revenue, cost and margin for each week's marketings (from `herd.simulate`).

    Revenue uses the herd's carcass pounds sold at a flat price (`c`) or a weekly price path;
    costs are per pig sold, net of the manure credit, and are booked when the pigs are sold.
    """
    out = pd.DataFrame(herd, columns=["week", "marketed_head", "sold_lb_carcass"])
    price = (
        np.full(len(out), c.lean_hog_usd_per_cwt_carcass)
        if hog_usd_per_cwt_carcass is None
        else np.asarray(hog_usd_per_cwt_carcass, dtype=float)
    )
    out["hog_usd_per_cwt_carcass"] = price
    out["revenue_usd"] = out["sold_lb_carcass"] / 100 * price
    out["cost_usd"] = out["marketed_head"] * cost_usd_per_head(c)["net"]
    out["margin_usd"] = out["revenue_usd"] - out["cost_usd"]
    out["cumulative_margin_usd"] = out["margin_usd"].cumsum()
    return out
