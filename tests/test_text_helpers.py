"""Wording helpers: dates without padded days, a/an before numbers."""

from datetime import date

import pandas as pd

from hogproj.text import article, day


def test_day_drops_zero_padding():
    assert day(date(2027, 8, 3), "%B %d, %Y") == "August 3, 2027"
    assert day(pd.Timestamp("2026-10-03"), "%b %d") == "Oct 3"
    assert day("2026-10-20") == "Oct 20, 2026"


def test_article():
    assert article("7%") == "a 7%"
    assert article("8%") == "an 8%"
    assert article("11%") == "an 11%"
    assert article("18%") == "an 18%"
    assert article("80%") == "an 80%"
    assert article("under 1%") == "under a 1%"
    assert article("over 99%") == "over a 99%"
