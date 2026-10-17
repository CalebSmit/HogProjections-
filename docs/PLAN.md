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
Each phase ends with a usable app the recipient can run.

| Phase | Deliverable | verify |
|---|---|---|
| 2 | Herd-flow model + assumptions page | head-count conservation tests; matches hand-calculated example |
| 3 | Cost of production / breakeven / P&L | reproduces an ISU ELR month within ±$2/head |
| 4 | Market data (AMS/NASS clients + cache + offline sample) | fixture tests; app runs with `OFFLINE=true` |
| 5 | Price outlook + scenarios + Monte Carlo | seeded snapshot tests; fan chart renders |
| 6 | Export (Excel) + polish + recipient docs | open workbook in tests; fresh-clone run on Win/Mac |

## Changelog
- 2026-10-17: Plan created; Phase 0 complete; Phases 2+ are placeholders pending the idea.
