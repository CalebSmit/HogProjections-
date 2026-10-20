"""Iowa feed prices from public USDA AMS PDFs (no key): cash corn, soybean meal and DDGS.

- AMS_2850 Iowa Daily Cash Grain Bids: state average cash corn ($/bu) and the CBOT corn
  settlements printed with it (¢/bu by contract month).
- AMS_3511 National Grain and Oilseed Processor Feedstuff (weekly): Iowa soybean meal 46.5–48%
  and Iowa DDGS ($/ton, FOB).

USDA posts only the latest issue, so each successful fetch is appended to a local cache to build
history. When offline or unreachable the app falls back to the cache, then to the bundled
sample, then to the model defaults.
"""

import io
import re
from datetime import datetime
from typing import Literal

import httpx
import pandas as pd

from hogproj.config import CACHE_DIR, SAMPLE_DIR

BASE = "https://www.ams.usda.gov/mnreports"
FEED_FILE = "ams_iowa_feed_prices.csv"
COLUMNS = ["date", "item", "value", "unit", "report"]
Source = Literal["live", "cache", "sample"]

_PRICE = re.compile(r"^\d{2,4}\.\d{2}(?:-\d{2,4}\.\d{2})?$")
_NUMBER = re.compile(r"^\d{1,4}\.\d{1,2}$")
_CHANGE = ("UP", "DN", "UNCH", "No ")
_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MONTHS = {m: i for i, m in enumerate(_MONTH_NAMES, 1)}


def _tokens(text: str) -> list[str]:
    return [t.strip() for t in text.splitlines() if t.strip()]


def parse_corn(text: str) -> pd.DataFrame:
    """AMS_2850 text -> Iowa state average cash corn + CBOT corn settlements."""
    flat = "|".join(_tokens(text))
    when = re.search(r"Grain Report for\s*\|(\d+/\d+/\d{4})\|", flat)
    avg = re.search(r"State Average Price: Corn --\s*\|\$(\d+\.\d+)\|", flat)
    if not when or not avg:
        raise ValueError("Not an Iowa Daily Cash Grain Bids report")
    day = datetime.strptime(when[1], "%m/%d/%Y")
    rows = [{"date": day, "item": "corn_cash_iowa", "value": float(avg[1]), "unit": "$/bu",
             "report": "AMS_2850"}]  # fmt: skip
    futures = re.search(r"CBOT\|Corn\|(.*?)\|CBOT", flat)
    if futures:
        for cents, mon, yr in re.findall(r"(\d+\.\d+) \((\w{3}) (\d{2})\)", futures[1]):
            item = f"corn_futures_{2000 + int(yr)}_{_MONTHS[mon]:02d}"
            rows.append({"date": day, "item": item, "value": float(cents) / 100, "unit": "$/bu",
                         "report": "AMS_2850"})  # fmt: skip
    return pd.DataFrame(rows, columns=COLUMNS)


def _iowa_row_average(section: str) -> float | None:
    """Average price on the Iowa row of a feedstuff table section (see module docstring)."""
    toks = section.split("|")
    try:
        i = toks.index("Iowa")
    except ValueError:
        return None
    row = []
    for t in toks[i + 1 :]:
        if t.startswith(("FOB", "DLVD")):
            break
        row.append(t)
    prices = [k for k, t in enumerate(row) if _PRICE.match(t)]
    if not prices:
        return None
    first = prices[0]
    for t in row[first + 1 :]:
        if t.startswith(_CHANGE):
            continue
        if _NUMBER.match(t):
            return float(t)
        break
    lo, _, hi = row[first].partition("-")
    return (float(lo) + float(hi or lo)) / 2


def parse_feedstuffs(text: str) -> pd.DataFrame:
    """AMS_3511 text -> Iowa soybean meal and DDGS ($/ton) for the report week."""
    flat = "|".join(_tokens(text))
    when = re.search(r"Report for\s*\|(\d+/\d+/\d{4})\|\s*-\s*\|(\d+/\d+/\d{4})\|", flat)
    if not when:
        raise ValueError("Not a National Grain and Oilseed Processor Feedstuff report")
    day = datetime.strptime(when[2], "%m/%d/%Y")
    rows = []
    for item, head in (("sbm_iowa", "Soybean Meal 46.5-48%"),
                       ("ddgs_iowa", "Corn Distillers Dried Grain 10%")):  # fmt: skip
        part = flat.split(head, 1)
        if len(part) < 2:
            continue
        section = part[1].split("|Region|", 2)[1] if part[1].count("|Region|") else part[1]
        v = _iowa_row_average(section)
        if v is not None:
            rows.append({"date": day, "item": item, "value": v, "unit": "$/ton",
                         "report": "AMS_3511"})  # fmt: skip
    if not rows:
        raise ValueError("No Iowa soybean meal or DDGS rows found")
    return pd.DataFrame(rows, columns=COLUMNS)


def _pdf_text(content: bytes) -> str:
    from pypdf import PdfReader

    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(content)).pages)


def fetch(client: httpx.Client | None = None) -> pd.DataFrame:
    with client or httpx.Client(timeout=60, follow_redirects=True) as c:
        parts = []
        for report, parser in (("ams_2850.pdf", parse_corn), ("ams_3511.pdf", parse_feedstuffs)):
            resp = c.get(f"{BASE}/{report}")
            resp.raise_for_status()
            parts.append(parser(_pdf_text(resp.content)))
    return pd.concat(parts, ignore_index=True)


def merge(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    both = pd.concat([f for f in (old, new) if not f.empty], ignore_index=True)
    both["date"] = pd.to_datetime(both["date"])
    both = both.drop_duplicates(["date", "item"], keep="last")
    return both.sort_values(["item", "date"]).reset_index(drop=True)


def _read(path) -> pd.DataFrame:  # noqa: ANN001 - Path
    return pd.read_csv(path, parse_dates=["date"])


def load(offline: bool) -> tuple[pd.DataFrame, Source, str]:
    """All saved observations (long format) and where the newest came from. Never raises."""
    cache = CACHE_DIR / FEED_FILE
    saved = merge(_read(SAMPLE_DIR / FEED_FILE), _read(cache) if cache.exists() else
                  pd.DataFrame(columns=COLUMNS))  # fmt: skip
    if not offline:
        try:
            df = merge(saved, fetch())
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", "Live from USDA AMS Iowa grain and feedstuff reports."
        except Exception as e:  # network, PDF or layout problems all fall back to saved data
            problem = f"Couldn't reach USDA ({type(e).__name__})."
    else:
        problem = "Offline mode."
    return saved, "cache" if cache.exists() else "sample", f"{problem} Showing saved prices."


def latest(df: pd.DataFrame, item: str) -> tuple[float, pd.Timestamp] | None:
    """Newest value of one item and its date."""
    x = df[df["item"] == item]
    if x.empty:
        return None
    row = x.sort_values("date").iloc[-1]
    return float(row["value"]), pd.Timestamp(str(row["date"]))
