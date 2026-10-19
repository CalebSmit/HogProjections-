# Domain research: US hog production and markets

*Compiled 2026-10-17. The agent proxy blocked direct fetches of usda.gov, iastate.edu and
cmegroup.com, so most figures here come from search snippets plus general domain knowledge.
**[VERIFY]** = not confirmed against a primary source. Check every API path live before you
build against it.*

## 1. Biology and production cycle

| Parameter | Typical value | Source / note |
|---|---|---|
| Gestation | ~114 days ("3 months, 3 weeks, 3 days") | standard |
| Lactation / weaning age | 19–24 days | US typical |
| Wean-to-estrus | 5–7 days | |
| Farrowing interval | ~140–150 days, so 2.3–2.45 litters/sow/yr | [VERIFY] |
| Pigs weaned / mated female / yr | 28.5 mean, 29.8 median (NA Q1–Q3 2025) | [PigCHAMP](https://www.pigchamp.com/Portals/0/Documents/Benchmarking%20Summaries/north-america2025-1st-2nd-3rd-quarter-summary.pdf) |
| Pre-wean mortality | 15–17% | PigCHAMP 15.4%; MetaFarms 17.0% / 16.4% (2024; sources conflict) |
| Sow death rate | ~11.4% (Q4 2025) | [PigCHAMP Apr 2026](https://www.pigchamp.com/newsletters/april-2026) |
| NASS pigs saved/litter | 11.96 (Jun–Aug 2026) | [DTN](https://www.dtnpf.com/agriculture/web/ag/news/article/2026/09/24/us-sept-1-hog-inventory-2-year-ago) |
| Nursery | 42–56 days, 12 to ~50–60 lb | [VERIFY] |
| Wean-to-finish (W2F) | ~156 days, 283 lb out, ADG 1.72, mortality 6.2–6.8% | [MetaFarms PAS](https://www.porkbusiness.com/news/hog-production/production-analysis-summary-u-s-pork-use-data-your-advantage) |
| Finishing | 114 days, 285 lb out, ADG 2.01, mortality 5.3% | same |
| Feed conversion (W2F) | ~2.60 lb feed / lb gain | whole-herd 2.9–3.1 [VERIFY] |
| Market weight | 280–290 lb live (ISU uses 270, Missouri 2026 uses 280) | |
| Carcass yield | ~0.75 (hot carcass weight ~210–220 lb) | ISU $64.04 live ≙ $85.39 carcass |
| Birth to market | ~5.5–6.5 months | |
| Sow replacement rate | 45–55%/yr | [VERIFY] |

## 2. Farm financials

**Iowa State Estimated Livestock Returns (ELR):** <https://estimatedreturns.econ.iastate.edu/>
- This is the industry barometer for a typical unhedged Iowa producer.
- Procedure PDFs exist for farrow-to-finish, wean-to-finish and farrow-to-wean.
- Pigs per litter come from NASS; litters per sow per year come from FINBIN.
- The ration is corn + DDGS + soybean meal (SBM) by phase. Corn is priced from AMS NW_GR110; SBM uses the Iowa price.
- Nonfeed costs are a 12-month rolling average.
- 2026 results:
  - Jul +$27.21/head, the 28th straight profitable month.
  - Jan–Jul average $19.36/head.
  - Feed cost in July: $87.99/head.

**ISU ELR line items (farrow to finish, Sep 2026 sale, $/head, 270 lb pig)** — verified from
the published PDF 2026-10-19; the app's defaults:
- Feed 90.58 = corn 40.78 + SBM 15.54 + DDGS 10.25 + complete feeds/other 18.10 + processing 5.92.
- Nonfeed 76.76 = variable 48.99 + operating interest 4.47 + fixed 23.30. Death loss 8.36.
- Total cost 175.70 → breakeven 65.07 live / 86.77 carcass. Manure credit 5.59 is added to
  profit but left out of breakeven.
- Monthly history 2001–2026 is in `farrow_to_finish_excel.xlsx` on the same site ($/head only;
  no input prices or quantities).

**Budgets:**
- ISU FM1815 / B1-21 (2024): breakeven ~$55.35/cwt at $4.50 corn and $0.15/lb SBM. Decision tools: <https://go.iastate.edu/AGDMB221>
- Missouri G688 (2026), the most current: 24.2 pigs weaned per sow per year, 280 lb market hogs. <https://extension.missouri.edu/g688>
- K-State agmanager.info: editable structure, but prices from 2017.

**Ration and margin shortcut (CIH Hog Margin Watch):**
- Per 100 lb carcass: 5.3 bu corn + 73 lb SBM + $44 other costs.
- Reconstructed margin formula (inferred; CIH doesn't publish it):
  `margin $/cwt carcass = LeanHog − 5.3·Corn($/bu) − 0.73·SBM($/ton)/20 − 44`

**Breakeven:**
- Breakeven $/cwt carcass = total cost per head ÷ (carcass weight / 100).
- Gross up cost for mortality: cost ÷ (1 − mortality).
- Cost lines: weaned pig/feeder, feed, vet/med, labor, utilities, interest, facilities/depreciation.
- Feed is ~55–65% of cost of production [VERIFY].

**Contract grower vs independent:**
- Contract growers supply barns, labor and utilities; the integrator owns the pigs and feed.
- Grower pay ≈ spaces × turns per year × fee:
  - Turns: ~2.3 for W2F, ~2.8–3.0 for finishing.
  - Fees (UMN 2024): $29.75–$38.70 per space per year.
- Independent producers carry the full price risk.

## 3. Markets and pricing

**CME Lean Hog futures (HE):**
- Contract size: 40,000 lb × CME Lean Hog Index, quoted in $/cwt carcass.
- Tick: $0.00025/lb = $10. $1/cwt = $400 per contract.
- Cash-settled. Last trading day is the 10th business day of the contract month.
- Months: Feb, Apr, May, Jun, Jul, Aug, Oct, Dec [VERIFY].
- Price limits have changed over time [VERIFY].
- [Rulebook ch.152](https://www.cmegroup.com/content/dam/cmegroup/rulebook/CME/II/150/152/152.pdf)

**CME Lean Hog Index:**
- Built from LM_HG201: producer-sold barrows and gilts, Negotiated + Swine/Pork Market Formula (SPMF) + Negotiated Formula.
- Two-day weighted average: Σ(head × carcass wt × net price) ÷ Σ(head × carcass wt).
- So it can be reproduced from the AMS API.
- Index history is free on CME DataMine; futures history is paid.

**USDA AMS Livestock Mandatory Reporting (MARS slugs):**

| Report | Description | Slug |
|---|---|---|
| LM_HG201 | Prior-day slaughtered swine | 2511 |
| LM_HG203 | National daily direct hog (afternoon) | 2675 |
| LM_PK602 | Afternoon pork cutout | 2498 |

Handout: <https://ams.prod.usda.gov/sites/default/files/media/LMRPorkPriceReportsHandout.pdf>

**Hedging:**
- Short HE futures, buy puts, or use collars.
- Basis = local cash − nearby futures. It's local and seasonal, so the user enters it or it's estimated from history.
- Packer contracts often price off the Index.

**Livestock Risk Protection (LRP) – Swine (USDA RMA):**
- A put-like floor: indemnity = (coverage price − ending value) × target weight × head.
- Endorsements run 13–52 weeks, with ~35–50% premium subsidy [VERIFY against RMA].

## 4. Supply projections

**NASS Quarterly Hogs and Pigs** (Mar/Jun/Sep/Dec 1; released late in the month; files on ESMIS named `hgpgMMYY.txt`):
- Categories:
  - All hogs, breeding herd and market hogs.
  - Market hogs by weight class: <50, 50–119, 120–179, 180+ lb.
  - Pig crop and pigs per litter.
  - Two quarters of farrowing intentions.
- Sep 1, 2026 report:
  - All hogs 74.3M (−2% year over year).
  - Breeding herd 5.87M, the lowest since 2014.
  - Market hogs 68.4M.
  - Jun–Aug pig crop 34.5M.
  - Sep–Nov farrowing intentions 2.85M.

**Inventory → slaughter rule of thumb** [VERIFY; calibrate by regression]:

| Weight class | Expected slaughter window |
|---|---|
| 180+ lb | 0–6 weeks |
| 120–179 lb | 1.5–3 months |
| 50–119 lb | 3–4.5 months |
| <50 lb | 4.5–6 months |
| Pig crop | ~6 months later (quarter +2) |
| Farrowing intentions × pigs/litter | 9–12 month view |

Adjust for survival (95–97%), Canadian feeder imports (~6–7M/yr [VERIFY]) and sow slaughter.

**USDA outlook:**
- WASDE (monthly, ~9th–12th). Oct 2026 WASDE:
  - 2026 pork production −150M lb.
  - 2027 pork production −245M lb.
  - Q4 2026 barrows-and-gilts price $55/cwt live.
- ERS Livestock, Dairy, and Poultry Outlook: PDF + XLSX.
- ERS Livestock & Meat Domestic Data: ZIP/CSV.
- ERS Meat Price Spreads.

**Seasonality:**
- Prices peak May–Aug and bottom in November: CME indices ≈ 1.11 in June, 0.90 in November (old data, so recompute).
- Slaughter is heaviest in Q4; carcass weights are highest in winter.

## 5. Free data APIs

| Source | Endpoint | Key | Notes |
|---|---|---|---|
| AMS MyMarketNews (MARS) | `https://marsapi.ams.usda.gov/services/v1.2/reports/{slug}?q=report_begin_date=MM/DD/YYYY:MM/DD/YYYY&allSections=true` | Free key, sent as HTTP Basic `auth=(KEY, "")` | JSON. 100k rows registered vs 5k unregistered. API version [VERIFY] |
| AMS LMR Datamart | `https://mpr.datamart.ams.usda.gov/services/v1.1/reports/2511/Barrows/Gilts?q=report_date=MM/DD/YYYY:MM/DD/YYYY` | **none** (verified 2026-10-19) | LMR reports only (no grain). 3 years of HG201 ≈ 6k rows in ~8 s. Rebuilt index matches CME to the cent (75.75, Oct 12 2026) when dated by the first of its two slaughter days |
| NASS Quick Stats | `https://quickstats.nass.usda.gov/api/api_GET/?key=KEY&commodity_desc=HOGS&...&format=JSON` | Free | 50k-record cap; call `get_counts` first |
| NASS ESMIS files | `https://esmis.nal.usda.gov` (hgpg*.txt) | none | Faster than Quick Stats for weight classes |
| ERS | XLSX/CSV downloads | none | No REST API |
| FRED | `api.stlouisfed.org/fred/series/observations` | Free | Monthly only (WPS0132 etc. [VERIFY]) |
| CME | DataMine | Account | Index files free, futures paid; no free quote API |
| Barchart OnDemand | getHistory | Paid (~$500/mo, per a third party) | |

## 6. Existing tools and gaps

**Existing:**
- Iowa State: ELR, Ag Decision Maker budgets, Livestock Crush Margin app, IPIC scheduling spreadsheet.
- Missouri G688 and K-State budgets.
- Records software: PigCHAMP, MetaFarms, Cloudfarms.
- Advisory services: CIH, StoneX, Ever.Ag.

**Gaps:**
1. No free tool connects NASS inventory → slaughter forecast → price forecast → farm P&L.
2. Budgets are static and their prices go stale.
3. Few tools combine weekly herd-flow simulation with hedge/LRP overlays and Monte Carlo.
4. Contract and independent scenarios are rarely compared side by side.
5. Records tools are strong on biology and weak on markets.

## 7. Modeling approaches

1. **Herd flow (weekly cohorts):**
   - Sows → farrowings (sows × litters/yr ÷ 52) → born alive → pre-wean mortality → weaned → nursery → finish (ADG curve) → sold at target weight.
   - Feed by phase via FCR.
   - Gestation lag of 114 days.
2. **Price:**
   - Futures curve + basis as the expected value.
   - Monte Carlo with GBM or Ornstein-Uhlenbeck on log price.
   - Hogs, corn and SBM correlated via Cholesky.
   - Outputs: margin distribution, P(breakeven), VaR.
3. **Seasonality:** STL decomposition, or ratio-to-moving-average indices.
4. **Supply → price:**
   - Regress price change on projected slaughter change.
   - Price flexibility ≈ −1.5 to −2.5 [VERIFY, re-estimate].
5. **Scenarios:** productivity, feed, futures and disease/export shocks, plus hedge and LRP overlays.
6. **Validation:** back-test against ISU ELR and WASDE/ERS; reconcile the computed Index with CME's published value.
