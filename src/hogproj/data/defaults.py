"""Bundled default assumptions (data/defaults/) and the user's saved edits (data/user/).

Sources for every default are in docs/research/w2f-inputs.md. Values tagged [ESTIMATE] or
[VERIFY] there are editable in the dashboard and in Excel.
"""

from datetime import date

import pandas as pd

from hogproj.config import DATA_DIR
from hogproj.inputs import FeedPhase, Location, MarketingCut, Projection

DEFAULTS_DIR = DATA_DIR / "defaults"
USER_DIR = DATA_DIR / "user"
LOCATION_COLUMNS = list(Location.model_fields)

# Futures settles, Fri 2026-10-16 (Brownfield / Barchart closing reports).
DEFAULT_CORN_FUTURES_USD_BU = 4.7425  # CBOT Dec 2026 corn, 474.25 c/bu
DEFAULT_SBM_FUTURES_USD_TON = 357.10  # CBOT Dec 2026 soybean meal
DEFAULT_LEAN_HOG_FUTURES_CWT = {
    "2026-12": 66.925,
    "2027-02": 69.225,
    "2027-04": 74.675,
}
# USDA AMS National Direct Feeder Pig Report, early weaned composite, week of 2026-10-13,
# as reprinted by Manitoba Agriculture [VERIFY cash vs formula split].
DEFAULT_WEAN_PIG_USD_HD = 24.81


def load_locations() -> list[Location]:
    """User-saved locations if present, else the bundled Midwest list."""
    path = USER_DIR / "locations.csv"
    if not path.exists():
        path = DEFAULTS_DIR / "locations.csv"
    df = pd.read_csv(path).fillna({"state": "", "source": ""})
    return [Location(**rec) for rec in df.to_dict("records")]  # type: ignore[arg-type]


def save_locations(locations: list[Location]) -> None:
    USER_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([lo.model_dump() for lo in locations], columns=LOCATION_COLUMNS).to_csv(
        USER_DIR / "locations.csv", index=False
    )


def reset_locations() -> None:
    (USER_DIR / "locations.csv").unlink(missing_ok=True)


def load_feed_phases() -> list[FeedPhase]:
    df = pd.read_csv(DEFAULTS_DIR / "feed_phases.csv")
    return [FeedPhase(**rec) for rec in df.to_dict("records")]  # type: ignore[arg-type]


def default_marketing() -> list[MarketingCut]:
    # W2F ADG ~1.72 lb/day from 12 lb (MetaFarms/NPB 2024): ~270 lb at day 145, ~290 by 175.
    return [
        MarketingCut(days_after_placement=145, pct_of_marketed=20, live_weight_lb=270),
        MarketingCut(days_after_placement=160, pct_of_marketed=40, live_weight_lb=285),
        MarketingCut(days_after_placement=175, pct_of_marketed=40, live_weight_lb=290),
    ]


def default_projection(location: Location, placement_date: date | None = None) -> Projection:
    return Projection(
        head_placed=2400,
        placement_date=placement_date or date.today(),
        wean_weight_lb=12.0,  # ISU FM1815 "finishing weaned 12-lb pigs"
        mortality_pct=6.8,  # MetaFarms/NPB single-stocked W2F 2024 (6.81%)
        dead_feed_share=0.25,  # [ESTIMATE] most W2F deaths are early
        carcass_yield_pct=75.0,  # LM_HG201 2025 sample days 74.1-75.3%
        wean_pig_usda_cash_usd_hd=DEFAULT_WEAN_PIG_USD_HD,
        wean_pig_usda_formula_usd_hd=DEFAULT_WEAN_PIG_USD_HD,
        wean_pig_manual_usd_hd=DEFAULT_WEAN_PIG_USD_HD,
        wean_pig_freight_usd_hd=1.00,  # [ESTIMATE]
        location=location,
        corn_futures_usd_bu=DEFAULT_CORN_FUTURES_USD_BU,
        sbm_futures_usd_ton=DEFAULT_SBM_FUTURES_USD_TON,
        feed_phases=load_feed_phases(),
        feed_mill_usd_ton=15.0,  # [ESTIMATE] grind/mix/delivery
        barn_downtime_days=10,  # [ESTIMATE] wash/dry/fill
        labor_hr_per_pig=0.20,  # [ESTIMATE] modern tunnel W2F; ISU budgets use 0.5
        vet_med_usd_hd=5.00,  # [ESTIMATE]
        utilities_usd_hd=4.00,  # [ESTIMATE] LP + electric
        trucking_usd_hd_sold=4.00,  # [ESTIMATE]
        insurance_misc_usd_hd=0.50,  # [ESTIMATE]
        interest_rate_pct=7.12,  # Chicago Fed AgLetter, operating loans Q2 2026
        marketing=default_marketing(),
        lean_hog_futures_cwt=dict(DEFAULT_LEAN_HOG_FUTURES_CWT),
        hog_basis_cwt_by_period={},  # filled from history at runtime
        carcass_premium_cwt=1.50,  # LM_HG201 net minus base, 2025 sample days [VERIFY]
        checkoff_pct=0.35,  # National Pork Checkoff, statutory
    )
