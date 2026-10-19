# PRD: Hog Projections

> **Status: DRAFT, waiting on the product idea from the owner.** The sections below hold
> research-informed placeholders (marked _TBD_). Once the idea arrives, this doc is rewritten and
> becomes the source of truth. Update it whenever the build deviates (see Changelog).

## 1. Problem
_TBD from the idea._ Research context (`docs/research/domain.md` §6):
- Hog producers and their lenders work from static university budgets with stale prices.
- No free tool connects USDA inventory → slaughter → price outlook → farm P&L.

## 2. Users
_TBD._ Candidates:
- Independent farrow-to-finish producer.
- Contract grower.
- Ag lender / loan officer.
- Market analyst.

Assumed: the primary user is non-technical and runs the app locally.

## 3. Goals / non-goals
- **Goals:** _TBD_
- **Non-goals (proposed):**
  - Real-time trading.
  - Paid data feeds.
  - Multi-user hosting / accounts.
  - Mobile app.

## 4. Features
_TBD._ The candidate menu from research:

| # | Feature | Notes |
|---|---|---|
| F1 | Herd-flow projection (weekly cohorts, sow → market) | biology defaults in domain.md §1 |
| F2 | Cost of production & breakeven per head / per cwt | ISU ELR / Missouri G688 structure |
| F3 | Market data: Lean Hog Index, cutout, corn/SBM | AMS MARS API, offline sample |
| F4 | Price outlook: futures + basis, seasonality | |
| F5 | Scenario & Monte Carlo risk (margin distribution) | |
| F6 | Hedge / LRP overlay | |
| F7 | Industry supply projection from NASS Hogs & Pigs | |
| F8 | Contract-grower vs independent comparison | |
| F9 | Excel / PDF export | |

## 5. Success criteria
_TBD._ Default bar:
- A fresh clone runs with a double-click on Windows and Mac.
- It works without API keys.
- Numbers reconcile with a published reference (e.g., ISU ELR month) within a stated tolerance.

## 6. Constraints
- Free data sources only.
- Python + Streamlit + uv (see `docs/decisions/0001-stack.md`).

## 7. Open questions
- What is the idea? Who is the user? Which outputs matter most?
- Which operation type comes first (farrow-to-finish, wean-to-finish, contract)?
- Does the user want hosted access (Streamlit Cloud), or local only?

## Changelog
- 2026-10-17: Draft skeleton created from research, before the product idea.
- 2026-10-19: F1 (herd flow) and F2 (cost/breakeven) built ahead of the idea; scope otherwise
  unchanged. Default prices now track Oct 2026 markets (corn $5.25, Lean Hog Index $75.75).
