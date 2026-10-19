# Build plan

> Source of truth for execution order. Phases ship one at a time. Every step has a
> `verify:` check, and a step is only ticked once its check passes. Re-plan freely, but
> edit this file (and its Changelog) when you do.

## Phase 0 — Foundation ✅
- [x] Research: domain, stack, workflow → `docs/research/`
- [x] Folder structure, CLAUDE.md, skills, reviewer agent
- [x] uv project, Streamlit stub, smoke test. verify: `uv run pytest -q` is green
- [x] Launchers for Windows, Mac and Linux. verify: `bash run.sh` serves on :8501
- [x] CI on Linux/Windows/macOS. verify: GitHub Actions green

## Phase 1 — Product definition ⏳ (blocked on the owner's idea)
- [ ] Receive the idea; deep research specific to it → `docs/research/`
- [ ] Rewrite `docs/PRD.md` (users, goals, features, success criteria)
- [ ] Finalize `docs/ARCHITECTURE.md` target and re-cut Phases 2+ below

## Phases 2+ — proposed, to be re-cut after Phase 1
Each phase ends with a usable app the recipient can run. Phases 2–3 were pulled ahead of
Phase 1 (2026-10-19) because every candidate idea in the PRD needs them.

## Phase 2 — Herd flow ✅
- [x] `herd.py`: weekly cohort model (sows → farrowings → weaned → marketed) with lags.
  verify: `tests/test_herd.py` (hand-calculated steady state, lag timing, head-count conservation)
- [x] Herd flow page with editable assumptions + CSV download. verify: page smoke test

## Phase 3 — Cost of production / breakeven / P&L ✅
- [x] `finance.py`: breakeven (carcass + live), sensitivity grid, weekly returns from herd
  marketings. Started on the CIH per-cwt shortcut; replaced by ISU's line items (see below).
- [x] Costs & returns page. verify: page smoke test; checked in a browser
- [x] Reconcile with ISU ELR within ±$2/head: cost model now uses ISU's farrow-to-finish line
  items (corn, SBM, other feed, nonfeed, death loss, manure credit). verify: all 9 published
  2026 months reproduce (cost ±$0.05, breakeven ±$0.03/cwt, profit ±$0.10) —
  `tests/fixtures/isu_f2f_2026.csv`

## Phase 4 — Market data ⏳
- [x] Keyless AMS LMR datamart client for LM_HG201 + cache + bundled 3-year sample.
  verify: `tests/test_markets.py` (fixture parse; live → cache → sample fallback; app runs offline)
- [x] Lean Hog Index rebuilt from HG201. verify: matches CME's published 75.75 for Oct 12, 2026
- [x] Market prices page (index, history, seasonality, carcass weight); Costs page defaults to
  the latest index. verify: smoke tests (forced offline) + browser check with live data
- [ ] Corn / SBM cash prices from My Market News NW_GR110/NW_GR116 (needs the owner's free
  `USDA_MMN_API_KEY`). Also calibrates corn bu/pig and SBM lb/pig against ISU's history
  (ISU publishes $/head, not quantities; current values are [VERIFY] estimates)
- [ ] NASS Hogs & Pigs inventory (needs `NASS_API_KEY`)

## Decision support (added 2026-10-19 for Pipestone users)
- [x] Overview dashboard: plain-English verdict, headline cards, 12-month price vs breakeven,
  profit by month, profit-driver tornado. verify: smoke test through the router; screenshot
- [x] Cost per pig responds to sow productivity (ISU farrow-to-wean $43.91/weaned pig spread
  over pigs sold per sow). verify: `test_more_pigs_per_sow_spreads_sow_costs`
- [ ] Scenarios page (compare what-ifs side by side)
- [ ] Risk page (probability of profit)
- [ ] Excel / PDF report for clients

## Phase 5 — Price outlook + scenarios ⏳ (started)
- [x] Seasonal hog price path for projected returns (monthly factors from USDA history,
  interpolated by day of year). verify: tests; Dec path ≈ $67.9 vs Dec futures ≈ $66.9
- [ ] Futures curve as the expected path (no free futures API; user-entered strip?)
- [ ] Scenarios + Monte Carlo margin distribution

| Phase | Deliverable | verify |
|---|---|---|
| 4 | Market data (AMS/NASS clients + cache + offline sample) | fixture tests; app runs with `OFFLINE=true` |
| 5 | Price outlook + scenarios + Monte Carlo | seeded snapshot tests; fan chart renders |
| 6 | Export (Excel) + polish + recipient docs | open workbook in tests; fresh-clone run on Win/Mac |

## Changelog
- 2026-10-17: Plan created; Phase 0 complete; Phases 2+ are placeholders pending the idea.
- 2026-10-19: Pulled Phases 2–3 ahead of Phase 1 (idea still pending; both are needed by every
  candidate feature). Phase 2 done; Phase 3 done except the ISU ELR reconciliation.
- 2026-10-19: Started Phase 4 with the keyless LMR datamart (hog prices); grain and inventory
  wait on the owner's free API keys.
- 2026-10-19: Phase 3 closed: cost model switched from the CIH shortcut to ISU's line items,
  which reproduce ISU's 2026 months to the cent.
