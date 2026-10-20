"""Iowa State Estimated Livestock Returns, farrow to finish (PDF text fixture, Oct 2026)."""

from pathlib import Path

import pandas as pd
import pytest

from hogproj.data.isu import parse

TEXT = (Path(__file__).parent / "fixtures" / "isu_f2f_2026-10.txt").read_text(encoding="utf-8")


def test_parse_latest_month_matches_the_published_table():
    df = parse(TEXT).set_index("sale_month")
    sep = df.loc[pd.Timestamp("2026-09-01")]
    assert sep["corn"] == pytest.approx(40.78)
    assert sep["total_cost"] == pytest.approx(175.70)
    assert sep["breakeven_carcass"] == pytest.approx(86.77)
    assert sep["profit"] == pytest.approx(-3.88)  # negative values parse
    assert len(df) == 9  # months without figures yet are left out


def test_defaults_structure_matches_the_cost_model():
    sep = parse(TEXT).iloc[-1]
    assert sep["ddgs"] + sep["complete_other"] + sep["processing"] == pytest.approx(34.27)
    assert sep["variable"] + sep["interest"] + sep["fixed"] == pytest.approx(76.76)


def test_rejects_other_text():
    with pytest.raises(ValueError):
        parse("Estimated Returns to Cattle Feeding")
