# Hog Projections: Wean-to-Finish Group Projection

Project the **final costs, revenue and profit** for a group of weaned pigs, from placement to
market. The default is a **2,400-head** wean-to-finish group.

- **Feed:** local **corn, soybean meal and DDGS** prices, for Northwest Iowa, Southwest Minnesota,
  Central South Dakota and 9 other Midwest locations. Corn and meal are priced as CBOT futures
  plus local **basis**.
- **Weaned pigs:** the weekly **USDA weaned pig price**. Cash (open market, largest lots) or
  formula, or type your own.
- **Barn and labor:** costs by location (rent per space or a grower fee; hours × wage or $/pig).
- **Hog revenue:** **CME Lean Hog futures** for when each load sells (4–6 months out), plus the
  **average historical basis** (CME Lean Hog Index − futures) for that time of year.
- **Two outputs:** an easy-to-read **dashboard**, and an **Excel workbook** whose inputs you
  can change.

## Just want the spreadsheet?

Open **`W2F_Projection.xlsx`** in the project folder. Pick a feeding location from the dropdown
on the **Inputs** sheet and change any yellow cell; the whole workbook recalculates. The app's
**Excel** tab downloads the same workbook filled in with your current dashboard inputs.

## Quick start (no programming needed)

1. **Get the code.** Either:
   - click the green **Code → Download ZIP** button on GitHub and unzip it, or
   - run `git clone https://github.com/CalebSmit/HogProjections-.git`.
2. **Start the app** by double-clicking the launcher for your computer:

   | Computer | Double-click |
   |---|---|
   | Windows | `run.bat` |
   | Mac | `run.command` (first time: right-click → **Open** → **Open**) |
   | Linux | `./run.sh` in a terminal |

3. Your browser opens at <http://localhost:8501>. To stop the app, close the black terminal window.

The first launch takes a minute or two. It downloads [uv](https://docs.astral.sh/uv/), the right
Python and the app's libraries into the project folder. Later launches take seconds.

## Using the dashboard

| Tab | What it's for |
|---|---|
| **Summary** | Profit or loss, breakeven $/cwt, cost and revenue per head, cost breakdown, each sale, and a corn × hog price "what if" grid |
| **Inputs** | Futures prices, feed budget by phase, death loss, yield, barn and labor method, other costs, when pigs sell, hog futures and basis |
| **Locations** | Net per head at every location side by side. Edit corn basis, meal basis, DDGS, barn rent and wage; add your own locations; **Save** |
| **Markets & basis** | Corn and meal basis by location vs CBOT, cash prices, hog basis history by year, USDA weaned pig prices |
| **Excel** | Download the projection as a workbook. Yellow cells are inputs; everything else is formulas |

The left sidebar sets the group: location, head placed, placement date and the weaned pig price
source (USDA cash, USDA formula or manual). Click **Refresh market data** to pull the latest prices.

## Live data (optional)

The app works offline with the bundled defaults. With internet it pulls:

| Data | Source | Key needed? |
|---|---|---|
| Lean hog futures, corn and meal futures | Yahoo Finance (delayed) | No |
| CME Lean Hog Index history (for basis) | Rebuilt from USDA report LM_HG201 | No |
| Weaned pig price, cash and formula | USDA National Direct Feeder Pig Report (2810) | **Free key**: get one at <https://mymarketnews.ams.usda.gov/mymarketnews-api> and paste it into the `.env` file as `USDA_MMN_API_KEY=...` |

**About the "2,400 head" lot size:** recent USDA reports show lot sizes of under 600, 600–1,200
and over 1,200 head. If a 2,400+ group is in the report the app uses it; otherwise it uses the
largest group and says so on screen.

## Where the default numbers come from

Every default (feed prices, basis, barn rent, wages, death loss, feed budget, costs) is listed
with its source in [`docs/research/w2f-inputs.md`](docs/research/w2f-inputs.md). Values marked
**[ESTIMATE]** or **[VERIFY]** are reasonable starting points, not facts. Replace them with your
own numbers on the Inputs and Locations tabs.

## Troubleshooting

- **Mac says the file "can't be opened":** right-click `run.command` → **Open**. If you
  downloaded a ZIP, run `xattr -d com.apple.quarantine run.command` in Terminal.
- **Windows SmartScreen warning:** click **More info → Run anyway**.
- **"Port already in use":** the app is already running. Open <http://localhost:8501>.
- **Numbers say "basis history isn't loaded":** connect to the internet and click
  **Refresh market data**.

---

## For developers

```bash
uv sync                      # install deps (incl. dev tools)
uv run streamlit run app.py  # run the app
uv run pytest                # tests (Excel parity tests need LibreOffice)
uv run ruff check . && uv run ruff format --check . && uv run pyright
```

Source-of-truth docs for the build:

| Doc | Purpose |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Working rules for AI agents and humans, plus the lessons log |
| [`docs/PRD.md`](docs/PRD.md) | What we're building and why; open questions |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Code map, data flow, invariants |
| [`docs/PLAN.md`](docs/PLAN.md) | Phased plan with verification checks |
| [`docs/PROGRESS.md`](docs/PROGRESS.md) | Session-by-session log |
| [`docs/research/`](docs/research/) | Domain, data-source and tooling research |
| [`docs/decisions/`](docs/decisions/) | Architecture decision records |
