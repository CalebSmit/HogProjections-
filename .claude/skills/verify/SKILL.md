---
name: verify
description: Run the full definition-of-done check (lint, format, types, tests, headless app render) and report real output. Use before every commit and whenever claiming a step is done.
---

Run these from the repo root, in order, and show the actual output of each:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
```

- If anything fails, fix it and re-run. Never mark a PLAN step done while a check is red.
- If the step touched the UI, also confirm the app serves:
  `uv run streamlit run app.py --server.headless true --server.port 8599 &`, then
  `curl -s localhost:8599/_stcore/health` should print `ok`. Kill the process afterwards.
- If the step touched a launcher, run `bash run.sh` (it should serve on :8501) and note that
  Windows/Mac are covered by CI.
- Report: the commands run, pass/fail per command, and any output that's still unexpected.
