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
- **Review fixes:** verdict now follows profit (incl. manure credit), with a third "profitable
  only thanks to the manure credit" case; months are ranked and charted per pig sold (months
  have 4 or 5 sale weeks and the first is partial), and the Excel Monthly sheet flags it.

## 2026-10-19 (cont.) — Premium redesign
- **Why:** owner feedback that the app "looks made by an AI, not premium"; it will be used by
  Pipestone and shown to clients.
- **Done:** research brief (Stripe/Linear/Carbon/Datawrapper/NN/g + Streamlit 1.66 theming) →
  design system (ADR 0002, `docs/DESIGN.md`): Inter + system fallback, neutral palette with one
  navy accent, CVD-checked profit/loss colours, Material-icon nav, logo, page header with data
  freshness chip, takeaway cards with key facts, white cards, house Plotly template (no toolbar,
  hairline grid, true minus signs), clean comparison tables. All six pages rebuilt; Excel report
  uses the same brand. README gets a screenshot and feature table.
- **Bugs caught while reviewing screenshots:** grey plot backgrounds from Streamlit's renderer;
  green ↑ on negative deltas (Streamlit reads only ASCII "-"); heatmap axes parsed "$55" as
  numbers; sidebar footer above page inputs; label collisions in tornado and scenario bars.
- **Verified:** ruff, format, pyright clean; 70 tests; screenshots of every page at 1500 and
  1280 px, plus the Risk floor interaction.

## 2026-10-19 (cont.) — "Field Report" redesign from a reference review
- **Why:** owner still found the dashboard generic.
- **Research:** three parallel tracks captured ~35 public references with headless Edge
  (fintech/SaaS, market-data, editorial/ag). Patterns adopted: finding-as-headline (ERS/OWID),
  quote hero + hairline key stats (Stock Analysis/CME), stat strip merged with the main chart
  (Plausible), direct end labels and forecast shading (ERS/Koyfin), source line under every chart.
- **Done:** new tokens and components in `ui.py`; every page rebuilt around one hero; inputs
  moved from the sidebar into assumption chips; Overview's signature chart joins 12 months of
  actual index with the 12-month projection and its simulated range.
- **Verified:** ruff, pyright, 70 tests; screenshots of all pages.

## 2026-10-19 (cont.) — Removing "AI-made" tells
- **Research:** designer write-ups on what makes AI-built dashboards recognisable (see
  `docs/DESIGN.md` checklist).
- **Done:** IBM Plex Sans + Source Serif 4; sentence-case kickers; 6-8px radius; decorative
  icons removed; unbreakable figures (word-joiner minus); reflowing stat strips; asymmetric
  lower layouts; footer with preparer/date/sources (`PREPARED_BY`); consistency fixes (timing
  chip 42 vs 41 weeks, wrapped labels, axis overrun, clipped chart labels).
- **Verified:** ruff, pyright, 72 tests; tall-viewport screenshots of all pages at 1440/1280.

## 2026-10-19 (cont.) — NASS Hogs and Pigs: supply outlook
- **Done:** NASS key verified (loaded via settings, never printed; error text scrubbed). `data/nass.py`
  client + bundled 2010-2026 sample; `supply.py` outlook by marketing window (weight classes,
  pig crop, farrowing intentions vs a year ago); new Hog supply page; U.S. pigs-per-litter
  benchmark on Herd flow; footer credits NASS.
- **Findings (Sep 1, 2026 report):** market hogs −1.5% y/y across all weight classes; Jun–Aug
  pig crop −1.5%; Sep–Nov farrowing intentions −1.8%, Dec–Feb +2.1%; breeding herd 5.87M,
  smallest September herd since 2013; U.S. pigs per litter 11.96 vs the app's default 12.10.
- **Verified:** ruff, pyright, 79 tests; screenshots of Hog supply and Herd flow.
- **Next:** My Market News key → corn/SBM cash prices and feed-quantity calibration.

## 2026-10-19 (cont.) — Usability round
- **Done:** inputs now have one source of truth (`ui.herd_from_state` / `cost_from_state` read
  the widget keys), so a setup loaded from file or changed on any page drives every page;
  Overview quick controls (hog price, corn, price path) share keys with Costs & returns;
  "Benchmark inputs / Your inputs" indicator; U.S. hog supply on the Overview; sidebar Save /
  Load inputs (JSON); plain-language Guide page (steps, glossary, data sources and update
  schedule, model limits).
- **Fixed:** hog-price note compared a custom price with last week's index; "today's" wording
  on custom prices; smoke test that passed on the stylesheet instead of real content.
- **Verified:** ruff, pyright, 81 tests (incl. inputs-drive-pages test); interaction test
  (Overview price change → Costs page, no Streamlit warnings); screenshots.

## 2026-10-19 (cont.) — Wean to finish (from Pipestone's wean pig crush workbook)

- The user shared a Pipestone "USDA Wean Pig Crush" workbook showing how staff use this kind of
  tool. Kept it in `reference/` (git-ignored: the repo is public and it holds internal costs and
  licensed futures data). Its USDA weaned pig series (public) became `data/sample/`.
- New `crush.py` reproduces the workbook's margin to the cent (Sep 14 placement: −$12.39 before,
  −$16.79 after debt payments). Contract mapping uses the 10th-business-day expiry, so a Feb 14
  sale prices on April (the workbook had typed February by hand).
- New `data/feeder.py` reads USDA's public feeder pig PDF (no My Market News key needed);
  `nass.load_corn` adds monthly Iowa corn so realized margins use the corn of their months on feed.
- New Wean to finish page: margin for a pig placed today, most you can pay for a pig, margin by
  week placed (3 years realized + pigs on feed), weaned pig history, cost lines, pig × hog grid.
- Lean hog futures have no free feed: contract prices default to a seasonal estimate from the
  index (chip says so) and are entered per contract.
- Pyright errors seen mid-session came from a half-installed pandas-stubs; removed, back to 0.

## 2026-10-19 (night) — Roadmap v2, Phase 0

- `docs/ROADMAP.md`: phased plan (crush history, hog market, hedging book, MMN, sow side,
  weekly brief, archive, polish) with a standard gate plus per-phase tests.
- `scripts/screenshots.py`: every page at 1440 and 390 px into `outputs/shots/`.
- Phone review found the sidebar covering the page (forced "expanded"); now "auto".
