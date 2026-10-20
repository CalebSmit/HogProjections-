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

## 2026-10-20 — Phase 1: crush history

- LM_HG201 loader is incremental (saved copy + new days + a week of overlap) and reaches back to
  Jan 2020; bundled sample now 2020→ (~540 KB). Index still matches CME 75.75 on Oct 12, 2026.
- `crush.py`: `worth_usd` per placement (break-even pig price given realized hog and corn),
  `margin_rank`, `by_month`, `month_average`, `annual_summary`. Shared `ui.crush_book()` so both
  wean-to-finish pages use one set of contract prices and placements.
- New **Crush history** page: paid vs worth, year × month heatmap, today's percentile in the
  distribution, annual table, best/worst weeks, CSV. Wean to finish hero shows the percentile.
- Findings on default inputs: 293 weeks since Sep 2020, avg +$3.26/pig, 57% profitable; Nov
  placements best (+$10.94), Aug worst (−$11.50).
- Data-source research saved to `docs/research/data-sources.md`: keyless AMS PDFs give Iowa cash
  corn (2850), soybean meal (3511) and DDGS (3618) — feed prices no longer wait on the MMN key.
  Yahoo futures rejected on terms of use.
- Gate: ruff, pyright 0, 106 tests, desktop + phone screenshots reviewed.

## 2026-10-20 — Phase 2: hog market

- `data/lmr.py`: generic incremental LMR loader; LM_PK602 cutout + primals since 2020 (sample).
- `hogmarket.py`: daily table (index, cutout, packer gross spread, producer-sold head, weights),
  weekly roll-up, year-ago comparisons that line up weekdays (364 days), five rule-based signals
  (packer spread percentile, cutout 4-week trend, weights and slaughter vs last year, NASS supply)
  and an overall read. Every rule is shown on hover.
- Market prices page rebuilt as **Hog market**: headline states the read; signals panel; cutout
  vs index; weekly packer spread with top/bottom quartiles; this year vs last year overlays for
  weights and slaughter (2020 left out of the range: COVID plant closures); primal table.
- Pyright: `useLibraryCodeForTypes = false`. Inferring pandas types from source was
  order-dependent — adding an unrelated module flipped 24 errors on and off in old files.
- Phone: column dividers became 400 px empty gaps once columns stacked; now a `.hp-vrule`
  class hidden under 640 px (an attribute selector on the inline style didn't match).
- Gate: ruff, pyright 0, 124 tests, all 10 pages × 2 widths screenshotted without exceptions.
- Deferred: sow prices (HG234 is split by weight class; weak signal), NASS cold storage.

## 2026-10-20 — Phase 2b: live Iowa feed prices without a key

- `data/feed.py` parses the public AMS PDFs: Iowa state average cash corn + CBOT corn settlements
  (AMS_2850, daily) and Iowa soybean meal and DDGS (AMS_3511, weekly). Feedstuff rows have a
  varying number of columns, so the Iowa row is read by token type (price → skip changes →
  average), not by position. History accumulates in the cache.
- Corn, soybean meal and DDGS inputs now default to the latest USDA Iowa prices on every page
  (help text names the report and date); `uses_benchmarks` compares against those defaults.
- Cold start was ~11 s: the NASS Hogs and Pigs fetch pulled 16 years each time. Now incremental
  (last two years merged into the saved copy) — 7.4 s → 1.7 s. A first version dropped the
  Dec 1, 2024 inventory at the cut-off; regression test added.
- Screenshot script now waits for Streamlit's running indicator to clear.
- Gate: ruff, pyright 0, 134 tests, screenshots reviewed.

## 2026-10-20 — Phase 3: hedging book

- `book.py`: positions for every placement on feed with hog hedges per contract (share + price),
  corn and SBM hedges, locked vs open margin, $ exposure per $1/cwt, by-contract summary, what-if
  (book with/without hedges across ±$15), and a user-set hedge rule (trigger percentile → target
  share) that reports what the rule says — never advice.
- New **Hedging** page (Decisions): headline states the book and how much is locked; contract
  prices carry an "as of" date and are flagged after three business days; rule table; what-if.
- Tests: open = unhedged at 0%, locked at 100%, linear between; corn hedge only moves cost;
  totals; what-if swing = head × cwt × move; rule tones; interaction test (hedge → headline).
- Gate: ruff, pyright 0, 148 tests, screenshots reviewed (desktop + phone).

## 2026-10-20 — Phase 5: sow farm and the integrated system

- `sowfarm.py`: cost per weaned pig = (sow feed + non-feed per sow per year) / weaned per sow;
  defaults reproduce ISU farrow-to-wean Sep 2026 ($43.91 at ~$4.00 corn, $300 SBM, 28.4 weaned).
  Weekly sow farm margin since 2020 (Iowa corn by month), integrated = sow + finishing for each
  placement already sold, by-year summary.
- New **Sow farm** page: margin per weaned pig and per sow per year, price vs cost since 2023,
  "selling weaned vs finishing your own" by year (finishing margin = what finishing adds), cost
  lines, break-even productivity (only stated when realistic).
- Tests: ISU reproduction, per-sow cost invariance, corn sensitivity, adder, monthly corn,
  integrated = sum of parts, herd productivity → page headline.

## 2026-10-20 — Phase 6: This week (new home page)

- `brief.py`: week/year moves for any series (NaN-safe), biggest movers in words, calendar of
  exact lean hog expiries + weekly USDA report days (quarterly Hogs and Pigs left as "late
  Mar/Jun/Sep/Dec — check NASS", since exact dates aren't verified).
- New **This week** page is the default: headline = the week's hog move + what a pig placed
  today projects; four numbers (index, cutout, weaned pig, Iowa corn) with week and year change;
  movers in words; four decision cards (placing pigs, hedging, hog market, sow farm) linking to
  their pages; coming-up list. Overview renamed **Farm outlook**.
- Navigation `expanded=True`: with 14 pages Streamlit had hidden three behind "View 3 more".
- Gate: ruff, pyright 0, 163 tests, screenshots reviewed.

## 2026-10-20 — Phase 7: market archive

- `archive.py`: one row per week ending Friday since 2020 joining index, cutout, packer spread,
  producer-sold slaughter, carcass weight, USDA weaned pig, Iowa corn (monthly) and the realized
  crush margin of pigs placed that week; yearly averages; year-over-year change.
- New **Market archive** page: this year vs last (margins as $ change — a % change across zero
  is meaningless), year-by-year table, any series overlaid by week of year, CSV and Excel
  (weekly + by year) downloads filtered by year, full weekly table.
- Guide: start-each-week step points to This week; glossary adds cutout, packer spread,
  percentile, hedged share.
- Gate: ruff, pyright 0, 166 tests, screenshots reviewed.

## 2026-10-20 — Corn off the futures curve (from the workbook)

- The workbook prices feed off corn futures (+ carry), not today's cash. Now pigs on feed (and a
  pig placed today) use the CBOT corn curve from the Iowa grain report for each month on feed
  plus your basis (your cash corn minus nearby futures). Toggle on Wean to finish → Feed; default
  "Futures curve" when the curve is available. Hedging positions use each placement's own corn.
- Tests: contract-for-month mapping, curve averaging + basis, past-the-curve months, on-feed rows
  use the curve, positions use row corn. 174 tests.

## 2026-10-20 — Weekly brief download; data status

- `export.build_brief`: Excel with a Brief sheet (headline, the week's numbers with week and year
  change, the four decisions in words) plus Pigs on feed, Market signals and Crush history by year.
  The decision sentences are built once and shared by the cards and the workbook, so they agree.
  Download button on This week.
- Sidebar "Data status": latest date and live/saved for every source.
- Timing: cold start (every USDA source) 7.4 s; each later page 0.3–0.7 s.

## 2026-10-20 — USDA WASDE outlook

- `data/wasde.py` reads the public WASDE text (this month's issue, else last month's): quarterly
  pork production and barrow/gilt price (national base, $/cwt live). `hogmarket.wasde_outlook`
  compares the next two quarters' production with a year earlier; sixth market signal.
- Hog market page: "USDA sees hogs at $X live in Qn" (reported vs projected) and production vs a
  year earlier by quarter. Wean to finish → Hog prices shows USDA's next-quarter price (live and
  ≈ carcass) beside the seasonal estimate. Guide source table updated.
- Tests: parser (Oct 2026 fixture values), outlook math, signal band, missing quarters. 179 tests.

## 2026-10-20 — Cold storage; parallel data warm-up

- `data/ers.py`: monthly pork in cold storage from the keyless ERS ZIP; seventh signal (stocks vs
  the 5-year average for the month, ±5%); Hog market chart (this year vs the prior five) next to
  the written rules for every signal.
- Cold start had grown to 11.2 s with eight USDA sources loaded one by one. `ui.warm_data`
  runs every cached loader side by side on the first run (script context attached to each
  thread): 5.1 s.
- 183 tests; screenshots reviewed.

## 2026-10-20 — Fixes from an independent code review of the overnight work

1. Live-default inputs (contract prices, USDA weaned pig, corn, SBM, hog price) were stored on
   first render, kept across pages and saved, so after a data refresh last week's default stuck
   and was flagged as typed. Now `live_number` + `user_value`: defaults follow live data until
   edited (on_change marks the key); only edited or loaded values are kept, flagged and saved.
2. This week's hedging card passed 0% hedged to the rule; it now uses your entered share.
3. Corn hedges are entered as CBOT futures and get your Iowa basis, like hog hedges get basis.
4. Archive slaughter blanks holiday/part weeks (as the Hog market overlay already did).
5. Contract expiry skips CME holidays (July contracts expire the 15th in 2026 and 2027).
6. Wean to finish compared your typed pig price with USDA a year ago; now USDA vs USDA.
7. Sow farm "finishing vs selling": your own pigs move at the sow farm's price, so adders cancel.
8. Guards: an expired saved corn curve falls back to cash; empty series no longer crash pages.
9. Pigs-on-feed window sized from days on feed (was a fixed 40 weeks).
10. Text: crush heatmap uses your days on feed; cutout signal never shows "nan%".
- Regression tests for each; 193 tests. All pages × 2 widths screenshotted.

## 2026-10-20 — My Market News connected (Phase 4)

- Key saved to the local, git-ignored `.env` (never printed; tracked files scanned for it).
- `data/mars.py` (MARS API v1.2, basic auth, key scrubbed from errors; incremental cache):
  feeder pigs since Oct 2020 (early weaned cash + formula composites, head, range, 40 lb pigs),
  Iowa cash corn by region and basis daily since Aug 2020, Iowa soybean meal and DDGS weekly
  since Feb 2022. Values match the public PDFs (20.08 / 36.94, 383.37 / 190.50).
- Merged into the existing loaders, so every page upgrades without change: weaned pig history
  has no gaps; Iowa corn by month comes from daily bids (NASS before Aug 2020); realized crush
  and sow farm margins use the soybean meal and DDGS of their months (Crush history now
  −$0.64/pig since 2020 vs −$2.01 with today's feed held constant).
- Wean to finish: formula price line and formula-over-cash premium. New **Feed prices** page:
  corn history + futures curve delivered at today's basis, basis vs earlier years, meal and DDGS,
  feed cost per pig by month at your ration.
- Perf: monthly lookups built once per call (placements 0.58 s → 0.05 s); merged history cached.
- 199 tests (MARS parsers against fixtures, key scrubbing, no-key fallback).
