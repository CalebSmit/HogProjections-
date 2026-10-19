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
    help: str = ""  # shown on hover


def kpi_cards(cards: list[Kpi], extra_class: str = "") -> str:
    return (
        f'<div class="hp-kpis {extra_class}">'
        + "".join(_kpi(c, i) for i, c in enumerate(cards))
        + "</div>"
    )


def _kpi(c: Kpi, i: int) -> str:
    sub = f'<div class="hp-kpi-sub">{esc(c.sub)}</div>' if c.sub else ""
    tip = f' title="{esc(c.help)}"' if c.help else ""
    q = '<span class="hp-q">?</span>' if c.help else ""
    return (
        f'<div class="hp-kpi {esc(c.tone)}" style="--i:{i}"{tip}>'
        f'<div class="hp-kpi-label">{esc(c.label)}{q}</div>'
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


def lede(text_html: str) -> str:
    """The result in one plain-English paragraph. text_html must already be escaped."""
    return f'<p class="hp-lede">{text_html}</p>'


@dataclass(frozen=True)
class Line:
    label: str
    total_usd: float


def pl_statement(
    revenue_usd: float,
    costs: list[Line],
    head_sold: float,
    carcass_cwt: float,
    debt_usd: float = 0.0,
) -> str:
    """Income statement for the group: revenue, each cost, total, net, then debt service.
    Columns: total, $/head sold, $/cwt carcass, % of revenue. Zero lines show a dash."""

    def cells(v: float) -> str:
        per_hd = v / head_sold if head_sold else 0.0
        per_cwt = v / carcass_cwt if carcass_cwt else 0.0
        pct = v / revenue_usd * 100 if revenue_usd else 0.0
        neg = " neg" if round(v, 2) < 0 else ""
        if abs(v) < 0.005:
            return '<td class="dash">–</td>' * 4
        return (
            f'<td class="{neg}">{esc(usd(v, 0))}</td><td class="{neg}">{esc(usd(per_hd))}</td>'
            f'<td class="{neg}">{esc(usd(per_cwt))}</td><td>{pct:,.1f}%</td>'
        )

    total = sum(c.total_usd for c in costs)
    net = revenue_usd - total
    rows = [f'<tr class="total"><td>Hog sales</td>{cells(revenue_usd)}</tr>']
    rows.append('<tr class="group"><td colspan="5">Costs</td></tr>')
    rows += [f'<tr><td class="indent">{esc(c.label)}</td>{cells(c.total_usd)}</tr>' for c in costs]
    rows.append(f'<tr class="total"><td>Total cost</td>{cells(total)}</tr>')
    tone_cls = "pos" if net > 0 else "neg" if net < 0 else ""
    rows.append(f'<tr class="key net {tone_cls}"><td>Net margin</td>{cells(net)}</tr>')
    if debt_usd:
        rows.append(f'<tr><td class="indent">Debt service</td>{cells(debt_usd)}</tr>')
        after = net - debt_usd
        tone_cls = "pos" if after > 0 else "neg" if after < 0 else ""
        rows.append(
            f'<tr class="key net {tone_cls}"><td>Net after debt service</td>{cells(after)}</tr>'
        )
    return (
        '<div class="hp-table-wrap"><table class="hp-table hp-pl"><thead><tr><th></th>'
        "<th>Total</th><th>$/head sold</th><th>$/cwt carcass</th><th>% of revenue</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def rank_table(rows: list[dict], selected: str) -> str:
    """Locations ranked by net $/head sold. rows: location, net, cost, corn, sbm."""
    rows = sorted(rows, key=lambda r: r["net"], reverse=True)
    mine = next((r["net"] for r in rows if r["location"] == selected), None)
    body = []
    for i, r in enumerate(rows, start=1):
        is_sel = r["location"] == selected
        diff = "" if mine is None or is_sel else usd(r["net"] - mine)
        diff = diff if not diff or diff.startswith(MINUS) else "+" + diff
        neg = "neg" if r["net"] < 0 else "pos" if r["net"] > 0 else ""
        body.append(
            f'<tr class="{"sel" if is_sel else ""}"><td><span class="hp-rank">{i}</span>'
            f"{esc(r['location'])}{' <em>selected</em>' if is_sel else ''}</td>"
            f'<td class="{neg}">{esc(usd(r["net"]))}</td><td>{esc(diff) or "–"}</td>'
            f"<td>{esc(usd(r['cost']))}</td><td>{esc(usd(r['corn']))}</td>"
            f"<td>{esc(usd(r['sbm']))}</td></tr>"
        )
    return (
        '<div class="hp-table-wrap"><table class="hp-table hp-rank-table"><thead><tr>'
        "<th>Location</th><th>Net $/head sold</th><th>vs selected</th><th>Cost $/head sold</th>"
        "<th>Corn $/bu</th><th>SBM $/ton</th>"
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


GUIDE_STEPS = [
    ("Set up the group", "In the left panel: location, head placed, placement date and the "
     "weaned pig price (USDA cash, formula or your own)."),
    ("Check the costs", "Inputs tab: feed prices and ration, barn, labor, health, interest and "
     "marketing. Save them as a profile so next time is one click."),
    ("Read the result", "Summary tab: net per head, breakeven, the P&L and what happens if "
     "corn or hogs move. Weekly crush shows the same math for every weekly placement."),
    ("Share it", "Excel tab: download a live workbook (every number is a formula) or print this "
     "page to PDF from the browser."),
]  # fmt: skip
GUIDE_TERMS = [
    ("Basis", "Local cash price minus futures. Hog basis = CME Lean Hog Index minus the futures "
     "contract; corn basis = local bid minus CBOT corn."),
    ("Breakeven", "The carcass price ($/cwt) that covers every cost, after checkoff."),
    ("$/cwt carcass vs live", "Hogs are priced per 100 lb of carcass. Live = carcass × yield "
     "(about 0.75), so a live price looks lower."),
    ("Contract month", "A sale in days 1-14 of a contract month (Feb, Apr, May, Jun, Jul, Aug, "
     "Oct, Dec) uses that contract; later in the month, the next one (ISU B2-41)."),
    ("Crush", "The margin of one weekly placement at that week's pig, feed and hog prices."),
    ("Debt service", "Principal + term interest per pig, shown below the operating margin."),
    ("Profile", "Your saved costs, ration and toggles. Kept on this computer, never uploaded."),
]  # fmt: skip
GUIDE_SOURCES = [
    ("Weaned pigs", "USDA AMS National Direct Feeder Pig Report (2810), early weaned, weekly."),
    ("Hog basis", "CME Lean Hog Index rebuilt from USDA LM_HG201, minus lean hog futures."),
    ("Futures", "CBOT corn and soybean meal, CME lean hogs (delayed quotes)."),
    ("Your imports", "Barchart downloads you upload on the Data tab (stay on this computer)."),
    ("Default costs", "Iowa State and Minnesota extension budgets; replace with your own."),
]


def guide() -> str:
    steps = "".join(
        f'<li><span class="hp-step">{i}</span><div><b>{esc(t)}</b><p>{esc(d)}</p></div></li>'
        for i, (t, d) in enumerate(GUIDE_STEPS, start=1)
    )
    terms = "".join(f"<dt>{esc(t)}</dt><dd>{esc(d)}</dd>" for t, d in GUIDE_TERMS)
    sources = "".join(f"<dt>{esc(t)}</dt><dd>{esc(d)}</dd>" for t, d in GUIDE_SOURCES)
    return (
        '<div class="hp-guide"><section><h4>How to use it</h4>'
        f'<ol class="hp-steps">{steps}</ol></section>'
        f'<section><h4>Terms</h4><dl class="hp-terms">{terms}</dl></section>'
        f'<section><h4>Where the numbers come from</h4><dl class="hp-terms">{sources}</dl>'
        "</section></div>"
    )


def footer(version: str, status_text: str) -> str:
    return (
        '<footer class="hp-footer"><span>W2F Projection v'
        f"{esc(version)}</span><span>{esc(status_text)}</span>"
        "<span>A projection, not a guarantee: prices, performance and costs will differ.</span>"
        "</footer>"
    )
