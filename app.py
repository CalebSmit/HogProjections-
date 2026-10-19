"""Wean-to-finish group projection dashboard. Run with: uv run streamlit run app.py

State rule (Streamlit data_editor): an editor's *input* frame is fixed in session state and
never replaced by its own output. Replacing it changes the widget's identity and silently drops
the user's next edit. Reset buttons bump `ss.ver`, which is part of every editor key.
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from hogproj import __version__, charts
from hogproj.basis import (
    PERIODS,
    average_basis_by_period,
    basis_by_year_period,
    basis_period,
    lean_hog_contract_for,
    period_label,
)
from hogproj.data import defaults, profiles
from hogproj.data.market import (
    load_grain_futures,
    load_hog_basis_daily,
    load_hog_futures_curve,
    load_wean_pig_prices,
)
from hogproj.excel import build_workbook
from hogproj.inputs import (
    BarnCostMode,
    InterestMode,
    LaborCostMode,
    Location,
    MortalityMode,
    Projection,
    WeanPigPriceSource,
)
from hogproj.model import cash_flow, project, sensitivity
from hogproj.tables import (
    fill_curve,
    parse_basis,
    parse_cuts,
    parse_locations,
    parse_phases,
    parse_ration_lbs,
    ration_lbs_from_phases,
)

st.set_page_config(page_title="Hog Projections", page_icon="🐖", layout="wide")

# ---------------------------------------------------------------- cached market data


@st.cache_data(ttl=6 * 3600, show_spinner="Loading hog basis history…")
def hog_basis(refresh_token: int):
    return load_hog_basis_daily(years=12, refresh=refresh_token > 0)


@st.cache_data(ttl=6 * 3600, show_spinner="Loading futures…")
def hog_futures(codes: tuple[str, ...], refresh_token: int):
    return load_hog_futures_curve(list(codes))


@st.cache_data(ttl=6 * 3600, show_spinner="Loading grain futures…")
def grain_futures(refresh_token: int):
    return load_grain_futures()


@st.cache_data(ttl=6 * 3600, show_spinner="Loading USDA weaned pig report…")
def wean_prices(min_lot: int, refresh_token: int):
    return load_wean_pig_prices(min_lot)


def money(v: float, dec: int = 2) -> str:
    return f"-${abs(v):,.{dec}f}" if v < 0 else f"${v:,.{dec}f}"


def md_money(v: float, dec: int = 2) -> str:
    """money() for st.markdown/caption text, where a bare $ starts a LaTeX formula."""
    return money(v, dec).replace("$", r"\$")


def frame(models: list) -> pd.DataFrame:
    return pd.DataFrame([m.model_dump() for m in models])


def reset_inputs() -> None:
    start = defaults.default_projection(defaults.load_locations()[0])
    ss.phases_base = frame(start.feed_phases)
    ss.cuts_base = frame(start.marketing)
    ss.ration_base = ration_lbs_from_phases(start.feed_phases)
    ss.ver = ss.get("ver", 0) + 1


# ---------------------------------------------------------------- session state

ss = st.session_state
if "ver" not in ss:
    ss.refresh = 0
    ss.loc_base = frame(defaults.load_locations())
    ss.locations_ok = defaults.load_locations()
    ss.curve_base = dict(defaults.DEFAULT_LEAN_HOG_FUTURES_CWT)
    reset_inputs()
base = defaults.default_projection(ss.locations_ok[0])
problems: list[str] = []

st.title("Wean-to-Finish Group Projection")
header = st.empty()
tab_sum, tab_in, tab_loc, tab_mkt, tab_xl = st.tabs(
    ["📊 Summary", "⚙️ Inputs", "📍 Locations", "📈 Markets & basis", "⬇️ Excel"]
)

# ---------------------------------------------------------------- locations (read first)

with tab_loc:
    st.markdown(
        "Every location runs with the same group, feed budget and hog prices, so the "
        "difference is local feed prices, barn and labor."
    )
    comparison_slot = st.container()
    st.subheader("Edit locations")
    st.caption(
        "Corn basis in \\$/bu (−0.40 = 40¢ under futures). SBM basis = delivered premium over "
        "CBOT meal futures, \\$/ton. Add a row for a new location, or rename one for your own "
        "barn. **Save** keeps changes on this computer (in `data/user/`)."
    )
    edited_locs = st.data_editor(
        ss.loc_base,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "name": "Location",
            "state": "State",
            "corn_basis_usd_bu": st.column_config.NumberColumn("Corn basis $/bu", format="%.2f"),
            "sbm_basis_usd_ton": st.column_config.NumberColumn("SBM basis $/ton", format="%.0f"),
            "ddgs_usd_ton": st.column_config.NumberColumn("DDGS $/ton", format="%.0f"),
            "barn_rent_usd_space_yr": st.column_config.NumberColumn("Barn $/space/yr"),
            "labor_wage_usd_hr": st.column_config.NumberColumn("Wage $/hr", format="%.2f"),
            "source": st.column_config.TextColumn("Source / notes", width="large"),
        },
        key=f"loc_editor_{ss.ver}",
    )
    new_locs, loc_problems = parse_locations(edited_locs)
    if loc_problems:
        st.error("Not applied yet: " + " · ".join(loc_problems))
    else:
        old_names = [lo.name for lo in ss.locations_ok]
        new_names = [lo.name for lo in new_locs]
        if ss.get("loc_name") not in new_names and ss.get("loc_name") in old_names:
            i = old_names.index(ss.loc_name)
            if len(old_names) == len(new_names):  # a rename: follow the renamed row
                ss.loc_name = new_names[i]
        ss.locations_ok = new_locs
    b1, b2, _ = st.columns([1, 1, 4])
    if b1.button("💾 Save locations", disabled=bool(loc_problems)):
        defaults.save_locations(ss.locations_ok)
        st.toast("Locations saved on this computer.")
    if b2.button("↩️ Reset to defaults"):
        defaults.reset_locations()
        ss.loc_base = frame(defaults.load_locations())
        ss.locations_ok = defaults.load_locations()
        ss.ver += 1
        st.rerun()

locations: list[Location] = ss.locations_ok
loc_names = [lo.name for lo in locations]
if ss.get("loc_name") not in loc_names:
    ss.loc_name = loc_names[0]

# ---------------------------------------------------------------- settings & widgets

RATION_MODES = ["By phase (% inclusion)", "Whole-group ration (lb per pig)"]
ENUM_KEYS = {
    "in_source": WeanPigPriceSource,
    "in_barn_mode": BarnCostMode,
    "in_labor_mode": LaborCostMode,
    "in_mort_mode": MortalityMode,
    "in_interest_mode": InterestMode,
}
# Settings saved in a profile: costs, ration, toggles. Never market prices or dates.
SETTING_DEFAULTS: dict[str, object] = {
    "in_head_placed": 2400,
    "in_source": WeanPigPriceSource.USDA_CASH,
    "in_min_lot": 2400,
    "in_wean_adder": 0.0,
    "in_freight": base.wean_pig_freight_usd_hd,
    "in_wean_wt": base.wean_weight_lb,
    "in_mort_mode": MortalityMode.PCT_OF_HEAD,
    "in_mortality": base.mortality_pct,
    "in_mort_cost": 6.0,
    "in_dead_share": base.dead_feed_share,
    "in_yield": base.carcass_yield_pct,
    "in_feed_mill": base.feed_mill_usd_ton,
    "in_corn_carry": 0.0,
    "in_corn_hedge_pct": 0.0,
    "in_corn_hedged": 0.0,
    "in_sbm_hedge_pct": 0.0,
    "in_sbm_hedged": 0.0,
    "in_barn_mode": BarnCostMode.PER_SPACE_YEAR,
    "in_barn_per_pig": 18.0,
    "in_downtime": 10,
    "in_labor_mode": LaborCostMode.HOURLY,
    "in_labor_hr": base.labor_hr_per_pig,
    "in_labor_per_pig": 4.0,
    "in_vet": base.vet_med_usd_hd,
    "in_util": base.utilities_usd_hd,
    "in_truck": base.trucking_usd_hd_sold,
    "in_ins": base.insurance_misc_usd_hd,
    "in_ga": 0.0,
    "in_other_sold": 0.0,
    "in_interest_mode": InterestMode.RATE,
    "in_interest": base.interest_rate_pct,
    "in_interest_per_pig": 0.0,
    "in_checkoff": base.checkoff_pct,
    "in_premium": base.carcass_premium_cwt,
    "in_hog_hedge_pct": 0.0,
    "in_hog_hedged": 0.0,
    "in_principal": 0.0,
    "in_term_interest": 0.0,
    "in_ration_mode": RATION_MODES[0],
}
MARKET_DEFAULTS: dict[str, object] = {
    "in_corn_fut": base.corn_futures_usd_bu,
    "in_sbm_fut": base.sbm_futures_usd_ton,
    "in_wean_cash": defaults.DEFAULT_WEAN_PIG_USD_HD,
    "in_wean_formula": defaults.DEFAULT_WEAN_PIG_USD_HD,
    "in_wean_manual": defaults.DEFAULT_WEAN_PIG_USD_HD,
}
for k, v in {**SETTING_DEFAULTS, **MARKET_DEFAULTS}.items():
    ss.setdefault(k, v)
ss.setdefault("in_placement", date.today())


def apply_settings(settings: dict) -> None:
    """Load saved settings into widgets (runs in a button callback, before widgets exist)."""
    for k, v in settings.items():
        if k in SETTING_DEFAULTS:
            ss[k] = ENUM_KEYS[k](v) if k in ENUM_KEYS else v
    if "phases" in settings:
        ss.phases_base = pd.DataFrame(settings["phases"])
    if "ration" in settings:
        ss.ration_base = pd.DataFrame(settings["ration"])
    if "cuts" in settings:
        ss.cuts_base = pd.DataFrame(settings["cuts"])
    ss.ver += 1


def current_settings() -> dict:
    out = {k: (ss[k].value if k in ENUM_KEYS else ss[k]) for k in SETTING_DEFAULTS}
    out.update(ss.get("last_tables", {}))
    return out


def load_profile_cb() -> None:
    name = ss.get("profile_pick")
    if name:
        apply_settings(profiles.load_profile(name))
        ss.profile_msg = f"Loaded “{name}”."


def save_profile_cb() -> None:
    try:
        saved = profiles.save_profile(ss.get("profile_name", ""), current_settings())
    except ValueError as e:
        ss.profile_msg = str(e)
        return
    ss.profile_pick = saved
    ss.profile_msg = f"Saved “{saved}” on this computer."


def delete_profile_cb() -> None:
    name = ss.get("profile_pick")
    if name:
        profiles.delete_profile(name)
        ss.profile_msg = f"Deleted “{name}”."
        ss.profile_pick = None


def reset_all_cb() -> None:
    apply_settings({k: v for k, v in SETTING_DEFAULTS.items()})
    reset_inputs()


# ---------------------------------------------------------------- sidebar: the group

with st.sidebar:
    with st.expander("💾 Settings profiles", expanded=False):
        st.caption(
            "Save your own costs, ration and toggles (for example “My system 2026 Q2”). "
            "Profiles stay on this computer in `data/user/profiles/`; market prices aren't saved."
        )
        saved_profiles = profiles.list_profiles()
        st.selectbox(
            "Saved profiles",
            saved_profiles,
            index=None,
            key="profile_pick",
            placeholder="Choose a profile",
        )
        p1, p2 = st.columns(2)
        p1.button(
            "Load", on_click=load_profile_cb, use_container_width=True, disabled=not saved_profiles
        )
        p2.button(
            "Delete",
            on_click=delete_profile_cb,
            use_container_width=True,
            disabled=not saved_profiles,
        )
        st.text_input(
            "Save current settings as", key="profile_name", placeholder="e.g. My system 2026 Q2"
        )
        st.button("Save profile", on_click=save_profile_cb, use_container_width=True)
        if ss.get("profile_msg"):
            st.caption(ss.profile_msg)

    st.header("Group")
    loc_name = st.selectbox("Feeding location", loc_names, key="loc_name")
    head_placed = st.number_input("Head placed", 100, 20000, step=100, key="in_head_placed")
    placement = st.date_input("Placement date", key="in_placement")

    st.subheader("Weaned pig price")
    source = st.radio(
        "Price source",
        list(WeanPigPriceSource),
        format_func=lambda s: {
            WeanPigPriceSource.USDA_CASH: "USDA cash (open market)",
            WeanPigPriceSource.USDA_FORMULA: "USDA formula",
            WeanPigPriceSource.MANUAL: "Manual",
        }[s],
        key="in_source",
    )
    min_lot = st.selectbox(
        "USDA lot size",
        [2400, 1200, 600, 0],
        format_func=lambda n: f"{n:,}+ head" if n else "All lots",
        help="Uses this lot-size bucket if the report has it, otherwise the largest one.",
        key="in_min_lot",
    )
    wean = wean_prices(min_lot, ss.refresh)
    wean_df = wean.data if isinstance(wean.data, pd.DataFrame) else pd.DataFrame()
    if not wean_df.empty and ss.get("wean_token") != (ss.refresh, min_lot):
        cash_hist = wean_df["cash_usd_hd"].dropna()
        formula_hist = wean_df["formula_usd_hd"].dropna()
        if len(cash_hist):
            ss.in_wean_cash = round(float(cash_hist.iloc[-1]), 2)
        if len(formula_hist):
            ss.in_wean_formula = round(float(formula_hist.iloc[-1]), 2)
        ss.wean_token = (ss.refresh, min_lot)
    wean_cash = st.number_input("USDA cash $/head", step=0.5, key="in_wean_cash")
    wean_formula = st.number_input("USDA formula $/head", step=0.5, key="in_wean_formula")
    wean_adder = st.number_input(
        "Price adder over USDA $/head",
        step=0.5,
        key="in_wean_adder",
        help="Your system's premium over the USDA price. Added to USDA cash/formula, not Manual.",
    )
    wean_manual = st.number_input("Manual $/head", step=0.5, key="in_wean_manual")
    st.caption(wean.note)

    st.divider()
    if st.button("🔄 Refresh market data", use_container_width=True):
        ss.refresh += 1
        st.cache_data.clear()
        st.rerun()
    st.button("↩️ Reset inputs to defaults", use_container_width=True, on_click=reset_all_cb)

location = locations[loc_names.index(loc_name)]
header.caption(
    f"{head_placed:,} head placed at **{loc_name}** on {placement:%b %d, %Y}. "
    f"Costs and revenue from wean to market. v{__version__}"
)

# ---------------------------------------------------------------- market data

grain = grain_futures(ss.refresh)
grain_data = grain.data if isinstance(grain.data, dict) else {}
if grain_data and ss.get("grain_token") != ss.refresh:
    if "corn_usd_bu" in grain_data:
        ss.in_corn_fut = round(grain_data["corn_usd_bu"], 4)
    if "sbm_usd_ton" in grain_data:
        ss.in_sbm_fut = round(grain_data["sbm_usd_ton"], 2)
    ss.grain_token = ss.refresh
basis_loaded = hog_basis(ss.refresh)
basis_daily = basis_loaded.data if isinstance(basis_loaded.data, pd.Series) else pd.Series()
by_year = basis_by_year_period(basis_daily) if not basis_daily.empty else pd.DataFrame()
years_available = [int(y) for y in by_year.index] if not by_year.empty else []

# ---------------------------------------------------------------- inputs tab

with tab_in:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Feed prices")
        corn_fut = st.number_input(
            "CBOT corn futures $/bu", step=0.05, format="%.4f", key="in_corn_fut"
        )
        sbm_fut = st.number_input("CBOT soybean meal futures $/ton", step=1.0, key="in_sbm_fut")
        if not grain.live:
            st.caption(grain.note + " Defaults are Dec '26 settles on Oct 16, 2026.")
        else:
            st.caption(grain.note)
        corn_carry = st.number_input(
            "Corn carry / storage adder $/bu",
            step=0.05,
            key="in_corn_carry",
            help="Added to local cash corn, e.g. +$0.20 for carrying corn to feeding time.",
        )
        st.markdown(
            f"**{loc_name}**: corn "
            f"{md_money(corn_fut + location.corn_basis_usd_bu + corn_carry)}/bu "
            f"(basis {location.corn_basis_usd_bu * 100:+.0f}¢/bu) · SBM "
            f"{md_money(sbm_fut + location.sbm_basis_usd_ton)}/ton "
            f"(basis {md_money(location.sbm_basis_usd_ton, 0)}/ton) · "
            f"DDGS {md_money(location.ddgs_usd_ton)}/ton. Edit basis on the Locations tab."
        )
        feed_mill = st.number_input("Feed mill grind/mix/delivery $/ton", key="in_feed_mill")
    with c2:
        st.subheader("Production")
        wean_wt = st.number_input("Weaned pig weight (lb)", key="in_wean_wt")
        mort_mode = st.radio(
            "Mortality method",
            list(MortalityMode),
            horizontal=True,
            key="in_mort_mode",
            help="% of head: deads reduce pigs sold. $ per pig: a flat death-loss charge per "
            "pig placed (every pig placed is counted as sold).",
        )
        if mort_mode is MortalityMode.PCT_OF_HEAD:
            mortality = st.number_input(
                "Mortality wean to market (%)", step=0.5, max_value=99.0, key="in_mortality"
            )
            dead_share = st.slider(
                "Feed eaten by a dead pig (share of a full budget)",
                0.0,
                1.0,
                key="in_dead_share",
                help="Most W2F death loss is early, so a dead pig eats little feed.",
            )
            mort_cost = float(ss.in_mort_cost)
        else:
            mort_cost = st.number_input(
                "Mortality charge $/pig placed", step=0.25, key="in_mort_cost"
            )
            mortality, dead_share = float(ss.in_mortality), float(ss.in_dead_share)
        yield_pct = st.number_input("Carcass yield (%)", step=0.5, key="in_yield")
        freight = st.number_input("Weaned pig freight $/head", key="in_freight")
    with c3:
        st.subheader("Barn & labor")
        barn_mode = st.radio("Barn cost", list(BarnCostMode), horizontal=True, key="in_barn_mode")
        if barn_mode is BarnCostMode.PER_SPACE_YEAR:
            st.caption(f"{md_money(location.barn_rent_usd_space_yr)}/space/yr at {loc_name}.")
        barn_per_pig = st.number_input(
            "Barn / grower fee $/pig placed",
            disabled=barn_mode is BarnCostMode.PER_SPACE_YEAR,
            key="in_barn_per_pig",
            help="A grower fee often covers barn, labor and utilities: zero those out if so.",
        )
        downtime = st.number_input(
            "Barn downtime between groups (days)", min_value=0, key="in_downtime"
        )
        labor_mode = st.radio(
            "Labor cost", list(LaborCostMode), horizontal=True, key="in_labor_mode"
        )
        labor_hr = st.number_input(
            "Labor hours per pig",
            step=0.05,
            disabled=labor_mode is LaborCostMode.PER_PIG_PLACED,
            key="in_labor_hr",
        )
        labor_per_pig = st.number_input(
            "Labor $/pig placed",
            disabled=labor_mode is LaborCostMode.HOURLY,
            key="in_labor_per_pig",
        )
        st.caption(f"Wage at {loc_name}: {md_money(location.labor_wage_usd_hr)}/hr.")

    st.subheader("Other costs")
    o = st.columns(4)
    vet = o[0].number_input("Animal health / vet $/hd placed", key="in_vet")
    util = o[1].number_input("Utilities $/hd placed", key="in_util")
    truck = o[2].number_input("Freight out / trucking $/hd sold", key="in_truck")
    ins = o[3].number_input("Insurance / misc $/hd placed", key="in_ins")
    o = st.columns(4)
    ga = o[0].number_input("G&A $/hd placed", key="in_ga")
    other_sold = o[1].number_input(
        "Other / (sales premiums) $/hd sold",
        key="in_other_sold",
        help="Positive = extra cost; negative = premiums received.",
    )
    checkoff = o[2].number_input("Checkoff % of gross", key="in_checkoff")
    with o[3]:
        interest_mode = st.radio(
            "Operating interest", list(InterestMode), horizontal=True, key="in_interest_mode"
        )
        if interest_mode is InterestMode.RATE:
            interest = st.number_input(
                "Interest %/yr",
                key="in_interest",
                help="On pig cost + half of feed, for the days on feed.",
            )
            interest_per_pig = float(ss.in_interest_per_pig)
        else:
            interest_per_pig = st.number_input("Interest $/pig placed", key="in_interest_per_pig")
            interest = float(ss.in_interest)

    with st.expander("📈 Hedges & contracts", expanded=False):
        st.caption(
            "Share of the need that's hedged or contracted, at an all-in price. The rest pays "
            "the open market. Hogs: the futures level locked on the hedged share; basis still "
            "applies."
        )
        h = st.columns(3)
        corn_hedge_pct = h[0].number_input("Corn % hedged", 0.0, 100.0, key="in_corn_hedge_pct")
        corn_hedged = h[0].number_input("Corn hedged price $/bu", key="in_corn_hedged")
        sbm_hedge_pct = h[1].number_input("SBM % hedged", 0.0, 100.0, key="in_sbm_hedge_pct")
        sbm_hedged = h[1].number_input("SBM hedged price $/ton", key="in_sbm_hedged")
        hog_hedge_pct = h[2].number_input("Hogs % hedged", 0.0, 100.0, key="in_hog_hedge_pct")
        hog_hedged = h[2].number_input("Hog hedged futures $/cwt", key="in_hog_hedged")

    with st.expander("🏦 Debt service (below the operating margin)", expanded=False):
        st.caption("Principal and term-debt interest per pig sold, giving a second bottom line.")
        d = st.columns(2)
        principal = d[0].number_input("Principal payment $/hd sold", key="in_principal")
        term_interest = d[1].number_input("Term interest payment $/hd sold", key="in_term_interest")

    st.subheader("Feed budget")
    ration_mode = st.radio("Enter the ration", RATION_MODES, horizontal=True, key="in_ration_mode")
    if ration_mode == RATION_MODES[0]:
        st.caption(
            "Feed per pig marketed, by phase. Other % = premix, fat, amino acids and specialty "
            "ingredients, priced per ton of that portion."
        )
        phases_df = st.data_editor(
            ss.phases_base,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "name": "Phase",
                "feed_lb_per_pig": st.column_config.NumberColumn("Feed lb/pig", min_value=0),
                "corn_pct": st.column_config.NumberColumn("Corn %", min_value=0, max_value=100),
                "sbm_pct": st.column_config.NumberColumn("SBM %", min_value=0, max_value=100),
                "ddgs_pct": st.column_config.NumberColumn("DDGS %", min_value=0, max_value=100),
                "other_usd_ton": st.column_config.NumberColumn("Other $/ton", min_value=0),
            },
            key=f"phases_{ss.ver}",
        )
        phases, phase_problems = parse_phases(phases_df)
        ration_df = ss.ration_base
    else:
        st.caption("Pounds of each ingredient per pig marketed for the whole group.")
        ration_df = st.data_editor(
            ss.ration_base,
            hide_index=True,
            use_container_width=True,
            column_config={
                "corn_lb": st.column_config.NumberColumn("Corn lb/pig", min_value=0),
                "sbm_lb": st.column_config.NumberColumn("SBM lb/pig", min_value=0),
                "ddgs_lb": st.column_config.NumberColumn("DDGS lb/pig", min_value=0),
                "other_lb": st.column_config.NumberColumn("Other lb/pig", min_value=0),
                "other_usd_lb": st.column_config.NumberColumn("Other $/lb", format="%.4f"),
            },
            key=f"ration_{ss.ver}",
        )
        phases, phase_problems = parse_ration_lbs(ration_df)
        phases_df = ss.phases_base
    problems += phase_problems
    st.caption(f"Total feed: {sum(p.feed_lb_per_pig for p in phases):,.0f} lb per pig marketed.")

    st.subheader("Marketing (when the pigs sell)")
    st.caption(
        "Pigs sell 4 to 6 months after placement. Each cut is priced at the lean hog futures "
        "contract for its sale date plus the average historical basis for that half-month. "
        "For a single average sale (e.g. placement + 160 days), use one row at 100%."
    )
    cuts_df = st.data_editor(
        ss.cuts_base,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "days_after_placement": st.column_config.NumberColumn(
                "Days after placement", min_value=1, step=1
            ),
            "pct_of_marketed": st.column_config.NumberColumn(
                "% of pigs", min_value=0, max_value=100
            ),
            "live_weight_lb": st.column_config.NumberColumn("Live wt lb", min_value=1),
        },
        key=f"cuts_{ss.ver}",
    )
    cuts, cut_problems = parse_cuts(cuts_df)
    problems += cut_problems

ss.last_tables = {
    "phases": phases_df.to_dict("records"),
    "ration": ration_df.to_dict("records"),
    "cuts": cuts_df.to_dict("records"),
}

# ---------------------------------------------------------------- hog futures & basis

sale_dates = [placement + timedelta(days=c.days_after_placement) for c in cuts if c.pct_of_marketed]
needed = sorted({lean_hog_contract_for(d) for d in sale_dates})
live_curve = hog_futures(tuple(needed), ss.refresh)
if (
    isinstance(live_curve.data, dict)
    and live_curve.data
    and ss.get("curve_token")
    != (
        ss.refresh,
        tuple(needed),
    )
):
    ss.curve_base = {**ss.curve_base, **live_curve.data}
    ss.curve_token = (ss.refresh, tuple(needed))

with tab_in:
    st.subheader("Lean hog futures ($/cwt carcass)")
    curve_df = st.data_editor(
        pd.DataFrame({"contract": needed, "price_cwt": [ss.curve_base.get(c) for c in needed]}),
        disabled=["contract"],
        hide_index=True,
        column_config={
            "contract": "Contract (year-month)",
            "price_cwt": st.column_config.NumberColumn("Futures $/cwt", format="%.3f"),
        },
        key=f"curve_{ss.ver}_{ss.refresh}_{'_'.join(needed)}",
    )
    typed = {str(r["contract"]): r["price_cwt"] for r in curve_df.to_dict("records")}
    curve, filled = fill_curve({**ss.curve_base, **typed}, needed)
    st.caption(
        (live_curve.note + " " if live_curve.note else "")
        + "Typed prices reset if the sale months change."
    )
    if filled:
        st.warning(
            "No price for "
            + ", ".join(f"{c} (using {src})" for c, src in filled.items())
            + ". Type the real futures price above.",
            icon="⚠️",
        )

    st.subheader("Hog basis (CME Lean Hog Index − futures)")
    years = st.multiselect(
        "Years to average", years_available, default=years_available, key="basis_years"
    )
    hist_avg = average_basis_by_period(by_year, years) if years else {p: 0.0 for p in PERIODS}
    sale_periods = {basis_period(d) for d in sale_dates}
    st.caption(basis_loaded.note + " Type over any value; changing the years resets typed values.")
    basis_df = st.data_editor(
        pd.DataFrame(
            {
                "period": list(PERIODS),
                "half_month": [period_label(p) for p in PERIODS],
                "basis_cwt": [round(hist_avg[p], 2) for p in PERIODS],
                "used": ["✔ sale" if p in sale_periods else "" for p in PERIODS],
            }
        ),
        disabled=["period", "half_month", "used"],
        hide_index=True,
        column_config={
            "period": None,
            "half_month": "Half-month",
            "basis_cwt": st.column_config.NumberColumn("Avg basis $/cwt", format="%.2f"),
            "used": "Sales in",
        },
        key=f"basis_{ss.ver}_{ss.refresh}_{'_'.join(map(str, years))}",
        height=300,
    )
    basis_used = parse_basis(basis_df)
    premium = st.number_input("Carcass merit premium $/cwt", key="in_premium")

# ---------------------------------------------------------------- build the projection


def build(loc: Location) -> Projection:
    return Projection(
        head_placed=int(head_placed),
        placement_date=placement,
        wean_weight_lb=wean_wt,
        mortality_mode=mort_mode,
        mortality_pct=mortality,
        mortality_cost_usd_hd=mort_cost,
        dead_feed_share=dead_share,
        carcass_yield_pct=yield_pct,
        wean_pig_source=source,
        wean_pig_usda_cash_usd_hd=wean_cash,
        wean_pig_usda_formula_usd_hd=wean_formula,
        wean_pig_manual_usd_hd=wean_manual,
        wean_pig_adder_usd_hd=wean_adder,
        wean_pig_freight_usd_hd=freight,
        location=loc,
        corn_futures_usd_bu=corn_fut,
        sbm_futures_usd_ton=sbm_fut,
        feed_phases=phases,
        feed_mill_usd_ton=feed_mill,
        corn_carry_usd_bu=corn_carry,
        corn_hedged_pct=corn_hedge_pct,
        corn_hedged_usd_bu=corn_hedged,
        sbm_hedged_pct=sbm_hedge_pct,
        sbm_hedged_usd_ton=sbm_hedged,
        barn_mode=barn_mode,
        barn_usd_pig_placed=barn_per_pig,
        barn_downtime_days=int(downtime),
        labor_mode=labor_mode,
        labor_hr_per_pig=labor_hr,
        labor_usd_pig_placed=labor_per_pig,
        vet_med_usd_hd=vet,
        utilities_usd_hd=util,
        trucking_usd_hd_sold=truck,
        insurance_misc_usd_hd=ins,
        ga_usd_hd=ga,
        other_usd_hd_sold=other_sold,
        interest_mode=interest_mode,
        interest_rate_pct=interest,
        interest_usd_hd=interest_per_pig,
        principal_usd_hd=principal,
        term_interest_usd_hd=term_interest,
        marketing=cuts,
        lean_hog_futures_cwt=curve,
        hog_basis_cwt_by_period=basis_used,
        carcass_premium_cwt=premium,
        hog_hedged_pct=hog_hedge_pct,
        hog_hedged_cwt=hog_hedged,
        checkoff_pct=checkoff,
    )


if not needed and cuts:
    problems.append("At least one marketing row needs a % of pigs above 0.")
if needed and not curve:
    problems.append(f"Enter a lean hog futures price for {', '.join(needed)} (Inputs tab).")
proj: Projection | None = None
result = None
if not problems:
    try:
        proj = build(location)
        result = project(proj)
    except (ValidationError, KeyError, ValueError) as e:
        if isinstance(e, ValidationError):
            problems += [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
        else:
            problems.append(str(e.args[0]) if e.args else str(e))
if problems:
    with tab_sum:
        st.error(
            "**Can't run the projection yet.** Fix these on the Inputs or Locations tab:\n\n"
            + "\n".join(f"- {p}" for p in problems)
        )
    st.stop()
assert proj is not None and result is not None

s = result.summary

# ---------------------------------------------------------------- summary tab

with tab_sum:
    if basis_daily.empty:
        st.warning(
            "Hog basis history isn't loaded, so basis is 0 unless you entered it on the "
            "Inputs tab. Click **Refresh market data** with an internet connection.",
            icon="⚠️",
        )
    if filled:
        st.warning(
            "Some sales use a copied futures price: "
            + ", ".join(f"{c} ← {src}" for c, src in filled.items())
            + ". See Inputs → Lean hog futures.",
            icon="⚠️",
        )
    k = st.columns(5)
    k[0].metric("Net profit (group)", money(s["net_usd"], 0))
    k[1].metric("Net per head sold", money(s["net_usd_per_head_sold"]))
    k[2].metric(
        "Breakeven $/cwt carcass",
        money(s["breakeven_cwt_carcass"]),
        help=f"Live equivalent: {money(s['breakeven_cwt_live'])}/cwt",
    )
    k[3].metric("Cost per head sold", money(s["cost_usd_per_head_sold"]))
    k[4].metric("Revenue per head sold", money(s["revenue_usd_per_head_sold"]))
    if s["debt_service_usd"]:
        d = st.columns(5)
        d[0].metric("Debt service (group)", money(s["debt_service_usd"], 0))
        d[1].metric("Net per head after debt service", money(s["net_after_debt_usd_per_head_sold"]))
    avg_px = md_money(s["avg_price_cwt_carcass"])
    gap = md_money(abs(s["avg_price_cwt_carcass"] - s["breakeven_cwt_carcass"]))
    if s["net_usd"] >= 0:
        st.success(
            f"✅ **Projected profit.** Average sale price {avg_px}/cwt carcass is {gap} "
            "above breakeven."
        )
    else:
        st.error(
            f"🔻 **Projected loss.** Average sale price {avg_px}/cwt carcass is {gap} "
            "below breakeven."
        )

    left, right = st.columns([3, 2])
    with left:
        st.plotly_chart(charts.cost_breakdown(result.costs), use_container_width=True)
    with right:
        st.markdown("#### Key numbers")
        fc = s["feed_conversion"]
        st.dataframe(
            pd.DataFrame(
                {
                    "": [
                        "Head sold",
                        "Avg days on feed",
                        "Feed conversion",
                        "Weaned pig $/head",
                        "Corn cash $/bu",
                        "SBM cash $/ton",
                        "DDGS $/ton",
                        "Total cost",
                        "Total revenue",
                    ],
                    "Value": [
                        f"{s['head_sold']:,.0f}",
                        f"{s['avg_days_on_feed']:.0f}",
                        "n/a" if pd.isna(fc) else f"{fc:.2f}",
                        money(s["wean_pig_usd_hd"]),
                        money(s["corn_cash_usd_bu"]),
                        money(s["sbm_cash_usd_ton"]),
                        money(s["ddgs_usd_ton"]),
                        money(s["total_cost_usd"], 0),
                        money(s["gross_revenue_usd"], 0),
                    ],
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    st.markdown("#### Sales")
    m = result.marketing
    st.dataframe(
        pd.DataFrame(
            {
                "Sale date": pd.to_datetime(m["sale_date"]).dt.strftime("%b %d, %Y"),
                "Head": m["head"].round(0),
                "Live wt": m["live_weight_lb"],
                "Contract": m["contract"],
                "Futures $/cwt": m["futures_cwt"],
                "Basis $/cwt": m["basis_cwt"],
                "Premium": m["premium_cwt"],
                "Price $/cwt carcass": m["price_cwt_carcass"],
                "Revenue": m["revenue_usd"].map(lambda v: money(v, 0)),
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

    st.markdown("#### Cost detail")
    c = result.costs
    st.dataframe(
        pd.DataFrame(
            {
                "Cost line": c["line"],
                "Total": c["total_usd"].map(lambda v: money(v, 0)),
                "$/head placed": c["usd_per_head_placed"].map(money),
                "$/head sold": c["usd_per_head_sold"].map(money),
                "$/cwt carcass": c["usd_per_cwt_carcass"].map(money),
                "% of cost": c["pct_of_total"].map(lambda v: f"{v:.1f}%"),
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

    st.markdown("#### Cash flow by month")
    st.caption(
        "Weaned pigs and vet/med are paid at placement. Feed follows daily intake (heavier pigs "
        "eat more). Barn, labor and utilities are spread evenly. Sales, trucking and checkoff "
        "fall on each sale date; interest at closeout."
    )
    cf = cash_flow(proj, result)
    st.plotly_chart(charts.cash_flow_chart(cf), use_container_width=True)
    with st.expander("Monthly detail"):
        show = cf.copy()
        show["month"] = pd.to_datetime(show["month"]).dt.strftime("%b %Y")
        for col in [c for c in show.columns if c != "month"]:
            show[col] = show[col].map(lambda v: money(v, 0))
        st.dataframe(
            show.rename(
                columns={
                    "month": "Month",
                    "cash_out_usd": "Total cash out",
                    "cash_in_usd": "Cash in",
                    "net_usd": "Net",
                    "cumulative_usd": "Cumulative",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    grid = sensitivity(proj, [-0.50, -0.25, 0.0, 0.25, 0.50], [-10, -5, 0, 5, 10])
    st.plotly_chart(charts.sensitivity_heatmap(grid), use_container_width=True)

# ---------------------------------------------------------------- locations comparison

with comparison_slot:
    rows = []
    for lo in locations:
        r = project(build(lo)).summary
        rows.append(
            {
                "location": lo.name,
                "net_usd_per_head_sold": r["net_usd_per_head_sold"],
                "cost_usd_per_head_sold": r["cost_usd_per_head_sold"],
            }
        )
    st.plotly_chart(charts.net_by_location(pd.DataFrame(rows), loc_name), use_container_width=True)

# ---------------------------------------------------------------- markets tab

with tab_mkt:
    st.markdown(
        f"Local cash price = CBOT futures + basis. Corn futures {md_money(corn_fut)}/bu, "
        f"soybean meal futures {md_money(sbm_fut)}/ton."
    )
    loc_table = frame(locations).rename(columns={"name": "location"})
    a, b = st.columns(2)
    a.plotly_chart(
        charts.basis_bars(loc_table, "corn_basis_usd_bu", "Corn basis vs CBOT", "¢/bu", loc_name),
        use_container_width=True,
    )
    b.plotly_chart(
        charts.basis_bars(
            loc_table,
            "sbm_basis_usd_ton",
            "Soybean meal basis vs CBOT (delivered)",
            "$/ton",
            loc_name,
        ),
        use_container_width=True,
    )
    st.dataframe(
        pd.DataFrame(
            {
                "Location": loc_table["location"],
                "Corn cash $/bu": (corn_fut + loc_table["corn_basis_usd_bu"]).round(2),
                "SBM cash $/ton": (sbm_fut + loc_table["sbm_basis_usd_ton"]).round(2),
                "DDGS $/ton": loc_table["ddgs_usd_ton"],
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Hog basis history")
    if by_year.empty:
        st.info(basis_loaded.note)
    else:
        st.plotly_chart(
            charts.hog_basis_seasonal(by_year, years or years_available), use_container_width=True
        )
        st.caption(basis_loaded.note)
        with st.expander("Basis by year and half-month ($/cwt)"):
            st.dataframe(
                by_year.rename(columns={p: period_label(p) for p in PERIODS}).round(2),
                use_container_width=True,
            )

    st.subheader("USDA weaned pig prices")
    if wean_df.empty:
        st.info(wean.note)
    else:
        st.plotly_chart(
            charts.price_history(
                wean_df.dropna(subset=["cash_usd_hd"]),
                "date",
                "cash_usd_hd",
                "Early weaned pig, cash $/head",
                "$/head",
            ),
            use_container_width=True,
        )
        st.caption(wean.note)

# ---------------------------------------------------------------- excel tab

with tab_xl:
    st.markdown(
        "Download this projection as an Excel workbook. Yellow cells are inputs and every "
        "other number is a live formula, so you can change prices, location, feed budget or "
        "marketing in Excel and it recalculates."
    )
    try:
        xlsx = build_workbook(
            proj,
            locations,
            basis_history=by_year if not by_year.empty else None,
            wean_pig_history=wean_df if not wean_df.empty else None,
        )
    except ValueError as e:
        st.error(f"Couldn't build the workbook: {e}")
    else:
        st.download_button(
            "⬇️ Download Excel workbook",
            data=xlsx,
            file_name=f"W2F projection {loc_name} {placement:%Y-%m-%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
