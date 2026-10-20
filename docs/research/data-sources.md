# Free data sources — verified 2026-10-19/20

Every row below was tested with real HTTP requests (no keys) unless marked "key".

## USDA AMS LMR datamart (keyless, JSON) — the backbone

`GET https://mpr.datamart.ams.usda.gov/services/v1.1/reports` lists 151 reports.
Query: `/reports/{slug}/{Section}?q=report_date=MM/DD/YYYY:MM/DD/YYYY` (URL-encode `/` in section
names). Values arrive as strings, head counts with commas. No range limit found below the
99,999-row cap.

| Report | Slug | Sections | Use | History |
|---|---|---|---|---|
| LM_PK602 pork cutout (afternoon) | 2498 | `Cutout and Primal Values`, `Current Volume` | cutout + primals (`pork_carcass, pork_loin, pork_butt, pork_picnic, pork_rib, pork_ham, pork_belly`), loads | 2013 → |
| LM_HG201 prior-day slaughtered | 2511 | `Barrows/Gilts` (in use), `Summary` (head), `Carcass Measurements` (`avg_carcass_weight, avg_backfat, avg_loin_depth, standard_lean_yield`), `14-Day Scheduled Swine` | index, slaughter, weights, packer bookings | 2010 → |
| LM_HG218 prior-day hog (national + regional) | 3458 | `National Volume and Price Data`, Iowa/Minnesota, WCB, ECB | regional prices | Dec 2020 → |
| LM_HG234 daily sows and boars | 3452 | `National Volume and Price Data` (`weight_range, wtd_avg, head_count`) | sow prices; liquidation signal | Dec 2020 → (LM_HG230 slug 2676 for 2010–2020) |
| LM_HG214 weekly national swine | 2524 | negotiated sows; barrows/gilts by purchase type | weekly series | 2010 → |
| LSDLM_PK680 weekly comprehensive cutout | 2680 | `Sow and Boar Values` | sow carcass value | 2019 → |

Retired: LM_HG200, HG202–212, HG230–233 (stopped Dec 2020); HG213 slaughter cost (May 2025).

## USDA AMS public PDFs (keyless; latest issue only)

| Report | URL `https://www.ams.usda.gov/mnreports/…` | Gives |
|---|---|---|
| National Direct Feeder Pig | `ams_2810.pdf` | weaned / 40 lb pig prices (in use) |
| Daily Livestock Slaughter (estimated FI) | `ams_3208.pdf` | daily hog slaughter estimate |
| Actual FI slaughter (weekly) | `ams_3658.pdf` | weekly slaughter |
| Iowa Daily Cash Grain Bids | `ams_2850.pdf` | Iowa state average cash corn/soybeans; CBOT settlements |
| Iowa Production Cost (bi-weekly) | `ams_2863.pdf` | Iowa feed ingredient prices |
| National Grain & Oilseed Processor Feedstuff | `ams_3511.pdf` | soybean meal 46.5–48% by location |
| National Weekly Grain Co-Products | `ams_3618.pdf` | DDGS by state (Iowa) |

The old `.txt` versions still answer 200 but stopped updating (2020–2024). The MARS JSON API
(`marsapi.ams.usda.gov/services/v1.2/reports/{slug}`) serves the same reports with history but
returns 403 without a My Market News key.

## Monthly / annual (keyless)

- **ERS Livestock & Meat Domestic Data** — `https://www.ers.usda.gov/media/5539/livestock-domestic-data-machine-readable-files.zip`:
  `Meat-Statistics.csv` (slaughter, weights, production, cold storage; 1907 → Aug 2026),
  `LivestockPrices.csv`, `WholesalePrices.csv`, `Meat-Supply-Disappearance.csv`.
- **ERS pork values and spreads** — `https://www.ers.usda.gov/media/5026/pork-values-and-spreads.csv`
  (retail / wholesale / farm value, farmer's share; → Sep 2026). `/media/NNNN/` ids can change.
- **WASDE** — `https://www.usda.gov/oce/commodity/wasde/wasdeMMYY.xml` (recent issues only;
  history via ESMIS). Pork production and barrow/gilt price forecasts by quarter.
- **FAS PSD** — `https://apps.fas.usda.gov/psdonline/downloads/psd_livestock_csv.zip` (US pork
  production, exports, imports by market year, 1960 → forecasts).

## Key required (free)

- **NASS Quick Stats** (in use): Hogs & Pigs, Iowa corn price received; candidates to confirm with
  `get_param_values`: commercial hog slaughter (head, live weight), pork and belly cold storage.
- **My Market News / MARS**: history for every AMS report above.
- **FRED** (prime rate), **EIA** (diesel; keyless XLS also exists), **FAS ESR** (weekly pork export sales).

## Futures

No free licensed source. CME blocks automated access; DataMine and Barchart are paid. Yahoo's
unofficial chart endpoint works (`HEJ27.CME` etc.) but its terms prohibit automated/commercial
use, so the app does **not** use it: contract prices are typed in with an as-of date. CBOT corn
and SBM settlements are printed in the AMS grain PDFs (2850, 3618) and can be read from there.
