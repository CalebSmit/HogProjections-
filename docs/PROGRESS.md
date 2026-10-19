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

## 2026-10-19 — Third review (Phase 7 follow-up)
- **Done:**
  - Weekly crush leaves the group's hedges out (Python and Excel), since a hedge belongs to
    one group's sales, not to every weekly placement.
  - `build_weeks`: weeks after today use today's prices; an as-of price more than 10 days old
    is flagged; notes say what was used.
  - Barchart: corn cash and corn futures are separate kinds (cash skips location basis);
    grain eighths ("420-2") parse; cents convert on save; implausible values warned; the
    contract box is validated.
  - Exact-contract basis from imports now overlays the base basis history instead of replacing it.
  - App: a hedged % with no hedged price stops the projection with a clear message; a warning
    when a sale half-month has no basis history.
- **Verified:** 79 tests green (ruff, pyright clean). New tests cover future/stale crush weeks
  and the hedge-price check.
- **Next:** live data check on a real machine (Phase 4).

## 2026-10-19 — Phase 8: UI/UX pass
- **Done:**
  - Design system: theme in `.streamlit/config.toml`, bundled Inter (served from `static/`),
    tokens + components in `src/hogproj/ui.css`, HTML builders in `src/hogproj/ui.py`.
  - Header with context chips and a live/imported/offline data pill; hero card with the
    verdict and a price-vs-breakeven gauge; KPI cards; quiet notices instead of alert boxes.
  - Every tab regrouped into cards. Number columns use real number formats (right-aligned).
  - Crush sheet rendered as a financial table.
  - Charts: transparent on cards, Inter, currency ticks with a real minus, padded ranges.
  - Motion: staggered card rise, tab panel rise, hover lift, eased tab underline; the page no
    longer washes out while recalculating; all off under reduced motion.
  - Speed: rerun after an input change ~1.8 s → ~0.6 s (Excel built on click; cached
    comparison/sensitivity).
- **Verified:** 83 tests green; screenshots of all tabs at 1440 px and 390 px (no horizontal
  overflow, no console errors); Excel download checked in Chromium.
- **History question:** rewriting the branch history to drop the owner's figures from older
  commits was attempted and blocked by the session's safety check (force-push / history
  rewrite needs the owner's explicit go-ahead). Nothing was pushed.
- **Next:** live data check on a real machine (Phase 4).

## 2026-10-19 — Phase 9: second UI pass + workbook redesign
- **Done:**
  - Workbook: How to use sheet (steps, colour key, sheet links, terms, sources); Dashboard
    rebuilt (KPI tiles, plain-English verdict, P&L per head, key numbers, cost chart, live
    what-if grid); every sheet has a title band, Arial, blue-on-cream inputs with hover help,
    accounting formats (negatives in parentheses, zero as a dash), freeze panes, print headers
    and footers; Weekly Crush has sections, summary stats and a margin chart.
  - Results are named cells; tests read them by name, so layout can change safely.
  - Dashboard: plain-English summary, P&L statement, crush KPIs, location ranking, Guide tab,
    footer, print styles; crush results now sit above the editable weekly prices.
- **Verified:** 87 tests green (new: what-if grid = `model.sensitivity` across 6 parameter sets);
  workbook rendered to PDF via LibreOffice and reviewed page by page; app screenshots of every
  changed tab; no console errors; no horizontal overflow at 390 px; download checked.
- **Next:** live data check on a real machine (Phase 4).

## 2026-10-19 — Fourth review + laptop handoff
- **Done:**
  - `scripts/check_live.py` runs every live-data check (PLAN Phase 4) and can bundle the
    sample basis; `docs/NEXT-STEPS.md` is the checklist for a real machine.
  - Optional scenario name (header, Excel Dashboard, file name).
  - Independent review fixes: saved locations named "NA"/"None"/numbers no longer crash the
    app (and an unreadable file falls back with a notice); Excel location lookup is exact
    (no wildcards, case-sensitive) and case-only duplicate names are rejected; cash-corn crush
    fallback includes basis; a cleared weekly price is reported instead of crashing or
    vanishing; "Latest week" is the newest past report; the summary's sale window ignores 0%
    cuts; text inputs starting with "=" stay text in Excel; no cell has two validations;
    percent and whole-number inputs are range-checked in Excel.
  - Fresh-clone first run checked end to end (no imports, offline): renders, font served.
- **Verified:** full suite green; each fix has a regression test (the Excel lookup test fails
  on the old formula).
- **Next:** on a real machine, `uv run python scripts/check_live.py --write-sample`.
