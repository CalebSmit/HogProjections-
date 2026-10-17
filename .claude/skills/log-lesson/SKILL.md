---
name: log-lesson
description: Record a mistake, gotcha or environment quirk as a one-line rule in CLAUDE.md's Lessons log so it doesn't happen again. Use whenever a check fails for a non-obvious reason, the user corrects you, or you discover a surprising behavior.
---

1. Write the lesson as a rule, not a story: what to do or avoid, plus the reason in a few words.
   Good: "MARS API dates are MM/DD/YYYY; ISO dates silently return 0 rows."
2. Append it under `## Lessons log` in `CLAUDE.md`. If an existing line covers it, refine that line.
3. Keep CLAUDE.md under ~150 lines. If it's getting long, delete lessons that are now enforced
   by a test or hook, or that no longer apply.
4. If the lesson needs more than one line of context, add the detail to the current
   `docs/PROGRESS.md` entry and keep the CLAUDE.md line short.
5. If it can be enforced mechanically (a test, a ruff rule, a hook), prefer that, and mention it.
