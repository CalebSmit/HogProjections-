# ADR 0002: A small in-app design system on top of Streamlit theming

- **Status:** accepted (2026-10-19)
- **Context:** The app is used by Pipestone staff and shown to producer clients. Feedback on the
  first version: "it looks like it was made by an AI, not premium." Default Streamlit + Plotly,
  emoji navigation and coloured callout boxes were the main tells.
- **Decision:**
  - Theme tokens in `.streamlit/config.toml` (Streamlit 1.66 supports fonts, heading scale,
    metric sizes, border colours, a sidebar theme and chart palettes).
  - One module, `hogproj.ui`, holds the rest: a Plotly template, a small CSS layer that only
    targets `data-testid` attributes and `st-key-card_*` classes (stable hooks, never hashed
    `st-emotion-cache-*` classes), and components (`page_header`, `insight`, `card`, `section`,
    `chart`, `table`, number formatting). Pages compose these instead of styling ad hoc.
  - Rules documented in `docs/DESIGN.md`.
- **Alternatives:**
  - A custom React front end: far more polish headroom, but breaks the double-click launcher
    and doubles the code.
  - A third-party Streamlit theme/component pack: less control, extra dependency, and still
    template-looking.
  - `theme="streamlit"` for charts: less control over grid, ticks and hover.
- **Consequences:**
  - CSS may need touch-ups on Streamlit upgrades; keep selectors to `data-testid` / `st-key-*`
    and re-screenshot every page after upgrading.
  - Inter loads from Google Fonts when online; offline falls back to the OS UI font.
