"""Wean-to-finish group projection dashboard. Run with: uv run streamlit run app.py"""

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
from hogproj.data import defaults
from hogproj.data.market import (
    load_grain_futures,
    load_hog_basis_daily,
    load_hog_futures_curve,
    load_wean_pig_prices,
)
from hogproj.excel import build_workbook
from hogproj.inputs import (
    BarnCostMode,
    FeedPhase,
    LaborCostMode,
    Location,
    MarketingCut,
    Projection,
    WeanPigPriceSource,
)
from hogproj.model import cash_flow, project, sensitivity

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


# ---------------------------------------------------------------- session defaults

ss = st.session_state
if "locations" not in ss:
    ss.locations = defaults.load_locations()
    ss.refresh = 0
    start = defaults.default_projection(ss.locations[0])
    ss.phases = pd.DataFrame([ph.model_dump() for ph in start.feed_phases])
    ss.cuts = pd.DataFrame([c.model_dump() for c in start.marketing])
    ss.hog_futures = dict(start.lean_hog_futures_cwt)
    ss.base = start
base: Projection = ss.base
locations: list[Location] = ss.locations
loc_names = [lo.name for lo in locations]

# ---------------------------------------------------------------- sidebar: the group

with st.sidebar:
    st.header("Group")
    loc_name = st.selectbox("Feeding location", loc_names, key="loc_name")
    head_placed = st.number_input("Head placed", 100, 20000, 2400, step=100)
    placement = st.date_input("Placement date", value=date.today())

    st.subheader("Weaned pig price")
    source = st.radio(
        "Price source",
        list(WeanPigPriceSource),
        format_func=lambda s: {
            WeanPigPriceSource.USDA_CASH: "USDA cash (open market)",
            WeanPigPriceSource.USDA_FORMULA: "USDA formula",
            WeanPigPriceSource.MANUAL: "Manual",
        }[s],
    )
    min_lot = st.selectbox(
        "USDA lot size",
        [2400, 1200, 600, 0],
        format_func=lambda n: f"{n:,}+ head" if n else "All lots",
        help="Uses this lot-size bucket if the report has it, otherwise the largest one.",
    )
    wean = wean_prices(min_lot, ss.refresh)
    latest_cash = latest_formula = defaults.DEFAULT_WEAN_PIG_USD_HD
    wean_df = wean.data if isinstance(wean.data, pd.DataFrame) else pd.DataFrame()
    if not wean_df.empty:
        cash_hist = wean_df["cash_usd_hd"].dropna()
        formula_hist = wean_df["formula_usd_hd"].dropna()
        latest_cash = float(cash_hist.iloc[-1]) if len(cash_hist) else latest_cash
        latest_formula = float(formula_hist.iloc[-1]) if len(formula_hist) else latest_formula
    wean_cash = st.number_input("USDA cash $/head", value=round(latest_cash, 2), step=0.5)
    wean_formula = st.number_input("USDA formula $/head", value=round(latest_formula, 2), step=0.5)
    wean_manual = st.number_input("Manual $/head", value=defaults.DEFAULT_WEAN_PIG_USD_HD, step=0.5)
    st.caption(wean.note)

    st.divider()
    if st.button("🔄 Refresh market data", use_container_width=True):
        ss.refresh += 1
        st.cache_data.clear()
        st.rerun()

location = locations[loc_names.index(loc_name)]

# ---------------------------------------------------------------- market data

grain = grain_futures(ss.refresh)
grain_data = grain.data if isinstance(grain.data, dict) else {}
basis_loaded = hog_basis(ss.refresh)
basis_daily = basis_loaded.data if isinstance(basis_loaded.data, pd.Series) else pd.Series()
by_year = basis_by_year_period(basis_daily) if not basis_daily.empty else pd.DataFrame()
years_available = [int(y) for y in by_year.index] if not by_year.empty else []

st.title("Wean-to-Finish Group Projection")
st.caption(
    f"{head_placed:,} head placed at **{loc_name}** on {placement:%b %d, %Y}. "
    f"Costs and revenue from wean to market. v{__version__}"
)

tab_sum, tab_in, tab_loc, tab_mkt, tab_xl = st.tabs(
    ["📊 Summary", "⚙️ Inputs", "📍 Locations", "📈 Markets & basis", "⬇️ Excel"]
)

# ---------------------------------------------------------------- inputs tab

with tab_in:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Feed prices")
        corn_fut = st.number_input(
            "CBOT corn futures $/bu",
            value=round(grain_data.get("corn_usd_bu", base.corn_futures_usd_bu), 4),
            step=0.05,
            format="%.4f",
        )
        sbm_fut = st.number_input(
            "CBOT soybean meal futures $/ton",
            value=round(grain_data.get("sbm_usd_ton", base.sbm_futures_usd_ton), 2),
            step=1.0,
        )
        st.caption(grain.note if grain.live else "Defaults: Dec '26 settles on Oct 16, 2026.")
        st.markdown(
            f"**{loc_name}**: corn {md_money(corn_fut + location.corn_basis_usd_bu)}/bu "
            f"(basis {location.corn_basis_usd_bu * 100:+.0f}¢) · SBM "
            f"{md_money(sbm_fut + location.sbm_basis_usd_ton)}/ton "
            f"(basis {location.sbm_basis_usd_ton:+.0f}) · "
            f"DDGS {md_money(location.ddgs_usd_ton)}/ton. Edit basis on the Locations tab."
        )
        feed_mill = st.number_input(
            "Feed mill grind/mix/delivery $/ton", value=base.feed_mill_usd_ton
        )
    with c2:
        st.subheader("Production")
        wean_wt = st.number_input("Weaned pig weight (lb)", value=base.wean_weight_lb)
        mortality = st.number_input(
            "Mortality wean to market (%)", value=base.mortality_pct, step=0.5
        )
        dead_share = st.slider(
            "Feed eaten by a dead pig (share of a full budget)",
            0.0,
            1.0,
            base.dead_feed_share,
            help="Most W2F death loss is early, so a dead pig eats little feed.",
        )
        yield_pct = st.number_input("Carcass yield (%)", value=base.carcass_yield_pct, step=0.5)
        freight = st.number_input("Weaned pig freight $/head", value=base.wean_pig_freight_usd_hd)
    with c3:
        st.subheader("Barn & labor")
        barn_mode = st.radio("Barn cost", list(BarnCostMode), horizontal=True)
        if barn_mode is BarnCostMode.PER_SPACE_YEAR:
            st.caption(f"{md_money(location.barn_rent_usd_space_yr)}/space/yr at {loc_name}.")
        barn_per_pig = st.number_input(
            "Barn / grower fee $/pig placed",
            value=18.0,
            disabled=barn_mode is BarnCostMode.PER_SPACE_YEAR,
        )
        downtime = st.number_input("Barn downtime between groups (days)", value=10, min_value=0)
        labor_mode = st.radio("Labor cost", list(LaborCostMode), horizontal=True)
        labor_hr = st.number_input(
            "Labor hours per pig",
            value=base.labor_hr_per_pig,
            step=0.05,
            disabled=labor_mode is LaborCostMode.PER_PIG_PLACED,
        )
        labor_per_pig = st.number_input(
            "Labor $/pig placed", value=4.0, disabled=labor_mode is LaborCostMode.HOURLY
        )
        st.caption(f"Wage at {loc_name}: {md_money(location.labor_wage_usd_hr)}/hr.")

    st.subheader("Other costs")
    o1, o2, o3, o4, o5, o6 = st.columns(6)
    vet = o1.number_input("Vet/med $/hd", value=base.vet_med_usd_hd)
    util = o2.number_input("Utilities $/hd", value=base.utilities_usd_hd)
    truck = o3.number_input("Trucking $/hd sold", value=base.trucking_usd_hd_sold)
    ins = o4.number_input("Insurance/misc $/hd", value=base.insurance_misc_usd_hd)
    interest = o5.number_input("Interest %/yr", value=base.interest_rate_pct)
    checkoff = o6.number_input("Checkoff % of gross", value=base.checkoff_pct)

    st.subheader("Feed budget by phase")
    st.caption(
        "Feed per pig marketed. Other % = premix, fat, amino acids and specialty ingredients, "
        "priced per ton of that portion."
    )
    ss.phases = st.data_editor(
        ss.phases,
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
        key="phases_editor",
    )
    st.caption(f"Total feed: {ss.phases['feed_lb_per_pig'].sum():,.0f} lb per pig marketed.")

    st.subheader("Marketing (when the pigs sell)")
    st.caption(
        "Pigs sell 4 to 6 months after placement. Each cut is priced at the lean hog futures "
        "contract for its sale date plus the average historical basis for that half-month."
    )
    ss.cuts = st.data_editor(
        ss.cuts,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "days_after_placement": st.column_config.NumberColumn(
                "Days after placement", min_value=1
            ),
            "pct_of_marketed": st.column_config.NumberColumn(
                "% of pigs", min_value=0, max_value=100
            ),
            "live_weight_lb": st.column_config.NumberColumn("Live wt lb", min_value=1),
        },
        key="cuts_editor",
    )

# ---------------------------------------------------------------- hog futures & basis inputs

cuts_clean = ss.cuts.dropna()
needed = sorted(
    {
        lean_hog_contract_for(placement + timedelta(days=int(d)))
        for d in cuts_clean["days_after_placement"]
    }
)
live_curve = hog_futures(tuple(needed), ss.refresh)
if isinstance(live_curve.data, dict):
    for k, v in live_curve.data.items():
        ss.hog_futures[k] = v

with tab_in:
    st.subheader("Lean hog futures ($/cwt carcass)")
    curve_df = pd.DataFrame(
        {"contract": needed, "price_cwt": [ss.hog_futures.get(c) for c in needed]}
    )
    edited_curve = st.data_editor(
        curve_df,
        disabled=["contract"],
        hide_index=True,
        column_config={
            "contract": "Contract (year-month)",
            "price_cwt": st.column_config.NumberColumn("Futures $/cwt", format="%.3f"),
        },
        key=f"curve_{'_'.join(needed)}",
    )
    for rec in edited_curve.to_dict("records"):
        if pd.notna(rec["price_cwt"]):
            ss.hog_futures[str(rec["contract"])] = float(rec["price_cwt"])
    st.caption(live_curve.note if live_curve.note else "")
    missing = [c for c in needed if c not in ss.hog_futures]

    st.subheader("Hog basis (CME Lean Hog Index − futures)")
    years = st.multiselect(
        "Years to average", years_available, default=years_available, key="basis_years"
    )
    hist_avg = average_basis_by_period(by_year, years) if years else {p: 0.0 for p in PERIODS}
    sale_periods = sorted(
        {
            basis_period(placement + timedelta(days=int(d)))
            for d in cuts_clean["days_after_placement"]
        }
    )
    basis_df = pd.DataFrame(
        {
            "period": list(PERIODS),
            "half_month": [period_label(p) for p in PERIODS],
            "basis_cwt": [round(hist_avg[p], 2) for p in PERIODS],
            "used": ["✔ sale" if p in sale_periods else "" for p in PERIODS],
        }
    )
    st.caption(basis_loaded.note + " You can type over any value.")
    edited_basis = st.data_editor(
        basis_df,
        disabled=["period", "half_month", "used"],
        hide_index=True,
        column_config={
            "period": None,
            "half_month": "Half-month",
            "basis_cwt": st.column_config.NumberColumn("Avg basis $/cwt", format="%.2f"),
            "used": "Sales in",
        },
        key=f"basis_{'_'.join(map(str, years))}_{ss.refresh}",
        height=300,
    )
    basis_used = {
        int(r["period"]): float(r["basis_cwt"] or 0) for r in edited_basis.to_dict("records")
    }
    premium = st.number_input("Carcass merit premium $/cwt", value=base.carcass_premium_cwt)

# ---------------------------------------------------------------- build the projection


def build(loc: Location) -> Projection:
    return Projection(
        head_placed=int(head_placed),
        placement_date=placement,
        wean_weight_lb=wean_wt,
        mortality_pct=mortality,
        dead_feed_share=dead_share,
        carcass_yield_pct=yield_pct,
        wean_pig_source=source,
        wean_pig_usda_cash_usd_hd=wean_cash,
        wean_pig_usda_formula_usd_hd=wean_formula,
        wean_pig_manual_usd_hd=wean_manual,
        wean_pig_freight_usd_hd=freight,
        location=loc,
        corn_futures_usd_bu=corn_fut,
        sbm_futures_usd_ton=sbm_fut,
        feed_phases=[FeedPhase(**r) for r in ss.phases.dropna().to_dict("records")],  # type: ignore[arg-type]
        feed_mill_usd_ton=feed_mill,
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
        interest_rate_pct=interest,
        marketing=[
            MarketingCut(
                **{k: (int(v) if k == "days_after_placement" else v) for k, v in r.items()}
            )  # type: ignore[arg-type]
            for r in cuts_clean.to_dict("records")
        ],
        lean_hog_futures_cwt=dict(ss.hog_futures),
        hog_basis_cwt_by_period=basis_used,
        carcass_premium_cwt=premium,
        checkoff_pct=checkoff,
    )


try:
    proj = build(location)
    result = project(proj)
except (ValidationError, KeyError, ValueError) as e:
    msg = str(e)
    if isinstance(e, ValidationError):
        msg = "; ".join(err["msg"] for err in e.errors())
    with tab_sum:
        if missing:
            st.error(f"Enter a lean hog futures price for: {', '.join(missing)} (Inputs tab).")
        st.error(f"Can't run the projection yet: {msg}")
    st.stop()

s = result.summary

# ---------------------------------------------------------------- summary tab

with tab_sum:
    if basis_daily.empty:
        st.warning(
            "Hog basis history isn't loaded, so basis is 0 unless you entered it on the "
            "Inputs tab. Click **Refresh market data** with an internet connection.",
            icon="⚠️",
        )
    profit = s["net_usd"] >= 0
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
    avg_px = md_money(s["avg_price_cwt_carcass"])
    gap = md_money(abs(s["avg_price_cwt_carcass"] - s["breakeven_cwt_carcass"]))
    if profit:
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
        money_cols = [c for c in show.columns if c != "month"]
        for col in money_cols:
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

# ---------------------------------------------------------------- locations tab

with tab_loc:
    st.markdown(
        "Every location runs with the same group, feed budget and hog prices, so the "
        "difference is local feed prices, barn and labor."
    )
    rows = []
    for lo in locations:
        r = project(build(lo)).summary
        rows.append(
            {
                "location": lo.name,
                "net_usd_per_head_sold": r["net_usd_per_head_sold"],
                "cost_usd_per_head_sold": r["cost_usd_per_head_sold"],
                "feed_cost_usd_per_head_sold": r["feed_cost_usd_per_head_sold"],
                "breakeven_cwt_carcass": r["breakeven_cwt_carcass"],
            }
        )
    comp = pd.DataFrame(rows)
    st.plotly_chart(charts.net_by_location(comp, loc_name), use_container_width=True)

    st.subheader("Edit locations")
    st.caption(
        "Corn basis in \\$/bu (−0.40 = 40¢ under futures). SBM basis = delivered premium over "
        "CBOT meal futures, \\$/ton. Add a row for a new location. Changes apply right away; "
        "**Save** keeps them for next time."
    )
    loc_df = pd.DataFrame([lo.model_dump() for lo in locations])
    edited_locs = st.data_editor(
        loc_df,
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
        key="loc_editor",
    )
    b1, b2, _ = st.columns([1, 1, 4])
    try:
        new_locs = [
            Location.model_validate(
                {k: ("" if pd.isna(v) and k in ("state", "source") else v) for k, v in r.items()}
            )
            for r in edited_locs.dropna(subset=["name"]).to_dict("records")
        ]
    except ValidationError:
        new_locs = None
        st.error("Fill in every number for each location before it can be used.")
    if new_locs is not None and [lo.model_dump() for lo in new_locs] != [
        lo.model_dump() for lo in locations
    ]:
        ss.locations = new_locs
        st.rerun()
    if b1.button("💾 Save locations"):
        defaults.save_locations(ss.locations)
        st.toast("Locations saved.")
    if b2.button("↩️ Reset to defaults"):
        defaults.reset_locations()
        ss.locations = defaults.load_locations()
        st.rerun()

# ---------------------------------------------------------------- markets tab

with tab_mkt:
    st.markdown(
        f"Local cash price = CBOT futures + basis. Corn futures {md_money(corn_fut)}/bu, "
        f"soybean meal futures {md_money(sbm_fut)}/ton."
    )
    loc_table = pd.DataFrame([lo.model_dump() for lo in locations]).rename(
        columns={"name": "location"}
    )
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
    cash_tbl = pd.DataFrame(
        {
            "Location": loc_table["location"],
            "Corn cash $/bu": (corn_fut + loc_table["corn_basis_usd_bu"]).round(2),
            "SBM cash $/ton": (sbm_fut + loc_table["sbm_basis_usd_ton"]).round(2),
            "DDGS $/ton": loc_table["ddgs_usd_ton"],
        }
    )
    st.dataframe(cash_tbl, hide_index=True, use_container_width=True)

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
    xlsx = build_workbook(
        proj,
        locations,
        basis_history=by_year if not by_year.empty else None,
        wean_pig_history=wean_df if not wean_df.empty else None,
    )
    st.download_button(
        "⬇️ Download Excel workbook",
        data=xlsx,
        file_name=f"W2F projection {loc_name} {placement:%Y-%m-%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
