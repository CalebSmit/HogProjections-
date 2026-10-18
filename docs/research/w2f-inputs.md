# Research: wean-to-finish projection inputs

*Compiled 2026-10-17/18. The cloud sandbox could not reach usda.gov, iastate.edu, umn.edu,
cmegroup.com or Yahoo, so the figures below come from search snippets and public GitHub code.*

Tags:
- **[VERIFY]**: a source was found, but it couldn't be checked against the primary document.
- **[ESTIMATE]**: industry-typical judgment, no direct source.

Every tagged value is an editable input in both the dashboard and Excel.

## 1. Weaned pig price: USDA "National Direct Feeder Pig Report"

**Identity**
- MyMarketNews slug **2810** (code AMS_2810; legacy code NW_LS255, `nw_ls255.txt` is probably dead).
- Weekly weighted-average report of direct trades.
- Don't confuse it with the "National Direct *Delivered* Feeder Pig Report" (NW_LS830, slug 2809), which is quarterly and discontinued.

**Contents**
- Early weaned (10–12 lb) and feeder pigs (40 lb), in $/head.
- **Cash** and **Formula** reported separately, each with head count, price range and weighted average.
- Lot-size buckets seen in 2024–25 editions: **under 600, 600–1,200, over 1,200 head**.
- **No "2,400 head or more" bucket was found** [VERIFY on a live report]. The app uses the
  2,400+ bucket if one exists, otherwise the largest bucket, and shows which it used.

**Access**
- `https://marsapi.ams.usda.gov/services/v1.2/reports/2810?q=report_begin_date=MM/DD/YYYY:MM/DD/YYYY&allSections=true`
- Needs a free API key, sent as HTTP Basic (key, "").
- JSON field names for this report aren't documented [VERIFY]. The parser matches by keyword
  and saves the raw response to `data/cache/usda_2810_raw.json`.

**Price levels** (early weaned composite, as reprinted by Manitoba Agriculture)

| Week of report | $/head |
|---|---|
| Oct 13, 2026 | **$24.81** (default) |
| Oct 6, 2026 | $28.22 |
| Jul 28, 2026 | $49.65 |

- Jan 27, 2026 (Meatingplace): cash $100 vs formula $68.70. About 70% of early-wean pigs now trade cash.

## 2. Feed: corn, soybean meal, DDGS

**Futures**, settles Fri 2026-10-16:
- Dec '26 corn (ZCZ26): 474.25¢/bu
- Dec '26 soybean meal (ZMZ26): $357.10/ton

**AMS reports**

| Report | Slug | Content |
|---|---|---|
| Iowa Daily Cash Grain Bids | 2850 | Corn/soy cash and basis by region: NW, N Central, NE, SW, S Central, SE |
| National Weekly Grain Co-Products | 3618 | DDGS 10% by state |
| National Weekly Ethanol Report | 3616 | DDGS asks by sub-region |
| Grain & Oilseed Processor Feedstuff, weekly | 3511 | SBM 46.5–48% and DDGS by state |
| Grain & Oilseed Processor Feedstuff, monthly | 3668 | Monthly averages by state |
| Illinois Grain Bids | 3192 | Illinois cash and basis by region |

- The Iowa Production Cost Report (2863) covers fertilizer and fuel only, not feed.

**Observed values**
- **DDGS, AMS 3618, Oct 5 2026:** IA 179.79, MN 186.25, SD 195.00, NE 207.50, IL 202.50, IN 187.88 $/ton.
- **SBM FOB, AMS 3668, Oct 8 2026:** IA 366.75, MN 359.79, IL 378.06 $/ton. That's roughly +$3 to +$21 over Dec ZM.
  - Trucking to the farm adds ~$15–25/ton [ESTIMATE].
  - So the location table stores SBM as a *delivered* premium over futures.
- **Corn basis:**
  - NW Iowa co-op Dec bids −37/−39 (Oct 7 2026).
  - S. MN cash $4.18–4.36 (Oct 13).
  - Harvest lows usually come mid-October (farmdoc).
  - Regional corn and SBM basis values in `data/defaults/locations.csv` are **[ESTIMATE]**, anchored on these figures.

**Futures, keyless:** Yahoo chart API `ZC=F` (¢/bu, divide by 100) and `ZM=F` ($/ton) [VERIFY].

## 3. Barn, labor, other costs

| Item | Default | Basis |
|---|---|---|
| Barn | $40/space/yr | Older extension $30–40/space/yr, or $9–12/head placed. Compeer/NHF 2023: the "$10–11" fee is now "$13–14". New barns cost $430–525/space (2025). [VERIFY] |
| Labor hours | 0.20 hr/pig [ESTIMATE] | ISU livestock budgets assume 0.5 hr/pig; ISU 2019 hoop budget 0.55 hr at $20/hr. A modern tunnel W2F barn is far lower. |
| Labor wage | $18.15/hr | NASS livestock worker wage, US, Apr 2025 |
| Labor wage, Northern Plains | $17.51/hr | NASS, Oct 2024. Regional figures are now only in Quick Stats [VERIFY] |
| Interest | 7.12% | Chicago Fed AgLetter, operating loans, Q2 2026 |
| Vet/med | $5/head [ESTIMATE] | |
| Utilities | $4/head [ESTIMATE] | |
| Trucking | $4/head [ESTIMATE] | |
| Insurance | $0.50/head [ESTIMATE] | |
| Checkoff | 0.35% of value | Statutory |
| Yield | 75% | LM_HG201 2025 sample days: 285.7–289.6 lb live, ~215 lb carcass |
| Merit premium | $1.50/cwt carcass | LM_HG201 net minus base, 2025 sample days [VERIFY] |
| Mortality | 6.8% | MetaFarms/NPB single-stocked W2F, 2024 (6.81%) |
| ADG | 1.72 lb/day | MetaFarms/NPB 2024 |
| Out weight | 282.9 lb | MetaFarms/NPB 2024 |

**Pipestone note:** a contract grower fee usually covers the barn, labor, utilities and building
insurance. Use the $/pig-placed barn mode for the fee, and zero out the labor and utilities lines,
so nothing is counted twice.

**Sources to pull on a real machine:**
- ISU FM1815 / B1-21 (2026)
- ISU `wean_to_finish_procedure.pdf`
- UMN "Select rents, rates and values" 2025, livestock section
- NASS Quick Stats, regional livestock wages

## 4. Feed budget

- **Total:** 12 → 285 lb at ~2.6 F:G is ~710 lb feed per pig marketed [ESTIMATE].
- **Default program** (`data/defaults/feed_phases.csv`): six phases, nursery 55 lb and
  grow-finish 655 lb. Works out to ~8.3 bu corn, ~93 lb SBM and ~125 lb DDGS per pig.
- **Other %** (premix, AA, fat, specialty proteins) is priced per ton of "other":
  - Nursery 1 at $1,600/t gives the specialty nursery premium.
  - Grow-finish 3% at $1,200/t ≈ $36 per ton of complete feed (industry $30–45).
- **DDGS is cut in Finisher 2** to manage pork fat iodine value.
- All values are [ESTIMATE]; they're meant to be replaced with the producer's own nutritionist's program.

## 5. Lean hog price and basis

See `docs/research/domain.md` §3, and `src/hogproj/basis.py`:
- The CME Index is rebuilt from LM_HG201 (slug 2511, LMR Datamart, keyless).
- Futures come from Yahoo `HE=F`.
- Basis is averaged by half-month.
- Contract mapping follows ISU B2-41.

**Futures settles, Oct 16 2026:**

| Contract | $/cwt |
|---|---|
| Dec '26 | 66.925 |
| Feb '27 | 69.225 |
| Apr '27 | 74.675 |

- CME Index: $75.09 on Oct 14 2026.
- No published table of "CME Index − nearby futures by month" exists. ISU B2-41 publishes IA/MN cash − futures, which is a different cash series. The app computes the index basis itself on first run.
