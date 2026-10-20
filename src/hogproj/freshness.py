"""Is each data source up to date? Every source has a publishing rhythm; when its newest
observation is older than that rhythm allows, the app says so instead of quietly showing old
numbers (a USDA format change, a dead link or a lapsed key would otherwise look like data).
Pure.
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd

# Source -> the oldest its newest observation may be, in days, before it counts as behind.
# Daily reports allow for weekends and holidays; quarterly/monthly ones for their release lag.
MAX_AGE_DAYS = {
    "Lean Hog Index": 5,
    "Pork cutout": 5,
    "Weaned pigs": 10,
    "Iowa cash corn": 6,
    "Soybean meal": 13,
    "My Market News: weaned pigs": 10,
    "My Market News: Iowa corn": 6,
    "My Market News: meal, DDGS": 13,
    "Hogs and Pigs": 125,  # reference date (1st of Mar/Jun/Sep/Dec), released ~4 weeks later
    "USDA WASDE": 45,  # report month
    "Cold storage": 80,  # month of the stocks, released ~3-5 weeks after
    "Regional hog prices": 5,
    "Sow prices": 6,
    "Corn by state": 6,
    "Feeder pig flows": 10,
    "Hog by-product value": 10,
    "Retail pork features": 10,
    "Iowa State costs": 75,  # sale month; published about a month after
    "Diesel": 10,
    "Inspected slaughter": 5,
    "Prime rate": 10,
    "Sow slaughter": 24,  # week ending Saturday, published ~12 days later
    "Pork exports": 105,  # month of the trade, published ~6-9 weeks after it ends
    "Export sales (weekly)": 16,  # week ending Thursday, published the next Thursday
    "Live hog imports": 105,
    "Pork price spreads": 75,  # month, published ~3-6 weeks after it ends
}


@dataclass
class Freshness:
    name: str
    latest: pd.Timestamp
    age_days: int
    max_days: int | None
    source: str  # "live" or "saved"

    @property
    def behind(self) -> bool:
        return self.max_days is not None and self.age_days > self.max_days


def check(name: str, latest: object, today: date, source: str) -> Freshness:
    ts = pd.Timestamp(str(latest))
    age = (pd.Timestamp(today) - ts.normalize()).days
    return Freshness(name, ts, int(age), MAX_AGE_DAYS.get(name), source)


def is_current(name: str, latest: object, today: date | None = None) -> bool:
    """False when a source's newest observation is past its limit (signals then skip it rather
    than describe old data as recent)."""
    return not check(name, latest, today or date.today(), "").behind


def summary(items: list[Freshness]) -> tuple[bool, str]:
    """(all current?, one line naming what's behind)."""
    late = [f for f in items if f.behind]
    if not late:
        return True, "Every source is current."
    names = ", ".join(f"{f.name} ({f.latest:%b %d})" for f in late)
    return False, f"Behind its usual schedule: {names}."
