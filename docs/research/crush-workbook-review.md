# Review: owner's "USDA Wean Pig Crush" workbook (9/25/26)

*Reviewed 2026-10-19. The owner built this before the app. This note records what it does, how it
differs from the app, and what to merge. No company figures appear here (owner's decision: the
app is a template; real numbers live in local settings profiles).*

## What the workbook is

A weekly **"crush" margin table** for wean-to-finish pigs. Each column is one weekly placement:
12 columns, the 12 most recent USDA report weeks. For each placement it computes $/pig revenue,
cost and margin.

| Sheet | Contents |
|---|---|
| `Sheet5` (the model) | **Settings** block: non-feed, non-pig costs per pig, labelled by quarter (e.g. "2026 Q2"). **Ration** block: lb per pig of corn, DDG, SBM and "other" ($/lb). **Weekly table** (described below). |
| `Sheet1` | An unfinished single-placement layout (USDA price, Pipestone adder, report date + 160 days, CME period, corn, SBM, "standard basis", projected revenue/expenses). |
| `CME Index` | Daily CME Lean Hog Index from Barchart (2024-07 → 2026-09). Column J holds a hand-typed futures price for 15 dates; column L holds notes such as "April CME as of 02/20/2026". |
| `Corn Spot Price - CF` | Barchart `CORN$.5328` daily cash corn; computed column = close **+ $0.20 cost of carry**. |
| `Soybean Meal - Prior to Basis` | Barchart `@SM` continuous futures, daily; no basis applied. |
| `USDA WP Price` | Barchart `LS255_CPEW10_12LTC_PR`: USDA LS255 early-weaned 10–12 lb, weekly; computed column = close **+ Pipestone adder** (a fixed $/head). |

The **weekly table** in `Sheet5` has these rows:

| Row | How it's computed |
|---|---|
| USDA report date | The date of each USDA report |
| Placement date | Report date + 1 |
| Avg marketing date | Placement + **160 days** |
| CME marketing period | Typed by hand |
| Corn futures | From the corn sheet |
| Corn % hedged, hedged price | Inputs |
| Corn basis | Input |
| Estimated cash corn | `(fut + basis)·(1 − %hedged) + hedged·%hedged` |
| SBM | Same rows and blend as corn |
| DDG | Typed $/lb × 2000 |
| Feed $/cwt | Ration lb × prices ÷ carcass cwt |
| Lean hog futures | Typed |
| Lean hog basis | CME Index − futures on the **same calendar point a year earlier** (one year only) |
| Revenue/cwt | Futures + basis |
| Revenue/head | Revenue/cwt × target weight × yield |
| Cost lines | Weaned pig (USDA + adder), feed, animal health, barn/labor, mortality ($/pig), G&A, freight out, operating interest, other/sales premiums |
| Margin/pig | Revenue − cost lines |
| Principal + term interest | Per pig |
| **Margin after principal payments** | Margin − principal − term interest |

## Check: the app reproduces it

One workbook column was put through `model.project()` with the workbook's own inputs (mortality
as a $/pig cost, a single whole-group ration, 100% sold at day 160). Revenue, feed, total cost and
margin per head **matched to the cent**. The actual figures are company data and are
intentionally not recorded here. `tests/test_crush_parity.py` locks in the same check with
synthetic numbers.

The workbook's hand-typed "CME marketing period" agrees with the app's ISU B2-41 contract rule
in all 12 columns, including Feb 14 → FEB and Feb 21 → APR.

## Differences

| Topic | Workbook | App today |
|---|---|---|
| Unit of analysis | 12 weekly placements side by side (trend view) | One group in detail (multiple sale cuts, cash flow, locations) |
| Weaned pig cost | USDA weekly close **+ Pipestone adder** | USDA cash/formula/manual + freight |
| Corn | Cash index + $0.20 carry, basis input, **% hedged + hedged price** | CBOT futures + location basis; no hedges |
| SBM | Futures, basis input, **% hedged + hedged price** | Futures + delivered basis by location |
| DDG | Typed weekly | Location table |
| Ration | One whole-group ration (lb/pig of each ingredient; other at $/lb) | 6 phases with inclusion %; other at $/ton |
| Non-feed costs | Pipestone closeout **settings by quarter**: animal health, barn/labor (combined), mortality **$ per pig**, **G&A**, freight out, interest **$ per pig**, other/sales premiums | Barn (rent or fee), labor (hours or fee), vet, utilities, trucking, insurance, interest (rate), checkoff; mortality as % of head |
| Debt service | **Principal + term interest per pig → margin after principal** | Not modelled |
| Marketing | One date (placement + 160 days), one weight | Several cuts with dates, % and weights |
| Hog basis | **One prior year**, picked by hand | Average of many years, by half-month; the year selector can reproduce "last year only" |
| Lean hog futures | Typed per column | Yahoo download or typed; missing contracts copied, with a flag |
| Data | **Barchart downloads** (owner has access) | USDA/Yahoo APIs (unverified live) |
| Locations | None (a single basis) | 12 Midwest locations, editable |
| Hedging | Corn and SBM | None |

**Fragilities in the workbook that the app avoids:**
- Hard VLOOKUP ranges (e.g. `$A$3:$F$485`) silently stop at old rows.
- `---` rows from Barchart give `#VALUE!` on holidays.
- The CME period is typed by hand.
- Basis comes from a single year.
- Futures are copied in by hand.

## What to merge

See PLAN Phase 7. In short:
1. Weekly crush table, in the app and as an Excel sheet.
2. Pipestone adder on the weaned pig price.
3. Closeout-style cost settings by quarter (G&A, mortality $/pig option, interest $/pig option,
   other/sales premiums).
4. Debt service, giving a "margin after principal payments" line.
5. Corn/SBM hedge % and hedged price.
6. Whole-group ration preset.
7. Barchart CSV import.
8. Corn price mode: cash + carry.
