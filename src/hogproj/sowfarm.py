"""Sow farm (farrow to wean): what a weaned pig costs to produce, what it sells for, and whether
finishing it beats selling it. Pure: no Streamlit.

    cost per weaned pig = (sow feed + non-feed, $ per sow per year) / pigs weaned per sow per year
    sow farm margin     = weaned pig price (USDA + your adder) − cost per weaned pig
    integrated margin   = sow farm margin + wean-to-finish margin of that same pig

Selling a weaned pig earns the sow farm margin; finishing it adds the wean-to-finish margin
(the crush), so the crush margin is exactly what finishing adds over selling.

Defaults reproduce Iowa State's farrow-to-wean estimate for September 2026 ($43.91 per weaned
pig at ~$4.00 corn and ~$300 soybean meal, 28.4 weaned per sow per year). The sow feed split is
a typical ration [VERIFY against ISU's budget]; non-feed is the remainder.
"""

from typing import Annotated

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

Money = Annotated[float, Field(ge=0)]

ISU_SEP_2026 = {"cost_per_weaned_pig": 43.91, "corn": 4.00, "sbm": 300.0, "weaned": 28.4}


class SowInputs(BaseModel):
    weaned_per_sow_yr: Annotated[float, Field(gt=0)] = 28.4  # from the herd inputs at runtime
    corn_usd_per_bu: Money = 4.00
    sbm_usd_per_ton: Money = 300.0
    corn_lb_per_sow_yr: Money = 1900.0  # ~2,500 lb of feed per sow per year in all
    sbm_lb_per_sow_yr: Money = 380.0
    other_feed_usd_per_sow_yr: Money = 60.0  # premix, lactation additives, processing
    nonfeed_usd_per_sow_yr: Money = 994.36  # labor, barns, vet, genetics, utilities, interest
    adder_usd_per_head: float = 0.0  # premium the sow farm gets over the USDA price

    def feed_usd_per_sow_yr(self, corn: float | None = None) -> float:
        corn = self.corn_usd_per_bu if corn is None else corn
        return (
            self.corn_lb_per_sow_yr * corn / 56
            + self.sbm_lb_per_sow_yr * self.sbm_usd_per_ton / 2000
            + self.other_feed_usd_per_sow_yr
        )


def cost_per_weaned_pig(s: SowInputs, corn: float | None = None) -> float:
    return (s.feed_usd_per_sow_yr(corn) + s.nonfeed_usd_per_sow_yr) / s.weaned_per_sow_yr


def cost_lines(s: SowInputs) -> pd.DataFrame:
    """Per weaned pig and per sow per year, by line."""
    per_sow = {
        "Corn": s.corn_lb_per_sow_yr * s.corn_usd_per_bu / 56,
        "Soybean meal": s.sbm_lb_per_sow_yr * s.sbm_usd_per_ton / 2000,
        "Other feed": s.other_feed_usd_per_sow_yr,
        "Non-feed": s.nonfeed_usd_per_sow_yr,
    }
    df = pd.DataFrame({"usd_per_sow_yr": per_sow})
    df.loc["Total"] = df["usd_per_sow_yr"].sum()
    df["usd_per_weaned_pig"] = df["usd_per_sow_yr"] / s.weaned_per_sow_yr
    return df


def margin(s: SowInputs, usda_price: float, corn: float | None = None) -> float:
    return usda_price + s.adder_usd_per_head - cost_per_weaned_pig(s, corn)


def history(pigs: pd.DataFrame, s: SowInputs, corn: pd.DataFrame | None = None,
            sbm: pd.DataFrame | None = None) -> pd.DataFrame:  # fmt: skip
    """Weekly sow farm margin since the USDA series starts. Corn (and soybean meal, `sbm` with
    month/usd) are the Iowa monthly prices where given, else today's inputs; non-feed is
    today's input."""
    by_month = (
        dict(zip(pd.to_datetime(corn["month"]), corn["usd_per_bu"], strict=True))
        if corn is not None and not corn.empty
        else {}
    )
    weeks = pd.to_datetime(pigs["week_ending"])
    price = pigs["cash_usd_per_head"].to_numpy(dtype=float)
    month = weeks.to_numpy(dtype="datetime64[M]")
    corn_px = np.array([by_month.get(pd.Timestamp(m), s.corn_usd_per_bu) for m in month])
    sbm_by = (dict(zip(pd.to_datetime(sbm["month"]), sbm["usd"], strict=True))
              if sbm is not None and not sbm.empty else {})  # fmt: skip
    sbm_px = np.array([sbm_by.get(pd.Timestamp(m), s.sbm_usd_per_ton) for m in month])
    cost = np.array([
        cost_per_weaned_pig(s.model_copy(update={"sbm_usd_per_ton": float(b)}), float(c))
        for c, b in zip(corn_px, sbm_px, strict=True)
    ])  # fmt: skip
    return pd.DataFrame(
        {"week_ending": weeks.to_numpy(), "price_usd": price + s.adder_usd_per_head,
         "cost_usd": cost, "margin_usd": price + s.adder_usd_per_head - cost,
         "corn_usd_per_bu": corn_px}
    )  # fmt: skip


def integrated(sow: pd.DataFrame, crush_rows: pd.DataFrame, sow_adder: float = 0.0,
               w2f_adder: float = 0.0) -> pd.DataFrame:  # fmt: skip
    """Join each USDA week's sow farm margin with the crush margin of a pig placed that week.

    Placements happen the Monday of the report week (week ending − 4 days), as in `crush`.
    Only placements already sold are joined, so both halves are realized. Your own pigs move at
    the sow farm's price (USDA + `sow_adder`), so the finishing margin is restated from the
    crush rows' purchase price (USDA + `w2f_adder`); the adders then cancel in the total.
    """
    sold = crush_rows[crush_rows["status"] == "sold"]
    w2f = pd.DataFrame(
        {"week_ending": pd.to_datetime(sold["placed"]).to_numpy() + np.timedelta64(4, "D"),
         "finish_margin_usd": sold["margin_usd"].to_numpy(dtype=float) + w2f_adder - sow_adder}
    )  # fmt: skip
    df = sow.merge(w2f, on="week_ending", how="inner")
    df["integrated_usd"] = df["margin_usd"] + df["finish_margin_usd"]
    return df


def by_year(df: pd.DataFrame) -> pd.DataFrame:
    year = df["week_ending"].to_numpy(dtype="datetime64[Y]").astype(int) + 1970
    out = []
    for y in sorted(set(year.tolist())):
        g = df[year == y]

        def avg(col: str, g: pd.DataFrame = g) -> float:
            return float(g[col].to_numpy(dtype=float).mean())

        out.append({"year": y, "weeks": len(g), "sow_usd": avg("margin_usd"),
                    "finish_usd": avg("finish_margin_usd"),
                    "integrated_usd": avg("integrated_usd")})  # fmt: skip
    return pd.DataFrame(out)
