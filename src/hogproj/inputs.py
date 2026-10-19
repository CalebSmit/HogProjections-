"""Typed inputs for a wean-to-finish group projection. Pure data, no I/O.

Units are in the field names: usd_bu = $/bushel, usd_ton = $/short ton (2,000 lb),
cwt_carcass = $/100 lb carcass, lb_live = live weight in pounds.
"""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

CORN_LB_PER_BU = 56.0
MAX_PHASES = 12  # Excel workbook row slots
MAX_CUTS = 8
LB_PER_TON = 2000.0


class WeanPigPriceSource(StrEnum):
    USDA_CASH = "USDA cash (open market)"
    USDA_FORMULA = "USDA formula"
    MANUAL = "Manual"


class BarnCostMode(StrEnum):
    PER_SPACE_YEAR = "$/space/year"
    PER_PIG_PLACED = "$/pig placed"


class LaborCostMode(StrEnum):
    HOURLY = "hours x wage"
    PER_PIG_PLACED = "$/pig placed"


class MortalityMode(StrEnum):
    PCT_OF_HEAD = "% of head"  # deads reduce head sold (and eat some feed)
    USD_PER_PIG = "$ per pig"  # flat death-loss charge per pig placed; head sold = placed


class InterestMode(StrEnum):
    RATE = "annual rate"  # rate x (pig + half the feed) x days on feed
    USD_PER_PIG = "$ per pig"


class Strict(BaseModel):
    # A cleared spreadsheet cell arrives as NaN; refuse it instead of computing "$nan".
    model_config = ConfigDict(allow_inf_nan=False)


class Location(Strict):
    """Local prices for one feeding location. Basis is local cash minus CBOT futures."""

    name: str
    state: str = ""
    corn_basis_usd_bu: float  # e.g. -0.45 = 45 cents under
    sbm_basis_usd_ton: float  # delivered-to-farm premium over CBOT meal futures
    ddgs_usd_ton: float  # DDGS trades cash, no futures
    barn_rent_usd_space_yr: float
    labor_wage_usd_hr: float
    source: str = ""


class FeedPhase(Strict):
    name: str
    feed_lb_per_pig: float = Field(ge=0)
    corn_pct: float = Field(ge=0, le=100)
    sbm_pct: float = Field(ge=0, le=100)
    ddgs_pct: float = Field(ge=0, le=100)
    other_usd_ton: float = Field(ge=0)  # premix, fat, AA, minerals: priced per ton of *other*

    @model_validator(mode="after")
    def _pct_le_100(self) -> "FeedPhase":
        if self.corn_pct + self.sbm_pct + self.ddgs_pct > 100.0001:
            raise ValueError(f"{self.name}: corn + SBM + DDGS inclusion exceeds 100%")
        return self

    @property
    def other_pct(self) -> float:
        return max(0.0, 100.0 - self.corn_pct - self.sbm_pct - self.ddgs_pct)


class MarketingCut(Strict):
    """One marketing event: share of the pigs that reach market, sold N days after placement."""

    days_after_placement: int = Field(ge=1)
    pct_of_marketed: float = Field(ge=0, le=100)
    live_weight_lb: float = Field(gt=0)


class Projection(Strict):
    # Group
    head_placed: int = Field(default=2400, gt=0)
    placement_date: date
    wean_weight_lb: float = 12.0
    mortality_mode: MortalityMode = MortalityMode.PCT_OF_HEAD
    mortality_pct: float = Field(default=5.0, ge=0, lt=100)
    mortality_cost_usd_hd: float = 0.0  # used in $-per-pig mode, per pig placed
    dead_feed_share: float = Field(
        default=0.25, ge=0, le=1
    )  # deads eat this share of a full feed budget
    carcass_yield_pct: float = Field(default=75.0, gt=0, le=100)

    # Weaned pig
    wean_pig_source: WeanPigPriceSource = WeanPigPriceSource.USDA_CASH
    wean_pig_usda_cash_usd_hd: float = 0.0
    wean_pig_usda_formula_usd_hd: float = 0.0
    wean_pig_manual_usd_hd: float = 0.0
    wean_pig_adder_usd_hd: float = 0.0  # system premium over the USDA price (not on Manual)
    wean_pig_freight_usd_hd: float = 0.0

    # Feed
    location: Location
    corn_futures_usd_bu: float
    sbm_futures_usd_ton: float
    feed_phases: list[FeedPhase] = Field(min_length=1, max_length=MAX_PHASES)
    feed_mill_usd_ton: float = 0.0  # grind/mix/delivery charge on every ton
    corn_carry_usd_bu: float = 0.0  # storage/carry added to local cash corn
    corn_hedged_pct: float = Field(default=0.0, ge=0, le=100)
    corn_hedged_usd_bu: float = 0.0  # all-in cash price on the hedged/contracted share
    sbm_hedged_pct: float = Field(default=0.0, ge=0, le=100)
    sbm_hedged_usd_ton: float = 0.0

    # Facilities, labor, other $/head placed
    barn_mode: BarnCostMode = BarnCostMode.PER_SPACE_YEAR
    barn_usd_pig_placed: float = 0.0
    barn_downtime_days: int = Field(default=10, ge=0)  # wash/dry/fill between groups
    labor_mode: LaborCostMode = LaborCostMode.HOURLY
    labor_hr_per_pig: float = 0.15
    labor_usd_pig_placed: float = 0.0
    vet_med_usd_hd: float = 0.0
    utilities_usd_hd: float = 0.0
    trucking_usd_hd_sold: float = 0.0
    insurance_misc_usd_hd: float = 0.0
    ga_usd_hd: float = 0.0  # general & administrative, per pig placed
    other_usd_hd_sold: float = 0.0  # other costs; negative = sales premiums received
    interest_mode: InterestMode = InterestMode.RATE
    interest_rate_pct: float = 0.0  # annual, on the pig + half the feed for the feeding period
    interest_usd_hd: float = 0.0  # used in $-per-pig mode, per pig placed

    # Debt service (below the operating margin): per head sold
    principal_usd_hd: float = 0.0
    term_interest_usd_hd: float = 0.0

    # Revenue
    marketing: list[MarketingCut] = Field(min_length=1, max_length=MAX_CUTS)
    lean_hog_futures_cwt: dict[str, float]  # contract code "2027-04" -> $/cwt carcass
    hog_basis_cwt_by_period: dict[int, float]  # half-month period 1-24 -> avg historical basis
    carcass_premium_cwt: float = 0.0  # lean/grade merit premium, $/cwt carcass
    hog_hedged_pct: float = Field(default=0.0, ge=0, le=100)
    hog_hedged_cwt: float = 0.0  # futures level locked on the hedged share; basis still applies
    checkoff_pct: float = 0.35  # National Pork Checkoff, % of gross

    @model_validator(mode="after")
    def _marketing_sums_to_100(self) -> "Projection":
        total = sum(c.pct_of_marketed for c in self.marketing)
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"marketing cuts must sum to 100% (got {total:.1f}%)")
        return self

    @property
    def barn_days_occupied(self) -> int:
        """Placement to last pig out, plus downtime before the next group."""
        return max(c.days_after_placement for c in self.marketing) + self.barn_downtime_days

    @property
    def wean_pig_usd_hd(self) -> float:
        """Price paid per weaned pig: USDA price + adder, or the manual price as typed."""
        if self.wean_pig_source is WeanPigPriceSource.MANUAL:
            return self.wean_pig_manual_usd_hd
        usda = (
            self.wean_pig_usda_cash_usd_hd
            if self.wean_pig_source is WeanPigPriceSource.USDA_CASH
            else self.wean_pig_usda_formula_usd_hd
        )
        return usda + self.wean_pig_adder_usd_hd
