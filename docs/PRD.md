# PRD: Wean-to-Finish Group Projection

> Source of truth for *what* we build and *why*. Update it in the same commit as any change in
> scope, and add a Changelog line.

## 1. Problem

A producer's accountant (Pipestone System) needs to know what a group of weaned pigs will cost
and earn from placement to market, before or right after placement. Today that means:
- University budgets with stale prices.
- Hand-gathered local feed prices.
- Guessing the hog price for sales 4–6 months out.

## 2. User

- **Primary:** an accounting person at Pipestone. Comfortable with Excel; not a programmer.
  Runs the app on their own laptop (Windows or Mac) by double-clicking a launcher.
- **Secondary:** producers and managers who read the dashboard or the Excel file.

## 3. Goals

| # | Goal |
|---|---|
| G1 | Project the **final costs, revenue and net** for one W2F group (default **2,400 head**), per head placed, per head sold, per cwt and in total. |
| G2 | Price feed from **local corn, soybean meal and DDGS** prices at the feeding location. Corn and SBM are CBOT futures plus local **basis**, shown against the futures ("market") price. |
| G3 | Default locations: **Northwest Iowa, Southwest Minnesota, Central South Dakota**, plus other Midwest locations. The user can edit all of them and add their own. |
| G4 | **Weaned pig price** from the weekly USDA report, **cash (open market) for large lots**, with a toggle for formula or a manual price. |
| G5 | **Barn** (rent $/space/yr or grower fee $/pig) and **labor** (hours × local wage, or $/pig) costs by location, from extension research. |
| G6 | **Hog revenue** = CME Lean Hog futures for each sale's contract + the **average historical basis** (CME Lean Hog Index − nearby futures, averaged across as many years as available) for that time of year. Pigs sell **4–6 months** after placement, in user-defined cuts. |
| G7 | An **easy-to-read dashboard** for the producer. |
| G8 | An **Excel workbook** with editable inputs and live formulas that reproduce the dashboard's numbers. |
| G9 | **Clone from GitHub and run** with no setup. Works offline with defaults and degrades visibly when data can't be fetched. |

## 4. Non-goals

- Farrow-to-finish / sow herd modelling.
- Multi-group, whole-system cash-flow scheduling.
- Hedging and LRP payoff overlays (candidate for later; see PLAN).
- User accounts or hosting.
- Paid data feeds.

## 5. Features (as built)

| ID | Feature | Status |
|---|---|---|
| F1 | Projection model: feed by phase, 10 cost lines, revenue per marketing cut, breakeven (carcass and live), feed conversion | ✅ |
| F2 | Contract mapping per ISU B2-41 (days 1–14 of a contract month use it, otherwise the next contract) | ✅ |
| F3 | Historical hog basis by **half-month** (24 periods), with year selection and manual override | ✅ |
| F4 | CME Lean Hog Index rebuilt from USDA LM_HG201 (keyless), with a coverage check | ✅ code; live run [VERIFY on a real machine] |
| F5 | USDA weaned pig report (2810): cash/formula, 2,400+ lot bucket or the largest available | ✅ code; needs a free USDA key; field names [VERIFY] |
| F6 | CBOT corn/SBM and lean hog futures from Yahoo (delayed) | ✅ code; [VERIFY] |
| F7 | 12 Midwest locations with sourced/estimated corn basis, SBM basis, DDGS, barn rent and wage; editable, saved to `data/user/` | ✅ |
| F8 | Dashboard: Summary, Inputs, Locations comparison, Markets & basis, Excel download | ✅ |
| F9 | Excel workbook with named-range formulas, dropdowns (location, weaned pig source, barn and labor mode), verified against the model by LibreOffice recalculation in tests | ✅ |
| F10 | Corn × hog price "what-if" grid | ✅ |
| F12 | Monthly cash flow (cash out by line, cash in by sale, cumulative) on the dashboard. Timing rules are in `model.cash_flow`. Dashboard only; the Excel workbook stays at the group-total level | ✅ |
| F13 | Crush-sheet inputs: weaned pig price adder; corn carry; corn/SBM/hog hedges; mortality as % of head or $/pig; interest as rate or $/pig; G&A; other/(sales premiums); debt service with net after debt service. Model + Excel | ✅ |
| F14 | **Settings profiles:** save/load named settings (costs, ration, toggles) on this computer only (`data/user/profiles/`, gitignored). This is how a company's own numbers are used without being committed | ✅ |
| F15 | Whole-group ration entry (lb per pig of each ingredient; other at $/lb), alongside phases | ✅ |
| F16 | **Barchart import** (CSV/Excel, both download layouts, whole workbooks). Used ahead of the USDA/Yahoo pulls; exact-contract hog basis when contract histories are imported | ✅ |
| F17 | **Weekly crush** tab: margin per pig for the last N + next M weekly placements (owner's layout), each week editable, using the full model and the group's settings (hedges excluded: they belong to one group's sales) | ✅ |
| F18 | Weekly Crush sheet in the Excel workbook (live formulas, parity-tested) | ✅ |
| F11 | Auto-pull regional corn/SBM basis and DDGS from USDA grain reports (2850 Iowa bids, 3618 co-products) | ⏳ Phase 5 |

## 6. Success criteria

1. On a fresh Windows or Mac machine, double-clicking the launcher opens the dashboard. No other steps.
2. With no network, the app shows a full projection from defaults, plus a visible notice.
3. Excel totals equal dashboard totals to within $0.01. Enforced by `tests/test_excel.py`.
4. Every default value has a source or an [ESTIMATE]/[VERIFY] tag (`docs/research/w2f-inputs.md`).
5. On a machine with internet access, Refresh pulls futures, the hog basis history and (with a key) the weaned pig price.

## 7. Open questions for the owner

1. **The 2,400-head lot bucket.** The USDA feeder pig report shows buckets of <600, 600–1,200 and >1,200 head. No 2,400+ bucket was found. The app uses 2,400+ if the report has it, otherwise the largest bucket, and says so. Is "over 1,200 head" acceptable?
2. **Grower fee vs owned barn.** Should the default be a Pipestone-style grower fee ($/pig placed, covering barn, labor and utilities) rather than rent plus hourly labor?
3. **Feed budget.** The default six-phase program is an industry-typical estimate. Can Pipestone's nutritionist provide the real phase lbs and inclusion rates?
4. **Merit premium** ($1.50/cwt) and **yield** (75%): use Pipestone's actual packer grid?

Answered 2026-10-19:
5. ~~Company figures in the repo?~~ **No.** The app is a template with generic defaults.
   Each user saves their own figures as a local settings profile (F14).
6. ~~Barchart?~~ **Both sources.** Barchart imports come first; free USDA/Yahoo pulls are the fallback (F16).
7. ~~Mortality?~~ **Both**, as a toggle. The default is % of head (fewer pigs sold); $/pig is
   available as the crush-sheet convention.

## Changelog
- 2026-10-17: Draft skeleton created from research, before the product idea.
- 2026-10-18: Rewritten for the owner's idea (W2F group projection). Scope, goals, features
  and open questions as above. Basis moved to half-month periods (from monthly) after
  research showed large within-month jumps at contract expiry.
- 2026-10-18: Added F12 monthly cash flow (for the accountant user).
- 2026-10-19: Reviewed the owner's crush workbook; added open questions 5–7. Merge plan is PLAN Phase 7.
- 2026-10-19: F17: the weekly crush leaves the group's hedges out (third review).
- 2026-10-19: The owner answered 5–7 (template with local profiles; both data sources; both
  mortality modes). Added F13–F18.
