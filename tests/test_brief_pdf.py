"""The one-page weekly brief PDF."""

import io
from datetime import date

import numpy as np
import pandas as pd
import pypdf

from hogproj import scorecard as sc
from hogproj import seasonal
from hogproj.brief_pdf import Brief, _t, build_pdf


def _series() -> pd.Series:
    idx = pd.date_range("2019-01-01", "2026-10-16", freq="D")
    return pd.Series(80 + 10 * np.sin(idx.dayofyear / 58.0), index=idx)


def _brief(**kw) -> Brief:
    s = _series()
    board = pd.DataFrame({"contract": ["Apr 2027", "Jun 2027"], "margin_usd": [-9.3, 4.1],
                          "rank": [31.0, 66.0]})  # fmt: skip
    base = dict(
        as_of=date(2026, 10, 20), headline="A pig placed today projects −$8.53 a head.",
        dek="Hogs are down $2.92 on the week.", scorecard=sc.build([sc.Metric("Lean hogs", s)]),
        index_weeks=seasonal.by_week(s), board=board,
        decisions=[("Placing pigs", "Worth up to $11.55."), ("Hedging", "Rule says wait.")],
        watch=[("caution", "Jun 2027: rule says hedge 50%.")],
        signals=[("good", "Supply ahead", "−1.5%", "Fewer hogs coming.")],
        sources="Data: USDA.",
    )  # fmt: skip
    return Brief(**{**base, **kw})


def _text(pdf: bytes) -> tuple[int, str]:
    r = pypdf.PdfReader(io.BytesIO(pdf))
    return len(r.pages), r.pages[0].extract_text()


def test_one_page_with_the_answer_and_no_branding():
    pages, text = _text(build_pdf(_brief()))
    assert pages == 1
    assert "A pig placed today projects -$8.53" in text
    assert "Lean hogs" in text and "Jun 2027: rule says hedge" in text
    assert "Pipestone" not in text


def test_long_content_still_fits_one_page():
    many = [("neutral", f"Item {i} " + "word " * 30) for i in range(12)]
    sig = [("bad", f"Signal {i}", "x", "word " * 20) for i in range(12)]
    pages, _ = _text(build_pdf(_brief(watch=many, signals=sig)))
    assert pages == 1


def test_latin1_text():
    assert _t("−$2 – a pig⁠") == "-$2 - a pig"
