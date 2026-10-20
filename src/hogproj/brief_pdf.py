"""The weekly brief as a one-page PDF (US letter) for producers to forward: the answer, the
scorecard, two charts (lean hogs against their season; margin by contract for pigs not placed
yet), the decisions in words, the watch list and where the numbers come from. Unbranded.
Pure: numbers in, PDF bytes out (fpdf2, no system dependencies).
"""

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
from fpdf import FPDF

from hogproj import seasonal
from hogproj.scorecard import Row

INK = (29, 37, 32)
INK_2 = (75, 85, 78)
MUTED = (124, 132, 126)
LINE = (229, 224, 213)
ACCENT = (31, 92, 69)
POS = (23, 138, 106)
NEG = (200, 69, 58)
CAUTION = (176, 122, 31)
BAND = (233, 229, 220)
TONES = {"good": POS, "bad": NEG, "caution": CAUTION, "neutral": MUTED}


@dataclass
class Brief:
    as_of: date
    headline: str
    dek: str
    scorecard: list[Row]
    index_weeks: pd.DataFrame  # seasonal.by_week of the Lean Hog Index
    board: pd.DataFrame  # board.summarize
    decisions: list[tuple[str, str]]  # (title, sentence)
    watch: list[tuple[str, str]] = field(default_factory=list)  # (tone, sentence)
    signals: list[tuple[str, str, str, str]] = field(
        default_factory=list
    )  # tone, name, value, read
    sources: str = ""


def _t(text: str) -> str:
    """The PDF core fonts are Latin-1: swap the typographic characters the app uses."""
    for a, b in (("−", "-"), ("–", "-"), ("—", "-"), ("⁠", ""), ("’", "'"), ("“", '"'),
                 ("”", '"'), ("…", "...")):  # fmt: skip
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


class _Doc(FPDF):
    def section(self, title: str) -> None:
        self.ln(2.5)
        self.set_font("Helvetica", "B", 7.5)
        self.set_text_color(*MUTED)
        self.cell(0, 4, _t(title.upper()), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*LINE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.2)


def _scorecard(pdf: _Doc, rows: list[Row]) -> None:
    widths = [40, 27, 25, 14, 46, 36]
    heads = ["Measure", "Latest", "Week", "Year", "Usual for this week", "Status"]
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(*MUTED)
    for w, h, i in zip(widths, heads, range(6), strict=True):
        pdf.cell(w, 4.5, h.upper(), align="R" if i in (1, 2, 3) else "L")
    pdf.ln(4.5)
    for r in rows:
        y = pdf.get_y()
        wk = (
            "-"
            if r.week_change is None
            else ("+" if r.week_change >= 0 else "") + r.fmt(r.week_change)
        )
        yr = "-" if r.year_pct is None else f"{r.year_pct:+.0%}"
        usual = (
            "-"
            if r.verdict is None
            else (f"{r.fmt(r.verdict.lo, False)}-{r.fmt(r.verdict.hi, False)} ({r.verdict.span})")
        )
        cells = [r.name, r.fmt(r.latest), wk, yr, usual]
        pdf.set_text_color(*INK)
        for i, (w, text) in enumerate(zip(widths[:5], cells, strict=True)):
            pdf.set_font("Helvetica", "B" if i in (0, 1) else "", 8)
            pdf.cell(w, 5, _t(text), align="R" if i in (1, 2, 3) else "L")
        pdf.set_fill_color(*TONES.get(r.tone, MUTED))
        pdf.ellipse(pdf.get_x() + 0.5, y + 1.6, 1.8, 1.8, style="F")
        pdf.set_x(pdf.get_x() + 3.5)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(widths[5] - 3.5, 5, _t(r.status), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*LINE)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + sum(widths), pdf.get_y())


def _usd(v: float) -> str:
    return f"{'-' if v < 0 else ''}${abs(v):,.0f}"


def _frame(pdf: _Doc, x: float, y: float, w: float, h: float, lo: float, hi: float
           ) -> None:  # fmt: skip
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*MUTED)
    pdf.set_draw_color(*LINE)
    for v in np.linspace(lo, hi, 4):
        yy = y + h - (v - lo) / (hi - lo) * h
        pdf.line(x, yy, x + w, yy)
        pdf.set_xy(x - 13, yy - 1.5)
        pdf.cell(12, 3, _usd(float(v)), align="R")


def _season_chart(pdf: _Doc, weeks: pd.DataFrame, x: float, y: float, w: float, h: float) -> None:
    """Lean hogs: this year (green), last year (grey), range of the five years before (band)."""
    if weeks.empty:
        return
    this = int(weeks["year"].max())
    b = seasonal.band(weeks, this)
    vals = pd.concat([b["lo"], b["hi"], weeks[weeks["year"] >= this - 1]["value"]])
    lo, hi = float(vals.min()) * 0.97, float(vals.max()) * 1.03
    _frame(pdf, x, y, w, h, lo, hi)

    def pt(wk: float, v: float) -> tuple[float, float]:
        return x + (wk - 1) / 51 * w, y + h - (v - lo) / (hi - lo) * h

    poly = [pt(k, v) for k, v in b["hi"].items()] + [pt(k, v) for k, v in b["lo"].items()][::-1]
    pdf.set_fill_color(*BAND)
    pdf.polygon(poly, style="F")
    for yr, color, width in ((this - 1, MUTED, 0.35), (this, ACCENT, 0.7)):
        part = weeks[weeks["year"] == yr]
        pdf.set_draw_color(*color)
        pdf.set_line_width(width)
        pdf.polyline([pt(k, v) for k, v in zip(part["wk"], part["value"], strict=True)])
    pdf.set_line_width(0.2)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*MUTED)
    for m, wk in (("Jan", 1), ("Apr", 14), ("Jul", 27), ("Oct", 40)):
        pdf.set_xy(*pt(wk, lo))
        pdf.cell(8, 3.5, m)


def _board_chart(pdf: _Doc, board: pd.DataFrame, x: float, y: float, w: float, h: float) -> None:
    """Margin per pig by contract, bars coloured by rank (green high, red low)."""
    if board.empty:
        return
    m = board["margin_usd"].to_numpy(dtype=float)
    lo, hi = min(float(m.min()), 0.0) * 1.15 - 1, max(float(m.max()), 0.0) * 1.15 + 1
    _frame(pdf, x, y, w, h, lo, hi)
    zero = y + h - (0 - lo) / (hi - lo) * h
    slot = w / len(board)
    pdf.set_font("Helvetica", "", 6.5)
    for i, r in enumerate(board.to_dict("records")):
        top = y + h - (float(r["margin_usd"]) - lo) / (hi - lo) * h
        rank = float(r["rank"]) if pd.notna(r["rank"]) else 50.0
        pdf.set_fill_color(*(POS if rank >= 60 else NEG if rank <= 40 else MUTED))
        bx = x + i * slot + slot * 0.2
        pdf.rect(bx, min(top, zero), slot * 0.6, max(abs(zero - top), 0.3), style="F")
        pdf.set_text_color(*INK_2)
        pdf.set_xy(x + i * slot, y + h + 0.5)
        pdf.cell(slot, 3, _t(str(r["contract"]).replace(" 20", " '")), align="C")
    pdf.set_draw_color(*INK_2)
    pdf.line(x, zero, x + w, zero)


def build_pdf(b: Brief) -> bytes:
    pdf = _Doc(format="letter", unit="mm")
    pdf.set_margins(14, 12, 14)
    pdf.set_auto_page_break(False)
    pdf.add_page()
    pdf.set_title(f"Weekly hog market brief {b.as_of:%Y-%m-%d}")
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 4, _t(f"WEEKLY HOG MARKET BRIEF  ·  {b.as_of:%B} {b.as_of.day}, {b.as_of.year}"),
             new_x="LMARGIN", new_y="NEXT")  # fmt: skip
    pdf.ln(1)
    pdf.set_font("Times", "B", 17)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 7, _t(b.headline), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(0.8)
    pdf.set_font("Helvetica", "", 8.8)
    pdf.set_text_color(*INK_2)
    pdf.multi_cell(0, 4.3, _t(b.dek), new_x="LMARGIN", new_y="NEXT")

    pdf.section("Scorecard · against the same week in the five years before")
    _scorecard(pdf, b.scorecard)

    pdf.section("Charts")
    y0 = pdf.get_y() + 1
    half = (pdf.w - pdf.l_margin - pdf.r_margin - 18) / 2
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(*INK)
    pdf.set_xy(pdf.l_margin, y0)
    pdf.cell(half, 4, "Lean hogs vs their usual season, $/cwt")
    pdf.set_xy(pdf.l_margin + half + 18, y0)
    pdf.cell(half, 4, "Margin per pig, pigs not placed yet")
    _season_chart(pdf, b.index_weeks, pdf.l_margin + 12, y0 + 7, half - 12, 36)
    _board_chart(pdf, b.board, pdf.l_margin + half + 30, y0 + 7, half - 12, 36)
    pdf.set_xy(pdf.l_margin, y0 + 48)
    pdf.set_font("Helvetica", "", 6.8)
    pdf.set_text_color(*MUTED)
    pdf.cell(half, 3, "Green: this year · grey: last year · shaded: five years before")
    pdf.set_x(pdf.l_margin + half + 18)
    pdf.cell(half, 3, "At today's contract prices · green: high rank vs history, red: low",
             new_x="LMARGIN", new_y="NEXT")  # fmt: skip

    pdf.section("Decisions")
    col = (pdf.w - pdf.l_margin - pdf.r_margin - 8) / 2
    for i in range(0, len(b.decisions), 2):
        y = pdf.get_y()
        bottom = y
        for j, (title, text) in enumerate(b.decisions[i : i + 2]):
            pdf.set_xy(pdf.l_margin + j * (col + 8), y)
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(*INK)
            pdf.cell(col, 4.2, _t(title), new_x="LEFT", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*INK_2)
            pdf.multi_cell(col, 3.8, _t(text), new_x="LEFT", new_y="NEXT")
            bottom = max(bottom, pdf.get_y())
        pdf.set_y(bottom + 1.5)

    if b.watch:
        pdf.section("Watch list")
        for tone, text in b.watch[:5]:
            if pdf.get_y() > pdf.h - 30:
                break
            y = pdf.get_y()
            pdf.set_fill_color(*TONES.get(tone, MUTED))
            pdf.ellipse(pdf.l_margin + 0.5, y + 1.3, 1.8, 1.8, style="F")
            pdf.set_x(pdf.l_margin + 4)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*INK)
            pdf.multi_cell(0, 4, _t(text), new_x="LMARGIN", new_y="NEXT")

    if b.signals:
        pdf.section("What the market is saying")
        for tone, name, value, read in b.signals[:8]:
            if pdf.get_y() > pdf.h - 24:
                break
            y = pdf.get_y()
            pdf.set_fill_color(*TONES.get(tone, MUTED))
            pdf.ellipse(pdf.l_margin + 0.5, y + 1.3, 1.8, 1.8, style="F")
            pdf.set_x(pdf.l_margin + 4)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*INK)
            pdf.cell(30, 4, _t(name))
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(36, 4, _t(value))
            pdf.set_text_color(*INK_2)
            pdf.multi_cell(0, 4, _t(read), new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(pdf.h - 16)
    pdf.set_draw_color(*LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(1.5)
    pdf.set_font("Helvetica", "", 6.8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 3.2, _t(b.sources + " Projections from public data, not financial advice."),
                   new_x="LMARGIN", new_y="NEXT")  # fmt: skip
    return bytes(pdf.output())
