# Design system

> Source of truth for how the app looks. The app is used by Pipestone staff and shown to
> producer clients, so it has to read as a finished product, not a template. Tokens live in
> `.streamlit/config.toml` (theme) and `src/hogproj/ui.py` (`TOKENS`, CSS, Plotly template);
> keep the three in sync. Changelog at the bottom.

## Direction: "Field Report"

An advisor's analysis, not generic software. Chosen after reviewing ~35 references
(2026-10-19): USDA ERS and Our World in Data charts (finding-as-headline, direct labels,
source lines, marked forecasts), Stock Analysis / CME / Koyfin (quote-style hero, hairline
key-stats tables, end-of-line value tags), Plausible / shadcn (one strip of figures merged with
the main chart, one-line takeaways).

## Principles

1. **The headline is the finding.** Every page opens with a serif sentence that answers its
   question ("You need $91.17/cwt to cover every cost."), a one-line dek, and a kicker.
2. **One hero per page.** A single white panel holds the quote (big number + change + context),
   a stat strip (figures split by hairlines, not separate cards) and the signature chart.
   Everything below sits directly on the paper background, separated by rules.
3. **Inputs live in the assumption bar,** a row of chips under the headline whose labels show
   the current values ("Prices · Corn $5.25 · SBM $300 · Hogs $73.40"). The sidebar is
   navigation only.
4. **Charts explain themselves.** Serif title stating the finding, units in the subtitle,
   series labelled at their ends (value tags), dotted breakeven with an inline label, projected
   periods shaded and labelled, a source/note line underneath. No legends unless unavoidable.
5. **Restraint.** Warm neutrals carry the page; field green for interaction and the headline
   series; green/red only for profit/loss. No emoji, gradients, dual axes or pies.
6. **Typeset numbers.** True minus sign, compact currency in headlines, units in labels, signed
   changes with the comparison stated.

## Tokens

| Token | Value | Use |
|---|---|---|
| Paper | `#f7f5f0` | page background |
| Surface | `#ffffff` | hero panel, chips; sidebar `#f2efe8` |
| Ink / Ink 2 / Muted | `#1d2520` / `#4b554e` / `#7c847e` | text levels |
| Line / Grid | `#e5e0d5` / `#ece8de` | rules, borders, gridlines |
| Field green | `#1f5c45` (tint `#e7efe9`) | accent, headline series, projection bands |
| History | `#3a423d` | observed series next to a projection |
| Positive / Negative | `#178a6a` / `#c8453a` | profit / loss (CVD-checked ΔE 8.1) |
| Caution | `#b07a1f` | manure-credit-only profit, stale data |
| Reference | `#857f73` | breakeven, dotted |
| Series 1-3 | `#2a78d6`, `#eb6834`, `#1baf7a` | scenarios, in this order |

Earthy greens/browns fail the dataviz validator's chroma floor for *categorical* use, so they
are kept to UI chrome and the single, directly-labelled headline series.

## Typography

- Headlines and chart titles: **Source Serif 4** (600). UI, labels and numbers: **Inter**, with
  system fallbacks offline.
- Page headline 33px; chart title 19px serif; dek 15.5px; kickers and stat labels 10.5-11px
  uppercase, +0.08em; quote value 46px/600; stat values 21px tabular.

## Components (`hogproj.ui`)

| Component | Purpose |
|---|---|
| `masthead(title, dek, kicker)` | finding headline + dek + data-freshness chip; returns the action column |
| `assumption_bar(key)` + `st.popover(md(label))` | input chips; `md()` escapes `$` |
| `hero()` | the page's one white panel |
| `quote(label, value, unit, change, tone, sub)` | market-quote hero number |
| `stat_strip(items)` | figures in one row split by hairlines |
| `chart_title`, `source_note`, `rule` | editorial chart furniture |
| `chart(fig, height, on=PAGE/SURFACE)` | Plotly in the house template |
| `end_tag`, `ref_line`, `projection_band` | value tags, dotted reference lines, forecast shading |
| `kv_table`, `table` | key-stats and comparison tables (hairline rows) |

## Changelog
- 2026-10-19: "Field Report" direction after the reference review: serif finding headlines,
  hero panel with quote + stat strip, assumption chips instead of sidebar inputs, warm paper
  palette with field green, actual-vs-projection signature chart.
- 2026-10-19: Created. Replaced the first-pass look (emoji nav, green/red callouts, default
  Plotly) after feedback that it "looks AI-made". Based on a research brief (Stripe, Linear,
  Carbon, Datawrapper, NN/g, Streamlit 1.66 theming docs) and the dataviz palette rules.
