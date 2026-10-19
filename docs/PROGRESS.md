# Progress log

Append-only. One entry per working session: what changed, what was verified, what's next.
Newest at the bottom.

---

## 2026-10-17 — Phase 0: foundation
- **Done:**
  - Researched the hog domain, the stack and the AI workflow (`docs/research/`).
  - Scaffolded the uv + Streamlit project, docs, skills, launchers and CI.
- **Verified:** `uv run pytest -q` → 2 passed; ruff + pyright clean; `run.sh` serves on :8501.
- **Notes:** Cloud sandbox can't reach usda.gov / iastate.edu / cmegroup.com directly.
- **Next:** Phase 1. Waiting on the owner's product idea.

## 2026-10-17/18 — Phases 1–5: W2F group projection
- **Done:**
  - Researched the owner's idea in 7 research passes: weaned pig report, regional feed
    prices and basis, barn/labor/costs, lean hog index and basis data (→ `docs/research/w2f-inputs.md`).
  - Built the model, half-month basis, Excel workbook, data clients, defaults and dashboard.
  - An independent review found 9 issues, all fixed:
    - roll-gap basis mismatch
    - silent index-bucket loss
    - offline hang
    - Excel truncation, stale location and text-cell issues
    - 0% cut needing a price
    - feed-conversion divide-by-zero
    - sensitivity label collisions
- **Verified:**
  - Tests green (`pytest`: model hand-calc, contract and roll gap, Excel parity in 4 scenarios
    via LibreOffice, parsers, fast-fail HTTP, app smoke offline).
  - ruff and pyright clean.
  - Screenshots of all tabs reviewed; fixed `$` being read as LaTeX in markdown, and basis
    chart label collisions.
- **Notes:**
  - Sandbox blocks the USDA, CME and Yahoo hosts, so live fetches are untested (PLAN Phase 4).
  - The USDA feeder pig report shows no 2,400+ lot bucket; the largest lot is used, with a
    notice (PRD open question 1).
- **Next:** Phase 4 live verification on a real machine, then Phase 6 (USDA grain basis pull,
  standalone workbook).

## 2026-10-18 — Second review pass (dashboard)
- **Done:** fixed 14 findings:
  - every other table edit dropped
  - a half-blank phase silently dropped
  - location editor rerun loop on NaN
  - offline error for placements after Oct 21 (missing contracts are now filled from the
    nearest contract, with a warning)
  - NaN basis turning numbers into "$nan" and crashing the Excel export
  - deleting every location crashed the app
  - renaming the selected location switched sites
  - a failed refresh discarded cached basis
  - `data/user/` not gitignored
  - typed futures reverting
  - vague error messages
  - hidden grain fetch reason
  - weaned-pig parser edge cases
  - Excel slot overflow
- **Verified:** 46 tests green. The 7 new regression tests drive the real app with editor
  edits; 6 of them fail on the previous app.py and pass now.
- **Next:** live data verification (PLAN Phase 4) on a machine with internet.

## 2026-10-19 — Phase 7: merged the owner's crush workbook
- **Done:**
  - Reviewed the owner's workbook; the app reproduced its margin column to the cent.
  - Model + Excel:
    - weaned pig price adder, corn carry, corn/SBM/hog hedges
    - mortality %/$ and interest rate/$ toggles
    - G&A and other/(premiums) lines
    - debt service, with net after debt service
  - Settings profiles (local only), whole-group ration mode.
  - Barchart import (both layouts, whole workbooks; the owner's file parsed correctly).
  - Exact-contract basis from imported contract histories.
  - Weekly crush tab and Excel sheet. ADR 0003.
- **Verified:**
  - 74 tests green: crush parity vs the workbook formulas, Excel crush parity, profile round
    trip, toggles, Barchart parsing.
  - Owner's file imported through the browser; weekly crush and Excel crush screenshots reviewed.
- **Notes:**
  - The ruff format hook's reformatting broke two string-replace edits (they silently didn't apply).
    Logged in CLAUDE.md.
- **Next:** independent review of Phase 7; live data check on a real machine (Phase 4).
