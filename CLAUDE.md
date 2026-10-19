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
- usda.gov, iastate.edu and cmegroup.com may be blocked from cloud sandboxes. Build API clients
  against recorded fixtures in `tests/fixtures/` and verify live calls on a real machine.
