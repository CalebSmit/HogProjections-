# ADR 0003: Template with local profiles, Barchart-first data, weekly crush in the model

- **Status:** accepted (2026-10-19)

## Context

The owner's own "USDA Wean Pig Crush" workbook holds company cost settings, a weaned pig price
adder, a ration and Barchart data. The owner said company figures must not go in the GitHub
repo, and that the app should be a template anyone (Pipestone or another system) can fill in.
They want both data sources, and lots of toggles.

## Decision

1. **Template defaults.** Generic research-based defaults ship in the repo. Company numbers live
   in **named settings profiles** (JSON in `data/user/profiles/`, gitignored), saved and loaded
   from the sidebar. Profiles hold settings only (costs, ration, toggles), never market prices,
   which change daily.
2. **Data order.** The user's Barchart imports come first (`data/cache/barchart/`, never
   committed, per Barchart's terms), then the cache, then the free USDA/Yahoo pulls. If lean hog
   contract histories are imported, basis is measured against the exact contract the projection
   prices off.
3. **The crush runs the model.** Each weekly crush column is a full `project()` with a single
   sale, so the crush, the group projection and the Excel crush (parity-tested) agree by
   construction. No second formula set is kept in Python.
4. **Both conventions as toggles:**
   - mortality as % of head (default) or $/pig;
   - interest as a rate or $/pig;
   - ration by phase or whole-group lb.

## Consequences

- A fresh clone shows generic numbers until the user loads their profile. That's intended.
- Excel holds one crush formula set, which mirrors `crush_table`. Any model change needs both,
  and the tests enforce it.
