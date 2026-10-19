# Next steps on a real machine

A checklist for picking this up on a laptop with normal internet. The cloud sandbox it was
built in blocks USDA, CME and Yahoo, so the live-data checks (PLAN Phase 4) happen here.

## 1. Get the code

Until PR #1 is merged, the work lives on the `feature/w2f-projection` branch:

```bash
git clone -b feature/w2f-projection https://github.com/CalebSmit/HogProjections-.git
cd HogProjections-
```

After the merge, a plain `git clone` (or **Download ZIP** on GitHub) gets everything.

## 2. Run it

Double-click `run.bat` (Windows) or `run.command` (Mac). The first launch installs uv, Python
and the libraries, then opens <http://localhost:8501>.

## 3. Check the live data (one command)

1. Get a free USDA MyMarketNews key: <https://mymarketnews.ams.usda.gov/mymarketnews-api>.
   Paste it into `.env` as `USDA_MMN_API_KEY=...` (the launcher creates `.env` on first run).
2. Run:

   ```bash
   uv run python scripts/check_live.py --write-sample
   ```

   It reports PASS / WARN / FAIL for the hog basis, lean hog futures, corn and meal futures, and
   the USDA weaned pig report, using the same loaders as the dashboard.
3. Spot-check the hog basis against CME: the CME Lean Hog Index for a recent day should match
   within $0.05.
4. If the basis came down live, `--write-sample` saved `data/sample/hog_basis_daily.csv`.
   Commit it: offline users then get a real seasonal basis instead of the "no basis history"
   notice.
5. If the USDA report parsed oddly, `data/cache/usda_2810_raw.json` holds the raw response.
   Copy it to `tests/fixtures/` and adjust `src/hogproj/data/weanpig.py`.
6. If Yahoo stops serving lean hog contract symbols (for example `HEJ27.CME`), switch the curve
   source and record the decision in `docs/decisions/`.

Tick PLAN Phase 4 when these pass.

## 4. Developer loop

```bash
uv sync                                         # dev tools
uv run pytest -q                                # tests (Excel parity needs LibreOffice)
uv run ruff check . && uv run ruff format --check . && uv run pyright
```

With Claude Code, start from `CLAUDE.md`; it points to the PRD, architecture map, plan and
progress log, and the `verify` and `sync-docs` skills.

## 5. Questions only the owner can answer

From `docs/PRD.md` §7:

1. Is the USDA "over 1,200 head" lot bucket acceptable when no 2,400+ bucket is reported?
2. Should the default barn cost be a grower fee ($/pig placed) instead of rent + hourly labor?
3. The real phase feed budget (lb and inclusion rates) from a nutritionist. Save it as a local
   profile, not in the repo.
4. Merit premium and yield from the actual packer grid. Also a local profile.

## 6. Keep company figures out of git

Real costs, rations and imported Barchart data belong in local profiles (`data/user/`) and
imports (`data/cache/`), both gitignored. Never put them in code, tests or docs.
