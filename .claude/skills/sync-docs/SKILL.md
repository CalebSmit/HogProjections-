---
name: sync-docs
description: Keep the source-of-truth docs (PRD, ARCHITECTURE, PLAN, PROGRESS) in line with the code. Use after finishing a plan step, after any deviation from the PRD/architecture/plan, or at the end of a session.
---

1. Diff the work against the docs: `git diff main...HEAD --stat`, plus the uncommitted changes.
2. For each doc, ask: does it still describe reality?
   - `docs/PLAN.md`: tick completed steps (only if their `verify:` passed); add, re-order or
     re-cut steps if the approach changed.
   - `docs/ARCHITECTURE.md`: code map rows (path, role, status), the mermaid diagram, invariants.
   - `docs/PRD.md`: scope, features or success criteria that changed because of what was learned.
3. Every doc you edit gets a dated line in its `## Changelog`, saying *what* changed and *why*.
4. A big or hard-to-reverse choice gets an ADR: `docs/decisions/NNNN-title.md`
   (Status / Context / Decision / Alternatives / Consequences).
5. Append a session entry to `docs/PROGRESS.md` (Done / Verified / Notes / Next).
6. Commit the doc changes together with the code they describe.
