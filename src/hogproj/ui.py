"""HTML pieces for the dashboard: header, KPI cards, notices, stat lists, financial tables. Pure.

Each function returns an HTML string for `st.html` (which, unlike st.markdown, never reads
`$...$` as LaTeX). Every piece of user text goes through `esc`. Styles live in `ui.css`.
"""

from dataclasses import dataclass
from html import escape
from importlib.resources import files

import pandas as pd

MINUS = "−"  # a real minus sign lines up with digits; a hyphen doesn't


def css() -> str:
    return files("hogproj").joinpath("ui.css").read_text(encoding="utf-8")


def esc(text: object) -> str:
    return escape(str(text), quote=True)


def usd(v: float, dec: int = 2) -> str:
    v = round(float(v), dec) + 0.0  # + 0.0 turns -0.0 into 0.0
    return f"{MINUS}${abs(v):,.{dec}f}" if v < 0 else f"${v:,.{dec}f}"


def tone(v: float) -> str:
    return "gain" if v > 0 else "loss" if v < 0 else ""


# The logo mark is drawn in ui.css (.hp-mark::after): st.html strips inline SVG.


def header(title: str, eyebrow: str, chips: list[tuple[str, str]], status: tuple[str, str]) -> str:
    """Brand, title and context chips. chips = (label, value); status = (kind, text) where kind
    is live / import / offline."""
    kind, text = status
    chip_html = "".join(f'<span class="hp-chip">{esc(k)} <b>{esc(v)}</b></span>' for k, v in chips)
    return (
        '<div class="hp-header"><div class="hp-brand">'
        '<div class="hp-mark"></div><div>'
        f'<p class="hp-eyebrow">{esc(eyebrow)}</p><h1 class="hp-title">{esc(title)}</h1>'
        f'</div></div><div class="hp-context">{chip_html}'
        f'<span class="hp-chip" title="{esc(text)}"><span class="hp-dot {esc(kind)}"></span>'
        f"{esc(_status_label(kind))}</span></div></div>"
    )


def _status_label(kind: str) -> str:
    return {"live": "Live market data", "import": "Your imported data"}.get(
        kind, "Offline · default prices"
    )


@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    sub: str = ""
    tone: str = ""  # gain / loss / ""


def kpi_cards(cards: list[Kpi], extra_class: str = "") -> str:
    return (
        f'<div class="hp-kpis {extra_class}">'
        + "".join(_kpi(c, i) for i, c in enumerate(cards))
        + "</div>"
    )


def _kpi(c: Kpi, i: int) -> str:
    sub = f'<div class="hp-kpi-sub">{esc(c.sub)}</div>' if c.sub else ""
    return (
        f'<div class="hp-kpi {esc(c.tone)}" style="--i:{i}">'
        f'<div class="hp-kpi-label">{esc(c.label)}</div>'
        f'<div class="hp-kpi-value">{esc(c.value)}</div>{sub}</div>'
    )


def hero_card(net_per_head: float, avg_price_cwt: float, breakeven_cwt: float) -> str:
    """The verdict: net per head sold, and where the average sale price sits against breakeven
    on a gauge running from 80% to 120% of breakeven."""
    t = tone(net_per_head) or "gain"
    verdict = "Projected profit" if net_per_head >= 0 else "Projected loss"
    lo, hi = 0.8 * breakeven_cwt, 1.2 * breakeven_cwt
    span = (hi - lo) or 1.0

    def pos(v: float) -> float:
        return max(0.0, min(100.0, (v - lo) / span * 100))

    be, px = pos(breakeven_cwt), pos(avg_price_cwt)
    left, width = min(be, px), abs(px - be)
    gap = avg_price_cwt - breakeven_cwt
    return (
        f'<div class="hp-kpi hp-hero {t}" style="--i:0">'
        '<div class="hp-kpi-label">Net per head sold</div>'
        f'<div class="hp-kpi-value">{esc(usd(net_per_head))}'
        f'<span class="hp-verdict">{verdict}</span></div>'
        '<div class="hp-gauge"><div class="hp-gauge-track">'
        f'<div class="hp-gauge-fill" style="left:{left:.2f}%;width:{max(width, 0.8):.2f}%"></div>'
        f'<div class="hp-gauge-mark" style="left:calc({be:.2f}% - 1px)" title="Breakeven"></div>'
        "</div>"
        '<div class="hp-gauge-legend">'
        f"<span>Avg sale <b>{esc(usd(avg_price_cwt))}</b>/cwt</span>"
        f"<span>{esc(usd(abs(gap)))} {'above' if gap >= 0 else 'below'} breakeven "
        f"<b>{esc(usd(breakeven_cwt))}</b></span>"
        "</div></div></div>"
    )


def kpi_grid_with_hero(hero: str, cards: list[Kpi]) -> str:
    return (
        '<div class="hp-kpis">'
        + hero
        + "".join(_kpi(c, i + 1) for i, c in enumerate(cards))
        + "</div>"
    )


def notice(text_html: str, kind: str = "info") -> str:
    """A quiet callout. text_html must already be escaped (use esc on user text)."""
    icon = "!" if kind == "warn" else "i"
    return (
        f'<div class="hp-notice {esc(kind)}"><span class="hp-notice-icon">{icon}</span>'
        f"<div>{text_html}</div></div>"
    )


def card_title(title: str, aside: str = "", sub: str = "") -> str:
    aside_html = f"<span>{esc(aside)}</span>" if aside else ""
    sub_html = f'<p class="hp-sub">{esc(sub)}</p>' if sub else ""
    return f'<div class="hp-card-title"><h4>{esc(title)}</h4>{aside_html}</div>{sub_html}'


def stat_list(rows: list[tuple[str, str]]) -> str:
    items = "".join(
        f'<div class="hp-stat"><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in rows
    )
    return f'<dl class="hp-stats">{items}</dl>'


# Crush table layout: section headers before these rows, emphasis on the totals.
CRUSH_GROUPS = {
    "USDA report date": "Timing",
    "USDA weaned pig $/hd": "Prices",
    "Revenue $/pig": "Per pig",
    "Weaned pig $/pig": "Costs per pig",
}
CRUSH_TOTALS = {"Revenue $/pig", "Cost of production $/pig", "Breakeven $/cwt carcass"}
CRUSH_KEYS = {"Margin $/pig", "Margin after debt service $/pig"}


def crush_table(table: pd.DataFrame, money_rows: set[str]) -> str:
    """The weekly crush as a financial table: weeks as columns (newest first, like the
    workbook), sticky row labels, section headers, negatives in red, an Average column."""
    cols = list(table.columns)
    head = "".join(
        f"<th>{esc(pd.Timestamp(str(table.loc['USDA report date', c])).strftime('%b %d'))}</th>"
        for c in cols
    )
    body = []
    for label in table.index:
        label = str(label)
        if label in CRUSH_GROUPS:
            body.append(
                f'<tr class="group"><td colspan="{len(cols) + 2}">'
                f"{esc(CRUSH_GROUPS[label])}</td></tr>"
            )
        cls = "key" if label in CRUSH_KEYS else "total" if label in CRUSH_TOTALS else ""
        cells, nums = [], []
        for c in cols:
            v = table.loc[label, c]
            text, num = _crush_cell(label, v, money_rows)
            if num is not None:
                nums.append(num)
            cells.append(f'<td class="{_sign_class(num, label)}">{esc(text)}</td>')
        avg = sum(nums) / len(nums) if nums and len(nums) == len(cols) else None
        avg_cell = (
            f'<td class="avg {_sign_class(avg, label)}">{esc(usd(avg))}</td>'
            if avg is not None
            else '<td class="avg"></td>'
        )
        body.append(f'<tr class="{cls}"><td>{esc(label)}</td>{"".join(cells)}{avg_cell}</tr>')
    return (
        '<div class="hp-table-wrap"><table class="hp-table"><thead><tr><th>USDA report</th>'
        f'{head}<th class="avg">Average</th></tr></thead><tbody>{"".join(body)}</tbody>'
        "</table></div>"
    )


def _crush_cell(label: str, v: object, money_rows: set[str]) -> tuple[str, float | None]:
    if label in ("USDA report date", "Placement date", "Avg marketing date"):
        return pd.Timestamp(str(v)).strftime("%b %d, %Y"), None
    if label in money_rows and isinstance(v, (int, float)):
        return usd(float(v)), float(v)
    return str(v), None


def _sign_class(num: float | None, label: str) -> str:
    if num is None:
        return ""
    if label in CRUSH_KEYS:
        return "pos" if num > 0 else "neg" if num < 0 else ""
    return "neg" if num < 0 else ""
