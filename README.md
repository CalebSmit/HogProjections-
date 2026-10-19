# Hog Projections

Hog production projections and financials: herd flow, cost of production, market prices and
profit scenarios. It runs in your web browser on your own computer.

> **Status:** early build. See [`docs/PLAN.md`](docs/PLAN.md) for which phases are done.

## Quick start (no programming needed)

1. **Get the code.** Either
   - click the green **Code → Download ZIP** button on GitHub and unzip it, or
   - run `git clone https://github.com/calebsmit/HogProjections-.git`
2. **Start the app** by double-clicking the launcher for your computer:

   | Computer | Double-click |
   |---|---|
   | Windows | `run.bat` |
   | Mac | `run.command` (first time: right-click → **Open** → **Open**) |
   | Linux | `./run.sh` in a terminal |

3. Your browser opens at <http://localhost:8501>. To stop the app, close the black terminal window.

The first launch takes a minute or two. It downloads [uv](https://docs.astral.sh/uv/), the
right version of Python and the app's libraries into the project folder. It doesn't change
anything else on your computer. Later launches take a few seconds.

## Optional: live USDA data

**Hog prices need no key.** When you're online the app pulls the daily USDA hog report and
rebuilds the CME Lean Hog Index itself. Offline, it uses the last data it saved, or the sample
data that ships with the app.

Two free keys unlock more data (planned features). Paste them into the `.env` file in this
folder, after the `=` sign, with no spaces or quotes. The launcher creates `.env` the first
time it runs. Never share the keys or commit `.env`.

| Key | Unlocks | Where to get it (free) |
|---|---|---|
| `USDA_MMN_API_KEY` | Corn and soybean meal prices (USDA My Market News) | <https://mymarketnews.ams.usda.gov/mymarketnews-api> |
| `NASS_API_KEY` | Quarterly Hogs & Pigs inventory (USDA NASS) | <https://quickstats.nass.usda.gov/api> |

## Troubleshooting

- **Mac says the file "can't be opened":** right-click `run.command` → **Open**. If you
  downloaded a ZIP, you may need to run `xattr -d com.apple.quarantine run.command` in Terminal.
- **Windows SmartScreen warning:** click **More info → Run anyway**.
- **Port already in use:** another copy is already running. Close it, or open
  <http://localhost:8501>.

---

## For developers

```bash
uv sync                      # install deps (incl. dev tools)
uv run streamlit run app.py  # run the app
uv run pytest                # tests
uv run ruff check . && uv run ruff format --check . && uv run pyright
```

Project docs (the source of truth for the build):

| Doc | Purpose |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Working rules for AI agents and humans, plus the lessons log |
| [`docs/PRD.md`](docs/PRD.md) | What we're building and why |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Code map, data flow, invariants |
| [`docs/PLAN.md`](docs/PLAN.md) | Phased plan with verification checks |
| [`docs/PROGRESS.md`](docs/PROGRESS.md) | Session-by-session log |
| [`docs/research/`](docs/research/) | Domain and tooling research |
| [`docs/decisions/`](docs/decisions/) | Architecture decision records |
