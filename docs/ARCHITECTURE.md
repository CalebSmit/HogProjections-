# Architecture

> Source of truth for code structure. Short on purpose (matklad style): a code map, the data
> flow and the invariants. Update it in the same commit as any structural change, and log it
> in the Changelog.
> **Current state:** Phases 2–3 (herd flow, costs & returns) built. The "Target" sections are the proposed design until the
> PRD is finalized.

## Bird's-eye view

```mermaid
flowchart LR
    subgraph Sources["Data sources (free)"]
        AMS[USDA AMS LMR datamart<br/>LM_HG201, no key]
        NASS[USDA NASS<br/>Quick Stats / Hogs & Pigs]
        ERS[USDA ERS / WASDE]
        SAMPLE[(data/sample<br/>bundled CSV)]
    end
    subgraph Data["hogproj.data — I/O only"]
        CLIENTS[API clients<br/>httpx + retries]
        CACHE[(data/cache<br/>parquet)]
    end
    subgraph Model["hogproj model — pure functions"]
        HERD[herd<br/>weekly cohort flow]
        FIN[finance<br/>cost, breakeven, P&L]
        MKT[markets<br/>index, seasonality, outlook]
        RISK[risk<br/>scenarios, Monte Carlo, hedge/LRP]
    end
    subgraph UI["Streamlit — app.py + views/"]
        INPUTS[Assumption editors]
        VIEWS[Charts & tables]
        EXPORT[Excel export]
    end
    AMS & NASS & ERS --> CLIENTS --> CACHE
    SAMPLE --> CACHE
    CACHE --> MKT
    INPUTS --> HERD --> FIN
    MKT --> FIN --> RISK
    HERD & FIN & MKT & RISK --> VIEWS --> EXPORT
```

## Code map

| Path | Role | Status |
|---|---|---|
| `app.py` | Router (`st.navigation`) + home page; keeps widget state across pages | done |
| `views/` | One file per page. Not `pages/`: that name triggers Streamlit's legacy auto-nav | started |
| `src/hogproj/config.py` | Paths + `Settings` (env / `.env`) | done |
| `src/hogproj/data/ams.py` | Keyless LMR datamart client (LM_HG201); live → `data/cache` → `data/sample` | done |
| `src/hogproj/herd.py` | Weekly cohort herd flow; pipeline starts in steady state | done |
| `src/hogproj/finance.py` | ISU ELR line-item cost per pig, breakeven, sensitivity, weekly returns | done |
| `src/hogproj/markets.py` | Lean Hog Index from HG201, monthly seasonal factors | done |
| `src/hogproj/outlook.py` | Whole-farm `Plan` (herd + cost + price path): projection, 12-month summary, monthly rollup, profit drivers | done |
| `src/hogproj/ui.py` | Shared page helpers: cached data load, notices, `usd()` formatting | done |
| `src/hogproj/risk.py` | Monte Carlo profit (fitted hog AR(1) + corn walk), price-floor payoff | done |
| `src/hogproj/export.py` | Excel report builder (xlsxwriter, returns bytes) | done |
| `data/sample/` | Committed datasets so the app runs offline (3 years of HG201, ~240 KB) | started |
| `tests/` | pytest. `test_smoke.py` renders the app headless | started |
| `run.bat`, `run.command`, `run.sh` | Recipient launchers | done |

## Invariants

- **Layering:** UI → model → (nothing); UI → data → network/disk. Model modules never import
  `streamlit`, `httpx` or `data`.
- Model functions are deterministic given their inputs. Randomness takes an explicit `seed`.
- Every quantity carries its unit in its name. Prices are $/cwt and state `live` or `carcass`.
- The app starts and every page renders with `OFFLINE=true` and no `.env`.
- Inputs cross into the model as pydantic models. Results come back as pandas DataFrames.
- Pages share model inputs through `st.session_state["herd_inputs"]` / `["cost_inputs"]` /
  `["seasonal"]`, read via `ui.current_plan()`, not by re-reading each other's widgets.
- `outlook.synced()` copies herd facts (weight, yield, pigs sold per sow) into the cost model;
  always project through it so the two pages can't disagree.

## Changelog
- 2026-10-17: Initial scaffold and proposed target design.
- 2026-10-19: Added `data/ams.py`, `markets.py`, `ui.py` and the Market prices page. Tests
  force `OFFLINE=true` (tests/conftest.py).
- 2026-10-19: Added herd/finance modules and two pages; pages live in `views/` behind an
  `st.navigation` router in `app.py` (so the sidebar says "Home", not "app").
