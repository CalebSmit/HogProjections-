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

## 2026-10-19 (cont.) — Phase 3 closed: ISU line-item cost model
- **Done:** Replaced the CIH per-cwt shortcut with ISU ELR's per-pig line items (corn, SBM, other
  feed, nonfeed, death loss, manure credit); feed scales with market weight vs ISU's 270 lb.
  Costs page shows ISU-style table. Fixed "-$0" money formatting.
- **Verified:** all 9 published 2026 ISU months reproduce to the cent (fixture test); 42 tests
  pass; pyright clean; checked the page in Chrome.
- **Notes:** ISU publishes $/head, not feed quantities, so corn 10.2 bu/pig and SBM 104 lb/pig
  are estimates at ~$4 corn / $300 SBM [VERIFY]. The $5.25 corn default is futures; cash runs
  lower. Both get fixed with USDA cash prices once a My Market News key is in `.env`.

## 2026-10-19 (cont.) — Seasonal price path
- **Done:** `markets.seasonal_price_path`; Costs & returns can project at a seasonal or flat hog
  price, with a chart of the price used against breakeven.
- **Verified:** 45 tests pass, pyright clean; browser check. From $73.40 today the path reaches
  ~$67.9 in mid-December, near Dec 2026 futures (~$66.9).
- **Notes:** factors come from only 2 full years (2024–25); they firm up as history accrues.

## 2026-10-19 (cont.) — Overview dashboard + productivity-aware costs
- **Done:** Overview is now the home page (verdict, 4 cards with a price sparkline, 12-month
  outlook charts, "what moves your profit" tornado, key assumptions). Theme + minimal toolbar.
  `outlook.py` ties herd, costs and price path together. Smoke tests run pages via the router.
- **Bug found via the tornado:** +1 pig weaned/sow *lowered* profit because cost per pig was
  fixed. Added a sow-productivity adjustment from ISU farrow-to-wean ($43.91/weaned pig).
- **Verified:** 56 tests, pyright clean. Screenshots via Playwright + installed Edge (Chrome
  extension unavailable while the user's screen is locked).

## 2026-10-19 (cont.) — Scenarios, Risk, Excel report
- **Done:** Scenarios page (3 editable what-ifs vs current plan, 12/24 months); Risk page
  (2,000 seeded price years; hog AR(1) fitted to the de-seasonalized index: phi 0.95/wk,
  sigma 2.8%/wk; chance of profit, P10/P50/P90, fan chart, price-floor overlay); one-click
  Excel report on the Overview.
- **Verified:** 67 tests, pyright clean, screenshots of every new page.
- **Next:** grain prices + quantity calibration once the owner adds a My Market News key.

## 2026-10-19 (cont.) — Visual consistency pass
- **Done:** Herd flow gets a plain-English takeaway (when a herd change reaches market, as a
  date), bordered cards and date axes. Costs & returns and Market prices get the same card and
  panel styling; projection charts use dates; "-0%" share fixed.
- **Verified:** ruff, format, pyright clean; 67 tests; screenshots of all pages.
