"""Every source is checked against its publishing rhythm."""

from datetime import date

from hogproj.freshness import MAX_AGE_DAYS, check, summary


def test_daily_source_allows_a_long_weekend():
    assert not check("Lean Hog Index", "2026-10-16", date(2026, 10, 20), "live").behind  # Fri->Tue
    assert check("Lean Hog Index", "2026-10-09", date(2026, 10, 20), "saved").behind


def test_quarterly_and_unknown_sources():
    assert not check("Hogs and Pigs", "2026-09-01", date(2026, 12, 20), "live").behind
    assert check("Hogs and Pigs", "2026-06-01", date(2026, 12, 20), "live").behind
    assert not check("Something new", "2020-01-01", date(2026, 10, 20), "live").behind


def test_summary_names_what_is_behind():
    items = [check("Pork cutout", "2026-10-19", date(2026, 10, 20), "live"),
             check("Weaned pigs", "2026-09-18", date(2026, 10, 20), "saved")]  # fmt: skip
    ok, why = summary(items)
    assert not ok and "Weaned pigs (Sep 18)" in why and "cutout" not in why
    assert summary(items[:1]) == (True, "Every source is current.")


def test_every_source_shown_in_the_app_has_a_rhythm():
    shown = {"Lean Hog Index", "Pork cutout", "Weaned pigs", "Iowa cash corn", "Soybean meal",
             "Hogs and Pigs", "USDA WASDE", "Cold storage"}  # fmt: skip
    assert shown <= set(MAX_AGE_DAYS)
