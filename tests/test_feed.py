"""Iowa feed prices from the public USDA AMS PDFs (text fixtures saved Oct 2026)."""

from pathlib import Path

import pandas as pd
import pytest

from hogproj.data import feed

FIXTURES = Path(__file__).parent / "fixtures"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_iowa_cash_corn_and_cbot_settlements():
    df = feed.parse_corn(_text("ams_2850_2026-10-19.txt")).set_index("item")
    assert df.loc["corn_cash_iowa", "value"] == pytest.approx(4.24)  # state average, Oct 19
    assert df.loc["corn_futures_2026_12", "value"] == pytest.approx(4.67)  # 467.00¢ Dec 26
    assert df.loc["corn_futures_2027_03", "value"] == pytest.approx(4.805)
    assert (df["date"] == pd.Timestamp("2026-10-19")).all()


def test_parse_iowa_soybean_meal_and_ddgs():
    df = feed.parse_feedstuffs(_text("ams_3511_2026-10-16.txt")).set_index("item")
    assert df.loc["sbm_iowa", "value"] == pytest.approx(383.37)
    assert df.loc["ddgs_iowa", "value"] == pytest.approx(190.50)  # average, not year-ago 129.67
    assert (df["date"] == pd.Timestamp("2026-10-16")).all()  # week ending date


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ("Iowa|Ask|15.00Z to 30.00Z|No Comp|374.80-389.80|UP 26.20-DN 0.90|383.37|FOB-T/R", 383.37),
        ("Iowa|Ask|175.00-215.00|UNCH-DN 5.00|190.50|129.67|FOB-T", 190.50),
        ("Iowa|Ask|20.00Z|DN 30.00|379.80|DN 27.80|379.80|FOB-T", 379.80),
        ("Iowa|Ask|300.00-320.00|FOB-T", 310.00),  # no average column: midpoint
    ],
)
def test_iowa_row_average(row, expected):
    assert feed._iowa_row_average("Header|" + row + "|Kansas|Ask|1.00") == pytest.approx(expected)


def test_parsers_reject_other_reports():
    with pytest.raises(ValueError):
        feed.parse_corn("National Daily Hog Report")
    with pytest.raises(ValueError):
        feed.parse_feedstuffs("National Daily Hog Report")


def test_offline_load_and_latest(tmp_path, monkeypatch):
    monkeypatch.setattr(feed, "CACHE_DIR", tmp_path)
    df, source, note = feed.load(offline=True)
    assert source == "sample"
    assert "Offline" in note
    got = feed.latest(df, "corn_cash_iowa")
    assert got is not None and 2 < got[0] < 10
    assert feed.latest(df, "nonexistent") is None


def test_merge_keeps_newest_per_day_and_item():
    a = feed.parse_corn(_text("ams_2850_2026-10-19.txt"))
    b = a.copy()
    b.loc[b["item"] == "corn_cash_iowa", "value"] = 4.30  # a revised figure for the same day
    out = feed.merge(a, b)
    assert len(out) == len(a)
    assert feed.latest(out, "corn_cash_iowa")[0] == pytest.approx(4.30)  # type: ignore[index]
