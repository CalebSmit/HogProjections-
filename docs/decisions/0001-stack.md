# ADR 0001: Python + uv + Streamlit

- **Status:** accepted (2026-10-17)
- **Context:** The recipient is non-technical and must clone the repo and run it on Windows or
  Mac with no setup. The workload is small tabular modeling plus charts and Excel export.
- **Decision:**
  - uv manages Python and the dependencies, with versions locked in `uv.lock`.
  - Streamlit for the UI; pandas/numpy for the model; Plotly for charts; xlsxwriter for export.
  - Double-click launchers that install uv if it's missing.
- **Alternatives:**
  - Dash/Panel: more code.
  - Reflex: needs a JS toolchain.
  - Excel-only: no live data or Monte Carlo.
  - Docker: too heavy for the recipient.
  - Poetry or pip: need Python installed first.
- **Consequences:**
  - The first run downloads about 200 MB.
  - Streamlit reruns the script on every interaction, so cache expensive calls with `st.cache_data`.
  - Free hosting is possible later via Streamlit Community Cloud.
- **Research:** `docs/research/stack-and-workflow.md`
