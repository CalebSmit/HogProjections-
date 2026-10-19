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

## Phase 3 — Cost of production / breakeven / P&L ⏳
- [x] `finance.py`: CIH per-cwt cost structure, breakeven (carcass + live), sensitivity grid,
  weekly returns from herd marketings. verify: `tests/test_finance.py` reproduces the CIH formula
- [x] Costs & returns page. verify: page smoke test; checked in a browser
- [ ] Reconcile with an ISU ELR month within ±$2/head. The CIH shortcut gives ~$82.8/cwt
  breakeven at $5.25 corn vs ISU's "above $87" (Aug 2026), so this needs ISU's line-item
  structure (feed by phase + nonfeed) or a calibrated "other" cost. verify: fixture test

## Phase 4 — Market data ⏳
- [x] Keyless AMS LMR datamart client for LM_HG201 + cache + bundled 3-year sample.
  verify: `tests/test_markets.py` (fixture parse; live → cache → sample fallback; app runs offline)
- [x] Lean Hog Index rebuilt from HG201. verify: matches CME's published 75.75 for Oct 12, 2026
- [x] Market prices page (index, history, seasonality, carcass weight); Costs page defaults to
  the latest index. verify: smoke tests (forced offline) + browser check with live data
- [ ] Corn / SBM prices from My Market News (needs the owner's free `USDA_MMN_API_KEY`)
- [ ] NASS Hogs & Pigs inventory (needs `NASS_API_KEY`)

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
