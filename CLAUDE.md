# CLAUDE.md

Hog production projections and financials, as a Streamlit app. The person it's for is
non-technical: they clone or download the repo and double-click `run.bat` / `run.command`.

## Source of truth (read before building)

1. `docs/PRD.md`: what and why. Scope questions are settled here.
2. `docs/ARCHITECTURE.md`: code map, data flow, invariants.
3. `docs/PLAN.md`: phases and steps, each with a `verify:` check. Work on the first unchecked step.
4. `docs/PROGRESS.md`: append one entry per session.

**Deviating is fine. Silent deviation is not.** If the code needs to differ from the PRD,
architecture or plan, update that doc *in the same commit* and add a line to its Changelog.
Larger choices get an ADR in `docs/decisions/`. Use the `sync-docs` skill.

## UI rules (see `docs/DESIGN.md`)

- Build pages from `hogproj.ui` ("Field Report"): `masthead` with a finding headline, inputs in
  an `assumption_bar` of popover chips (labels through `md()`), one `hero` with `quote` +
  `stat_strip` + signature chart, then unboxed charts with `chart_title` / `source_note`.
  No emoji, no inputs in the sidebar, no raw hex outside `ui.py`/`export.py`, no dual axes.
- After any UI change, restart the server and screenshot every touched page before claiming
  it's done.

## Commands

```bash
uv sync                                  # install / update env
uv run streamlit run app.py              # run app (http://localhost:8501)
uv run pytest -q                         # tests
uv run ruff check . --fix && uv run ruff format .
uv run pyright                           # types
```
Definition of done = all four pass, plus the app renders (`tests/test_smoke.py` covers this).
Use the `verify` skill.

## Rules

- **Think before coding.** State your assumptions. If the PRD is ambiguous, ask; don't guess.
- **Simplicity first.** Keep the structure flat and the modules few. No factories, plugin systems
  or config frameworks. If 200 lines could be 50, rewrite it.
- **Surgical changes.** Every changed line should trace back to the current plan step.
- **Goal-driven.** Write the test or check first, then loop until it passes. Show the output;
  don't just say it works.
- **Model code is pure.** `herd`/`finance`/`markets` take inputs and return DataFrames.
  No Streamlit, network or file I/O in them. I/O goes in `data/` modules; the UI goes in `app.py`/`views/`.
- **Units in names.** `price_cwt_carcass`, `weight_lb_live`, `cost_usd_per_head`. Live and
  carcass prices differ by ~0.75; mixing them up is the #1 domain bug.
- **Offline first.** The app must work with no API keys or network, using `data/sample/`.
  Every live fetch falls back to sample or cached data, with a visible notice.
- **Never commit secrets** (`.env`, `.streamlit/secrets.toml`) or `data/cache/`.
- **The recipient path is sacred.** A change that breaks `run.bat`/`run.command`, or needs a
  manual install step, is a bug. Add dependencies with `uv add`, never pip.
- Defaults for biology and finance come from `docs/research/domain.md`. Cite the source in a
  comment next to the constant. Anything marked [VERIFY] there stays a user-editable input.

## Lessons log

Add a one-line rule here each time something goes wrong (Boris-style). Prune stale rules.
Longer write-ups go in `docs/PROGRESS.md`.

- hatchling fails to build if `readme = "README.md"` points to a missing file. Keep README present.
- `UV_NATIVE_TLS` deprecation warning in the cloud sandbox is harmless noise.
- Streamlit markdown treats `$...$` as LaTeX. Escape dollars (`\$`) in captions/markdown.
- Streamlit doesn't hot-reload `hogproj` (it's an installed package). Restart the server after
  model edits, and stop it before `uv run`/`uv sync` on Windows (it locks the venv).
- With `st.navigation`, keep pages out of a folder named `pages/` or the legacy auto-nav shows.
- Widget state is dropped when its page isn't shown. Key widgets `herd_*`/`cost_*`; `app.py`
  re-assigns them each run.
- `st.page_link` only resolves inside the router: smoke-test pages via `app.py` + `switch_page`.
- Screenshot without the Chrome extension: `uv run --no-project --with playwright` driving the
  installed Edge (`channel="msedge"`); plain `--headless --screenshot` only catches the skeleton.
- In raw-HTML `st.markdown`, write `&#36;` for "$" (backslash escapes show literally there).
- The repo lives in OneDrive. If `uv add/sync` fails with "Access is denied" on an empty
  `hogproj-*.dist-info`, `mv` it out of `site-packages` and re-run. Never kill python.exe
  processes you didn't start; other projects run on this machine.
- Theme font names with a bare number ("Source Sans 3") break Streamlit's font CSS; use names
  like "IBM Plex Sans". Screenshot audits need a tall viewport (Streamlit scrolls internally).
- usda.gov, iastate.edu and cmegroup.com may be blocked from cloud sandboxes. Build API clients
  against recorded fixtures in `tests/fixtures/` and verify live calls on a real machine.
- Pyright must not infer pandas types from its source (`useLibraryCodeForTypes = false`): the
  inference was order-dependent, so adding an unrelated module flipped errors in old files.
- With 14+ pages `st.navigation` hides some behind "View N more"; keep `expanded=True`.
- Column dividers must be the `.hp-vrule` class (hidden under 640 px). Inline-style dividers
  became 400 px empty gaps on phones, and attribute selectors don't match Streamlit's markup.
- USDA PDFs (feeder pigs, Iowa grain, feedstuffs) only hold the latest issue; parse by token
  type, not column position, and let the cache build history. Save the extracted text as a
  fixture whenever a parser changes.
- Weekly series line up on week ending Friday; placements are the Monday before (−4 days).
  Year-ago comparisons use 364 days so weekdays match.
- A % change across zero (margins) is meaningless: show the $ change instead.
- Run `scripts/screenshots.py` (all pages × 1440/390 px) before every commit that touches views.
- Never put Pipestone's internal numbers or licensed futures data in the public repo; they live
  in the git-ignored `reference/` folder (incl. a loadable setup JSON).
- Inputs whose default is live data must use `ui.live_number` and be read with `user_value`;
  a plain keyed `number_input` stores its default and it goes stale after a refresh.
