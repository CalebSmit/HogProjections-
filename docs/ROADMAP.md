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
- [ ] NASS monthly slaughter and cold storage (pork, bellies) vs 5-year average
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

- [ ] MARS API client (basic auth, key scrubbed from errors) with sample + cache
- [ ] Iowa/Minnesota cash corn, SBM (48% Decatur / rail), DDGS (Iowa) → defaults for every
      corn/SBM/DDGS input, with "as of" chips
- [ ] Feeder pig report full history: cash **and formula** composites, receipts, 40 lb pigs →
      formula-vs-cash spread chart; volume
- [ ] Corn basis vs Iowa price received history
- [ ] Guide data-source table and README updated

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
- [ ] WASDE pork production / hog price forecast if a keyless source is verified
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
- [ ] Load-time budget: first paint < 3 s from cache; profile and cache the heavy computations
- [x] Phone layout pass on every page
- [ ] Final full-app screenshot review and a written review against the principles above
- [x] README, Guide, ARCHITECTURE refreshed

**Phase tests:** standard gate on every page; timing check script.

## 5. Order tonight

0 → 1 → 2 → 3 → 5 → 6 → 7 → 8. Phase 4 waits for the My Market News key.
