# Design system

> Source of truth for how the app looks. The app is used by Pipestone staff and shown to
> producer clients, so it has to read as a finished product, not a template. Tokens live in
> `.streamlit/config.toml` (theme) and `src/hogproj/ui.py` (`TOKENS`, CSS, Plotly template);
> keep the three in sync. Changelog at the bottom.

## Principles

1. **Neutral first.** Grays carry ~90% of the screen. One accent (navy) for interaction and
   selection; green/red only for profit/loss and status.
2. **Hierarchy by size and colour, not weight.** Headings 600, never 700+. Labels are muted,
   values are ink.
3. **Say the takeaway.** Every page opens with an `insight` (status chip, one-sentence
   headline, a row of key facts). Chart titles state the finding ("Hog prices stay below
   breakeven all year"), with the units in the subtitle.
4. **No decoration.** No emoji, gradients, coloured callout boxes as layout, dual axes, pies,
   or numbers on every point. Material icons only where they carry meaning (navigation,
   actions).
5. **Numbers are typeset.** True minus sign (U+2212) for display values, compact currency in
   headlines ($1.24M), full values in tables, units in labels, signed deltas with the
   comparison stated ("vs breakeven").

## Tokens

| Token | Value | Use |
|---|---|---|
| Page | `#f6f6f4` | app background |
| Surface | `#ffffff` | cards, charts, sidebar `#fbfbfa` |
| Ink / Ink 2 / Muted | `#16181d` / `#4d535e` / `#8b909a` | text levels |
| Line / Grid | `#e3e3de` / `#efefeb` | hairline borders, gridlines |
| Accent | `#1f4e8c` | buttons, selected nav, links |
| Positive / Negative | `#178a6a` / `#c8453a` | profit / loss (CVD-checked ΔE 8.1) |
| Caution | `#b7791f` | "only with manure credit", stale data |
| Reference | `#5b616e` | breakeven and other reference lines (dashed) |
| Series 1-3 | `#2a78d6`, `#eb6834`, `#1baf7a` | categorical, in this order (validated all-pairs) |
| Baseline series | `#3a3f47` | "current plan" next to scenarios |

Palette checked with the dataviz skill's `validate_palette.js` on a white surface.

## Typography

- Inter (Google Fonts) with system fallback (`Segoe UI Variable`, SF Pro via `system-ui`), so
  the app still looks right offline.
- Base 14px. Page title 24px/600, card title 14.5px/600, KPI label 12.5px/500 muted, KPI
  value 28px/600 (−0.025em), captions 12.5px muted. Tabular figures in tables and fact rows.

## Components (`hogproj.ui`)

| Component | Purpose |
|---|---|
| `page_header(title, subtitle, eyebrow)` | eyebrow + title + one-line subtitle; data-freshness chip on the right; returns the right column for an action |
| `insight(tone, status, headline, facts)` | the page takeaway |
| `card(key)` | white panel (hairline border, 12px radius, faint shadow) |
| `section(title, caption)` | card title + muted subtitle |
| `chart(fig, height)` | Plotly in the house template, no toolbar, white plot area |
| `table(header, rows)` | comparison table, figures right-aligned |
| `usd`, `usd_short`, `signed`, `delta` | number formatting (`delta` keeps an ASCII "-" because Streamlit picks the arrow from it) |
| `st.metric` | KPI cards, styled globally; `height="stretch"` so a row lines up |

## Charts

- Hairline horizontal grid, no vertical grid, muted 11px ticks, money ticks via `tickformat`
  (`$,.0f` / `$~s`) so negatives get a true minus.
- 2px lines, 3px rounded bar ends, bar gaps 0.3-0.45. Direct labels on the extreme/endpoint
  only; legends only for ≥ 2 series.
- Breakeven: thin dashed reference line with a right-aligned label.
- Heatmap: diverging loss ↔ neutral ↔ profit, 2px cell gaps, current cell outlined.
- Fan chart: median line in series 1, 25-75% band at 20%, 10-90% at 10%; no legend.
- Standard heights: 280-330px in cards.

## Changelog
- 2026-10-19: Created. Replaced the first-pass look (emoji nav, green/red callouts, default
  Plotly) after feedback that it "looks AI-made". Based on a research brief (Stripe, Linear,
  Carbon, Datawrapper, NN/g, Streamlit 1.66 theming docs) and the dataviz palette rules.
