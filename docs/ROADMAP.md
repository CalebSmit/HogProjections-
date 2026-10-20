# Roadmap v2 — from projection tool to the desk everyone checks every week

> Written 2026-10-19 after reviewing Pipestone's "USDA Wean Pig Crush" workbook.
> Execution order lives here; `docs/PLAN.md` keeps the history of phases 0–4.
> A phase is done only when every check in its **Gate** passes. Gates are run, not assumed.

## 1. What the workbook tells us

Pipestone staff price a weaned pig like a trader prices a crush spread:

| Workbook step | What it means | Where the app is today |
|---|---|---|
| USDA early weaned 10–12 lb cash composite + **$7 Pipestone adder** | Cost of the pig | Live (public USDA PDF), adder is an input |
| Report date + **160 days** → CME period | Which lean hog contract prices the pig | `crush.contract_for`, 10th-business-day expiry |
| Lean hog futures + **basis** (index − futures, same week last year) | Expected sale price | Futures typed in; basis is a single number |
| Corn futures + $0.20 carry, SBM futures, DDGS | Feed priced at placement | One corn/SBM/DDGS price for every row |
| **% hedged** and hedged price per row (corn, SBM) | Positions already taken | Not modelled |
| Fixed costs (2026 Q2 settings) + principal + term interest | Cost to raise and service debt | Inputs; Pipestone values in a local setup file |
| Twelve weekly placement columns | The book of pigs on feed | "Pigs on feed" table |

It's a spreadsheet that answers one question: **what are the pigs we just placed going to make?**
It can't answer the questions that come right after it, and those are this roadmap:

1. **Was that a good price for the pig?** (what pigs have *turned out* to be worth, by season)
2. **Should we lock it in?** (is this margin good versus history; what's hedged; what's open)
3. **What's the market telling us?** (packer margins, slaughter, weights, supply, cold storage)
4. **What about the sow side?** (a weaned pig is revenue for a sow farm; finish or sell?)
5. **What happened?** (a weekly record since 2020 everybody can point to)

## 2. Product principles (every phase is reviewed against these)

1. **Every view ends in an answer.** A chart's title states the finding; every page leads with a
   decision or a number that drives one. No chart ships without a sentence saying why it matters.
2. **Past and future on one footing.** Realized margins use the same formula as projections
   (index ↔ futures, same cost lines), so "now" can be compared with history honestly.
3. **Percentiles, not just levels.** "−$7 a pig" means little; "worse than 82% of placements
   since 2020" means a lot. Every key margin gets a historical rank.
4. **Say where every number comes from and how old it is.** Source line on every chart, a
   freshness chip per source, and a visible "estimate" tag when a value is modelled.
5. **Your numbers, not ours.** Every default can be overridden and saved to a setup file.
   Internal Pipestone values never go into the public repo.
6. **Runs with no keys and no internet.** Live → cache → bundled sample, always.

## 3. Data sources (all free)

Verification status is filled in from live tests (see `docs/research/data-sources.md`).

| Source | Gives us | Key | Status |
|---|---|---|---|
| USDA AMS LMR datamart · LM_HG201 | Lean Hog Index, head, carcass weights | none | in use |
| USDA AMS Feeder Pig Report (AMS_2810 PDF) | Weekly weaned & 40 lb pig prices, receipts | none | in use (latest 2 weeks; history via sample + cache) |
| USDA NASS Quick Stats | Hogs & Pigs inventory, Iowa corn price received | NASS | in use |
| USDA AMS LMR · pork cutout (LM_PK602) | Cutout and primal values → packer margin | none | Phase 2 |
| USDA AMS LMR · slaughter / sow reports | Daily slaughter, weights, sow prices | none | Phase 2 |
| USDA NASS · slaughter, cold storage | Monthly slaughter, pork & belly stocks | NASS | Phase 2 |
| USDA WASDE | Pork production and hog price forecasts | none | Phase 6 |
| USDA ERS · meat price spreads | Retail pork value | none | Phase 7 |
| USDA AMS My Market News (MARS API) | Cash corn, SBM, DDGS; full feeder pig history incl. formula prices | MMN (free) | Phase 4 — when the key works |
| FRED / EIA | Prime rate, diesel | free keys | optional, Phase 8 |
| Lean hog / corn / SBM futures | Contract prices | — | No free licensed feed: typed in with an "as of" date; see Phase 3 |

## 4. Phases

Each phase ends with a usable app, pushed to the PR branch.

### Standard gate (applies to every phase, in addition to its own checks)

- [ ] `uv run ruff check .` and `uv run ruff format --check .` clean
- [ ] `uv run pyright` — 0 errors
- [ ] `uv run pytest -q` — all green, including new tests listed in the phase
- [ ] Every page renders through the router in AppTest (`test_pages_render`) and leads with
      headline figures
- [ ] App runs with `OFFLINE=true` (bundled data only) without errors
- [ ] Screenshots of every changed page at 1440 px and 390 px (phone) reviewed against the
      design rules in `docs/DESIGN.md`: finding titles, source lines, no overlapping labels,
      no horizontal scroll on phone, true minus signs, no unexplained jargon
- [ ] **Answer review:** for each new chart/table, write down the decision it supports. If it
      supports none, cut it.
- [ ] `docs/PROGRESS.md` updated; commit + push

---

### Phase 0 — Baseline and guardrails
Goal: a clean, repeatable base to build on overnight.

- [x] Type checker back to 0 errors
- [x] `scripts/screenshots.py`: Playwright (installed Edge/Chrome) screenshots of every page at
      1440 and 390 px into `outputs/shots/` (git-ignored)
- [x] Offline smoke test in pytest (forces `OFFLINE`, checks every page)

**Gate:** standard gate.

---

### Phase 1 — Crush history: what weaned pigs turned out to be worth
Goal: the reference view of the past. Answers "was that a good price for the pig?"

- [x] Extend LM_HG201 history to Jan 2020 (chunked fetch, bundled sample) so every USDA weaned
      pig week since Oct 2020 has a realized sale price
- [x] `crush.realized_value`: for each placement week, the pig price that would have broken
      even given the hog price it actually sold at and the corn it actually ate
      (**"what the pig was worth"**) and the spread to what was paid
- [x] `crush.margin_rank`: percentile of any margin against all realized placements
- [x] Seasonality of realized margin by placement month (year × month grid, plus average)
- [x] New page **Crush history** (Markets → or Wean to finish tab): paid vs worth chart,
      year × month heatmap, best/worst placement weeks, annual summary table, CSV download
- [x] Wean to finish hero gains the rank: "worse than 82% of placements since 2020"

**Phase tests:**
- Realized value: margin at the realized value is $0 (property), hand-calculated value for
  three placement weeks matches to the cent
- Percentile rank: monotone, 0 and 100 at the extremes, ties handled
- Seasonal grid: 12 months, years complete/partial flagged, averages match a manual pivot
- AppTest: history page renders offline and live; download button present

---

### Phase 2 — The hog market behind the price
Goal: explain *why* hog prices are where they are. Answers "what's the market telling us?"

- [x] LMR pork cutout client (carcass + primals) with sample + cache
- [x] Packer margin proxy: cutout value per head − hog cost per head; spread history
- [x] Daily/weekly slaughter and average carcass weight vs last year (heavy weights = hogs
      backing up = bearish)
- [ ] Sow slaughter / sow prices (herd liquidation signal) if available keyless
- [x] Cold storage vs 5-year average (ERS, total pork; bellies aren't published separately there)
- [x] **Market prices** page becomes **Hog market**: index + cutout + spread; weights;
      slaughter; storage — each with a one-line read ("Packers are making $X a head, the most
      since …; that usually supports cash hogs")
- [x] Signal summary strip: each indicator scored bullish / neutral / bearish with the rule
      written out (no black boxes)

**Phase tests:**
- Parsers against saved fixtures; cutout matches USDA's published composite for a known date
- Packer margin arithmetic against a hand calculation
- Weight/slaughter YoY math; signal rules unit-tested at their thresholds
- Offline fallback for every new source

---

### Phase 3 — The book: positions, hedges and margin locks
Goal: the workbook's % hedged rows done properly. Answers "should we lock it in?"

- [x] Contract price table with an **"as of"** date and a stale warning after 3 days
- [x] Head placed per week (default: your herd flow or a flat number)
- [x] Hedges per lean hog contract (head or %, price), corn and SBM % hedged + price
- [x] Margin split: locked vs open, per contract and total book ($ and per pig)
- [x] Rank each contract's margin against history (Phase 1) and show a rule-based hedge
      suggestion the user configures, e.g. "hedge 50% when margin is in the top 25%";
      always shows the rule, never advice
- [x] What-if: hog price ±$10 shows the book's change with and without hedges

**Phase tests:**
- Hedged margin = open margin at 0%; = locked margin at 100%; linear in between (property)
- Book totals equal the sum of weeks; head-weighted averages correct
- Stale-price warning appears when as-of > 3 business days old
- AppTest: editing a hedge changes the book headline

---

### Phase 4 — My Market News (when the key works)
Goal: local cash prices and the full feeder pig record.

- [x] MARS API client (basic auth, key scrubbed from errors) with sample + cache
- [x] (done keyless from AMS PDFs 2850/3511) Iowa cash corn, SBM, DDGS → defaults for every
      corn/SBM/DDGS input, with "as of" chips
- [x] Feeder pig report full history: cash **and formula** composites, receipts, 40 lb pigs →
      formula-vs-cash spread chart; volume
- [x] Corn basis vs Iowa price received history
- [x] Guide data-source table and README updated

**Phase tests:** parsers against fixtures; key never appears in logs/errors (test injects a
fake key and asserts it's scrubbed); fallback when the key is missing or wrong.

---

### Phase 5 — The sow side and the integrated system
Goal: a weaned pig is a sow farm's revenue. Answers "sell pigs or finish them?"

- [x] Farrow-to-wean cost per weaned pig (ISU farrow-to-wean line items as defaults)
- [x] Sow farm margin = USDA weaned pig price (+ adder) − cost, history since 2020
- [x] Integrated margin per pig = sow farm + wean-to-finish, and the comparison
      "selling weaned pigs vs finishing them" by placement week
- [x] New page **Sow farm** (Your operation)

**Phase tests:** ISU farrow-to-wean published month reproduces; integrated = sum of parts
(property); page smoke.

---

### Phase 6 — The weekly brief (new home page)
Goal: the page people open every Monday. Answers "what changed and what do we do?"

- [x] "This week" strip: Lean Hog Index, weaned pig, cutout, corn — each with w/w and y/y
- [x] Three decisions, each a sentence with the number that drives it:
      placement (margin + rank + most you can pay), hedging (best contract vs history),
      feed (corn vs seasonal norm)
- [x] What changed since last week (biggest movers, in words)
- [x] Calendar: Hogs & Pigs, WASDE, Cold Storage release dates; contract expiries
- [x] WASDE pork production / hog price forecast (keyless text file)
- [x] One-page export (Excel today; PDF if a dependency-light route exists)

**Phase tests:** brief is deterministic for fixed data (snapshot of the generated sentences);
calendar dates correct for 2026–2027; export opens and contains every section.

---

### Phase 7 — Reference and archive
Goal: the record people cite.

- [x] Weekly archive table since 2020: index, cutout, weaned pig, corn, realized crush margin,
      slaughter, weights — filter by year, download CSV/Excel
- [ ] Annual recap cards (best and worst months, averages, what drove them)
- [ ] Methods page: every formula in plain language with its source

**Phase tests:** archive row count = weeks in range; values match source tables; download opens.

---

### Phase 8 — Polish and trust
- [x] Freshness chip per source in the footer; error states for every loader
- [x] Load-time budget: cold start 5 s (parallel warm-up), later pages 0.3–0.7 s
- [x] Phone layout pass on every page
- [ ] Final full-app screenshot review and a written review against the principles above
- [x] README, Guide, ARCHITECTURE refreshed

**Phase tests:** standard gate on every page; timing check script.

## 5. Status (2026-10-20 morning)

Done overnight: phases 0, 1, 2 (+ live feed prices, WASDE, cold storage), 3, 5, 6, 7 and most
of 8. Phase 4 done Oct 20 (My Market News connected). Open: sow price signal, annual recap cards, a
full methods page.

## 6. Original order

0 → 1 → 2 → 3 → 5 → 6 → 7 → 8. Phase 4 waits for the My Market News key.


---

## Phase 9 — More of the market (plan, 2026-10-20)

Written from two seats: a producer deciding when to buy pigs, sell hogs and price feed, and a
Pipestone finance analyst building next year's forecast. Every source below was checked against
the live My Market News catalog (1,051 reports) or the keyless LMR datamart on Oct 20, 2026.

### A. A national view, not just Iowa
| # | Data | Source | Key | History | What it answers |
|---|---|---|---|---|---|
| 1 | Hog prices by region (Iowa/Minnesota, Western and Eastern Corn Belt, national) by purchase type: negotiated, swine/pork market formula, other purchase arrangements | LMR LM_HG218 (slug 3458) | none | Dec 2020 → | Is my region paid more or less than the index? How far apart are formula and negotiated hogs? |
| 2 | Hogs slaughtered by state of origin | LM_HG218 "State of Origin" | none | Dec 2020 → | Where the hogs come from, week to week |
| 3 | Carcass weight differentials and the lean/weight matrix | LM_HG218 | none | Dec 2020 → | What heavy or light hogs cost you: sell now or feed longer? |
| 4 | Cash corn and basis in 10+ states: Minnesota, South Dakota, Nebraska, Illinois, Indiana, Ohio, Missouri, Kansas, North Carolina, Texas (+ Iowa) | My Market News state grain bids (3049, 3186, 3225, 3192, 3463, 2851, 2932, 2886, 3156, 2711) | MMN | Feb 2020 → | Feed cost by region; where corn is cheap relative to futures |
| 5 | Feeder pig flows: share of pigs by state of origin and destination | AMS_2810 "Report Volume" | MMN | Oct 2020 → | Where weaned pigs are moving; demand by region |
| 6 | Feed ingredient prices by state (meal, DDGS, premix inputs) | Production cost reports: Iowa 2863, Illinois 3195, North Carolina 3159, Oklahoma 3621, Inter-Mountain West 3883 | MMN | 2020 → | Ration cost outside Iowa |

### B. Complete the margins
| 7 | Hog by-product (drop) value, $/cwt | AMS_2835 (NW_LS446) | MMN | Feb 2020 → | Packer margin = cutout + drop − hog cost (today's gauge leaves drop out) |
| 8 | Sow prices by weight class | LMR LM_HG234 (3452), LM_HG230 before 2021 | none | 2010 → | Cull sow revenue for the sow farm; liquidation signal |
| 9 | Daily and weekly federally inspected slaughter (all hogs, incl. packer-owned) | AMS_3208, AMS_3658 | MMN | 2020 → | Total supply, not just producer-sold |

### C. Demand
| 10 | Grocery pork feature activity and retail prices by cut and region | AMS_2868 | MMN | 2006 → | Is retail promoting pork more than last year? |
| 11 | Live hog trade with Mexico | AMS_3629 | MMN | — | Export pull at the border |
| 12 | Pork export sales and shipments by country (Mexico, China, Japan, Korea) | USDA FAS Export Sales API | free api.data.gov key | 1990s → | The biggest swing factor for hog prices |

### D. Futures (the one gap)
No free, licensed source for lean hog futures exists. The workbook shows Pipestone already uses
DTN and Barchart. Options, best first:
1. **Import their export**: upload a Barchart or DTN quote export (CSV/Excel) and the app fills
   every contract price with its as-of date. Small, robust, no new subscription.
2. Their DTN/Barchart API, if the subscription includes one (needs their credentials).
3. Today's manual entry with the stale warning (in place).
CBOT corn and soybean settlements already come free in the Iowa grain report.

### E. Finance inputs for budgets
| 13 | Prime rate / SOFR | FRED (free key) | Operating interest per pig |
| 14 | On-highway diesel; propane | EIA (keyless XLS / free key) | Freight and barn heat cost lines |
| 15 | Iowa State Estimated Livestock Returns, monthly | ISU (public) | Keep cost defaults current automatically |
| 16 | WASDE history | USDA ESMIS (public) | How accurate USDA's hog price forecasts have been — how much weight to give them |

### Status (2026-10-20)
Done: A1–A5 (National view), B7 drop value in the packer spread, B8 cull sows, B9 all
federally inspected slaughter (AMS_3208, Dec 2023 on), C10 retail features, D1 futures import,
E13 prime rate (FRED keyless CSV), E14 diesel and propane (EIA keyless XLS), E15 ISU cost
defaults, E16 WASDE track record. Weekly refresh Action and staleness guard in place.
Not done: A6 state feed ingredients (Iowa covers the ration today); C11 Mexico trade — AMS_3629's
hog rows are breeding-stock exports in small numbers, little signal for market hogs; C12 FAS
export sales — needs a free api.data.gov key from the user.

### Recommended order
1. National view page (A1–A4): regional hog prices + state corn/basis map.
2. Drop value and sow prices into the packer margin and sow farm (B7–B8).
3. Futures import from Barchart/DTN exports (D1).
4. Exports (C12, needs a free key) and retail features (C10).
5. Finance inputs (E13–E15).

### Keeping it current
- **How fresh is it?** Every source reloads when the app opens (and every six hours while
  open), at USDA's own rhythm: hog prices and cutout each business day, weaned pigs and meal
  weekly (Fridays), WASDE monthly, Hogs and Pigs quarterly. It isn't tick-by-tick: USDA
  publishes once a day or week, and lean hog futures still come from the user.
- **Staleness guard (done Oct 20):** each source has a maximum age; past it, every page header
  turns red ("N data sources out of date") and Data status names the source.
- **Proposed (needs approval):** a weekly scheduled GitHub Action that refreshes the bundled
  data (so a fresh download is never old), runs the live parser checks, and fails loudly
  (GitHub emails the owner) if a USDA report changes format. Needs the MMN and NASS keys stored
  as GitHub repository secrets.

## Phase 10 — Make it one clear weekly answer (plan, 2026-10-20)

Inputs: a review of everything shipped in Phase 9 (code review plus a page-by-page read of
every headline), and research into how CIH Margin Watch, Steiner's Daily Livestock Report,
Sterling's Pork Profit Tracker, ISU/Ever.Ag, MSHMP/SDRS and EIA present the same kind of data.
The theme: fewer, sharper answers that agree with each other, every number shown against its
own history, and a one-page brief clients will actually forward.

Each step ends with its test gate (ruff, pyright, pytest, AppTest on every page with and
without the My Market News key, and screenshots of the changed pages).

### 10.0 Fix what Phase 9 shipped (first, small)
| # | Problem | Fix |
|---|---|---|
| 1 | Without the MMN key in GitHub, slaughter, drop value and retail samples freeze; the signals keep using them as "last 4 weeks" | Signals ignore a source past its freshness limit (Slaughter falls back to LMR); ask user to add the repo secret |
| 2 | An old local cache beats a newer committed sample | Load whichever has the later date |
| 3 | Hog market's slaughter chart (producer-sold, −2.8%) disagrees with its signal (all inspected, −0.1%) | Chart uses all inspected hogs; producer-sold as the thin line |
| 4 | WASDE caption counts 14 forecasts but quotes a bias based on 4 | Quote the right count |
| 5 | Retail signal says "last 4 weeks" for a one-week feature rate | Average the 4 weeks |
| 6 | Propane shows May's price all summer as if current | "Last surveyed May 12" off-season |
| 7 | Futures "HEZ9" read in Jan 2030 becomes 2039 | Pick the nearest year either way |
| 8 | Weekly refresh rewrites hundreds of lines of float noise | Round before saving |
| 9 | Delaware, West Virginia, Maine missing from the origin map; cull sow weight averaged since 2020; page footers list only the original sources | Add states; last 8 weeks; footer lists sources the page uses |
| 10 | Quote exports with no date are stamped today, hiding stale files | Use the file's own dates, else ask |
Gate: new tests for each (stale-source fallback, cache vs sample, year rollover).

### 10.1 Every number against its own history (seasonal bands)
One chart helper used everywhere a weekly series appears: this year (bold), last year (thin),
and the 5-year min–max band (shaded), with a one-line verdict ("inside the usual range",
"lowest for October since 2020"). Apply to: Lean Hog Index, cutout, inspected slaughter,
carcass weights, weaned pig price, cold storage, sow prices, corn basis.
Gate: helper unit tests (band math, leap years, missing weeks); screenshots.

### 10.2 Forward margin board (the hedging decision)
CIH-style: margin per pig for each marketing month ahead, colored by its percentile against
every placement since 2020, with the trend over recent weeks (rows = weeks ago, from saved
snapshots of each futures upload and of the seasonal estimate). Callout: "Apr 2027 is at the
62nd percentile, up from 27th two weeks ago; your rule hedges at 75th." Lives on Hedging,
summarized on This week. Adds hog/corn ratio and margin in $/cwt for analysts.
Gate: percentile and snapshot tests; Excel sheet with the grid.

### 10.3 This week as a scorecard
- Three sentences up top that answer: margin now, best month to hedge, what changed.
- Scorecard table: value, week change, year change, percentile vs 5 years, a status dot with
  a word (never color alone) for ~10 metrics.
- "Biggest movers" bars: what moved the margin per pig since last week, sorted.
- A "watch list" of rule crossings: margin above the hedge trigger, coverage below policy,
  sow prices or slaughter breaking their 5-year range.
Gate: AppTest checks the sentences match the numbers on the detail pages.

### 10.4 More of the market (new data, all free)
| Data | Source / access | Shown as |
|---|---|---|
| Sow slaughter vs a year ago, as a herd liquidation signal | AMS_3658 weekly actual FI slaughter (MMN key, ~2 week lag) — check sow class; fallback LM_HG234 head counts | Hog supply + a signal |
| Pork exports by destination (Mexico, China, Japan, Korea, Canada) | ERS Livestock & Meat Trade (monthly, keyless ZIP); FAS export sales (ESRQS, said to need no login since Mar 2026 — verify) | Small multiples with 5-year band, "top mover" line |
| Disease pressure (PRRS/PED) | ISU SDRS public dashboard / monthly report; MSHMP charts (no data API) | Link card + a status the user sets; no scraping |
| Farm-to-retail pork spread | ERS Meat Price Spreads (monthly, keyless) | Hog market demand section |
| Canadian hogs into the U.S. | AAFC weekly exports to the U.S. (public) | National view, next to feeder pig origins |
| Outside views | ERS Livestock, Dairy & Poultry Outlook; Rabobank quarterly summary | Quarterly digest row, entered by hand |
| Benchmark check | Sterling Pork Profit Tracker (weekly, Drovers) | "Your margin vs industry benchmark" line, entered by hand |
Not planned: packer capacity utilization (no free official series), CME data feeds (licensing).
Gate: parser tests with fixtures, freshness entries, weekly refresh, Guide rows.

### 10.5 The weekly brief clients forward
One page PDF/print view: headline, scorecard, margin board, two charts, as-of dates and
sources, Pipestone-ready. Download button on This week; Excel twin.
Gate: render test; page fits on one letter page.

### 10.6 Phone layout
Scorecard-only stacked view under ~700 px; charts collapse to sparklines with the verdict.
Gate: screenshots at 390 px width.

### Order and size
10.0 (half a day) → 10.1 (1 day) → 10.3 (1 day) → 10.2 (1–2 days) → 10.5 (1 day) →
10.4 (2–3 days, source by source) → 10.6 (half a day).

### Needs the user
- Add `USDA_MMN_API_KEY` (and `NASS_API_KEY`) as GitHub repository secrets so the weekly
  refresh keeps every source current (10.0 #1).
- Confirm the hedge policy defaults (trigger percentile, target coverage) Pipestone uses.
- Optional: whether Pipestone wants its logo/name on the brief (10.5).
