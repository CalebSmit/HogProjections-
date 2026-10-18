# CLAUDE.md

Wean-to-finish hog group projection (costs, revenue, breakeven) as a Streamlit dashboard
plus a live-formula Excel workbook. The person it's for is an accountant at Pipestone, not a
programmer: they clone or download the repo and double-click `run.bat` / `run.command`.

## Source of truth (read before building)

1. `docs/PRD.md`: what and why. Scope questions are settled here.
2. `docs/ARCHITECTURE.md`: code map, data flow, invariants.
3. `docs/PLAN.md`: phases and steps, each with a `verify:` check. Work on the first unchecked step.
4. `docs/PROGRESS.md`: append one entry per session.

**Deviating is fine. Silent deviation is not.** If the code needs to differ from the PRD,
architecture or plan, update that doc *in the same commit* and add a line to its Changelog.
Larger choices get an ADR in `docs/decisions/`. Use the `sync-docs` skill.

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
- **Model code is pure.** `inputs`/`model`/`basis`/`charts` take inputs and return values,
  DataFrames or figures. No Streamlit, network or file I/O in them. I/O goes in `data/`;
  the UI goes in `app.py`.
- **Excel mirrors the model.** Any formula change in `model.py` needs the same change in
  `excel.py`; `tests/test_excel.py` must stay green.
- **Units in names.** `price_cwt_carcass`, `weight_lb_live`, `cost_usd_per_head`. Live and
  carcass prices differ by ~0.75; mixing them up is the #1 domain bug.
- **Offline first.** The app must work with no API keys or network, using `data/sample/`.
  Every live fetch falls back to sample or cached data, with a visible notice.
- **Never commit secrets** (`.env`, `.streamlit/secrets.toml`) or `data/cache/`.
- **The recipient path is sacred.** A change that breaks `run.bat`/`run.command`, or needs a
  manual install step, is a bug. Add dependencies with `uv add`, never pip.
- Defaults come from `docs/research/w2f-inputs.md` (and `domain.md`). Cite the source next to
  the value. Anything marked [VERIFY] or [ESTIMATE] stays a user-editable input.
- Streamlit markdown reads `$...$` as LaTeX. Use `md_money()` (or `\$`) for dollar amounts
  in `st.markdown`, `st.caption`, `st.success` and similar text.

## Lessons log

Add a one-line rule here each time something goes wrong (Boris-style). Prune stale rules.
Longer write-ups go in `docs/PROGRESS.md`.

- hatchling fails to build if `readme = "README.md"` points to a missing file. Keep README present.
- `UV_NATIVE_TLS` deprecation warning in the cloud sandbox is harmless noise.
- usda.gov, iastate.edu and cmegroup.com may be blocked from cloud sandboxes. Build API clients
  against recorded fixtures in `tests/fixtures/` and verify live calls on a real machine.
- LibreOffice headless won't recalculate xlsxwriter files (it keeps the cached 0s) unless the profile
  sets `OOXMLRecalcMode=0`. See `tests/test_excel.py::recalc`.
- Excel formulas use named ranges (`HeadPlaced`, `CornCash`...). When a model formula changes,
  change `excel.py` too. `test_excel.py` compares the two.
- Never pipe checks through `tail` inside an `&&` chain: the pipe hides the exit code (a red
  pyright got committed once). Chain `uv run pyright >/dev/null && ...` instead.
- pandas 3's type hints make pyright fail on groupby/rolling chains. For small aggregations,
  use plain dicts or `.to_dict("records")` (see `data/leanhog.py::cme_index`).
- Streamlit `st.data_editor`: never assign its output back to its input (`ss.x = st.data_editor(ss.x)`).
  The widget identity changes and the user's next edit is silently dropped. Keep a fixed base frame
  and parse the output (`tables.py`). Regression tests in `tests/test_smoke.py` send real edits.
- A cleared cell arrives as NaN, and pydantic accepts NaN floats by default. Models use
  `allow_inf_nan=False` (`inputs.Strict`).
- A long-running `streamlit run` keeps old `hogproj` modules imported. Restart it after
  changing package code before taking screenshots.
