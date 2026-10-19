# ADR 0002: W2F group scope, half-month basis, free data sources

- **Status:** accepted (2026-10-18)

## Context

The owner's idea is a single wean-to-finish group projection (2,400 head) with local feed
prices, barn and labor costs, the USDA weaned pig price, and hog revenue at futures plus
historical basis. It needs a dashboard and an Excel workbook.

## Decision

1. **Scope:** one group, deterministic projection plus a corn × hog what-if grid. No herd
   simulator and no Monte Carlo.
2. **Hog price:** futures for the contract that prices each sale date (ISU B2-41 rule), plus
   the average **half-month** basis = CME Lean Hog Index − nearby futures.
   - Half-month, not monthly, because basis jumps at contract roll (e.g. Feb 1–14 −$0.85 vs
     Feb 15–28 −$4.32, ISU B2-41 3-year averages).
   - Days between expiry and the 14th are dropped so the history and the pricing use the same
     contract.
3. **Index source:** rebuild the index from USDA LM_HG201 (keyless LMR Datamart). The
   alternative, CME DataMine, needs an account; CME's web endpoints block scripts.
4. **Futures:** Yahoo Finance chart API (free, delayed, keyless; unofficial). Futures can always
   be typed in by hand.
5. **Weaned pigs:** USDA report 2810 via MyMarketNews, which needs a free key. If the report
   has no 2,400+ bucket, the largest lot bucket is used, and the app says so.
6. **Excel:** generated with xlsxwriter as live formulas over named cells. Parity with Python
   is enforced by a LibreOffice recalculation test.

## Alternatives

- **Monthly basis:** simpler, but mixes two contracts in roll months.
- **ISU B2-41 IA/MN cash basis tables:** published, but a different cash series than the
  CME Index the owner asked for.
- **Paid feeds (Barchart, DataMine):** not free.
- **openpyxl formulas:** no advantage over xlsxwriter for writing.

## Consequences

- Live data paths can't be exercised from the cloud sandbox (hosts blocked). They are covered
  by fixture tests and must be verified once on a real machine (PLAN Phase 4).
- Yahoo is unofficial and could change. The manual-entry fallback protects the app.
