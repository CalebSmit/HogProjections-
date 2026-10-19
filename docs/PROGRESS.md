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

## 2026-10-19 — Phases 2–3: herd flow, costs & returns
- **Done:**
  - `herd.py`: weekly cohort herd flow with gestation/lactation/wean-to-market lags; starts in
    steady state; a herd change appears in farrowings after 16 wk and marketings after 41 wk.
  - `finance.py`: CIH per-cwt cost structure, breakeven ($/cwt carcass and live, $/head),
    margin sensitivity grid (hog × corn), weekly returns from herd marketings.
  - Pages: Herd flow, Costs & returns (heatmap, weekly + cumulative margin, CSV download).
    Router in `app.py` via `st.navigation`; pages moved to `views/`.
  - Defaults updated to Oct 2026 markets: corn $5.25 (Dec futures $5.23–5.50), Lean Hog Index
    $75.75 (Oct 12). SBM $300/ton is still the 2024 ISU budget value [VERIFY].
- **Verified:** ruff, ruff format, pyright (0 errors), pytest 17 passed on Windows. Clicked
  through all pages in Chrome: herd +500 sows at week 4 → weaning steps at wk 23, marketings
  at wk 45; inputs survive page switches.
- **Bugs found in the browser, fixed:** `$` rendered as LaTeX; "Sows after change" input
  silently projected a herd cut when "Sows today" was edited (now a +/− change input);
  inputs reset on page switch; "$-11.61" money formatting; misleading dual-axis chart.
- **Notes:** CIH breakeven (~$82.8/cwt carcass) runs below ISU's ">$87" for Aug 2026, so the
  "other costs" line ($44/cwt) likely understates current nonfeed costs.
- **Next:** ISU ELR reconciliation (Phase 3 last step); the owner's product idea (Phase 1);
  then market data (Phase 4) to replace typed-in prices.

## 2026-10-19 (cont.) — Phase 4 start: live hog prices, no key
- **Done:**
  - Found that USDA's LMR datamart serves LM_HG201 with no API key; 3 years load in ~8 s.
  - `data/ams.py` client with live → cache → bundled-sample fallback and a visible notice.
  - `markets.py`: Lean Hog Index rebuilt from HG201 (matches CME's 75.75 for Oct 12, 2026 to the
    cent) and monthly seasonal factors (Jul +11%, Jan −16% over 2024–25).
  - Market prices page; Costs page now defaults the hog price to the latest index.
- **Verified:** ruff, format, pyright 0 errors, pytest 27 passed (offline forced); browser check
  with live data (index $73.40 on Oct 15, −$3.11 on the week).
- **Next:** owner adds free USDA keys to `.env` → corn/SBM (My Market News) and Hogs & Pigs
  (NASS). ISU ELR reconciliation still open.
