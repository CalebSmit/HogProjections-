"""Read lean hog futures from a quote export (Barchart, DTN ProphetX or similar), so contract
prices don't have to be typed. Pure: bytes in, prices out.

Accepted, CSV or Excel:
- a quote board: one row per contract with a symbol (HEZ26, HEZ6, @HEZ26, HEZ26.CME, LHZ26)
  and a Settle / Last / Close / Price column ("73.425s" style suffixes are fine);
- one contract's price history (Barchart's "price-history" download): the symbol comes from the
  file name and the newest row is used.
"""

import io
import re
from datetime import date, datetime

import pandas as pd

MONTH_CODES = {"G": 2, "J": 4, "K": 5, "M": 6, "N": 7, "Q": 8, "V": 10, "Z": 12}
SYMBOL = re.compile(r"(?<![A-Z])@?(?:HE|LH)([GJKMNQVZ])(\d{1,2})(?![0-9])", re.I)
PRICE_COLUMNS = ("settle", "settlement", "last", "latest", "close", "price", "previous", "prev")
DATE_COLUMNS = ("time", "date", "trade date", "tradedate")


def _num(v: object) -> float | None:
    s = re.sub(r"[^0-9.\-]", "", str(v))
    try:
        return float(s) if s not in ("", "-", ".") else None
    except ValueError:
        return None


def _contract(code: str, yy: str, today: date) -> tuple[int, int]:
    month = MONTH_CODES[code.upper()]
    if len(yy) == 2:
        return 2000 + int(yy), month
    # One digit: the year ending in that digit nearest to today (contracts list ~2 years out, and
    # a file may be a few months old), so in Jan 2030 "Z9" is Dec 2029, not 2039.
    base = today.year - today.year % 10 + int(yy)
    year = min((base - 10, base, base + 10), key=lambda y: abs(y - today.year))
    return year, month


def _read(data: bytes, name: str) -> pd.DataFrame:
    if name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(data), dtype=str)
    text = data.decode("utf-8-sig", errors="replace")
    return pd.read_csv(io.StringIO(text), dtype=str, on_bad_lines="skip", engine="python")


def _price_col(df: pd.DataFrame) -> str | None:
    cols = {str(c).strip().lower(): c for c in df.columns}
    for want in PRICE_COLUMNS:
        if want in cols:
            return cols[want]
    return None


def parse(data: bytes, name: str, today: date | None = None
          ) -> tuple[dict[tuple[int, int], float], date | None]:  # fmt: skip
    """(contract -> $/cwt, as-of date if the file says) from a quote export."""
    today = today or date.today()
    df = _read(data, name)
    price_col = _price_col(df)
    if price_col is None:
        raise ValueError("No Settle/Last/Close/Price column found")
    out: dict[tuple[int, int], float] = {}
    for row in df.to_dict("records"):
        text = " ".join(str(v) for v in row.values() if v is not None)
        m = SYMBOL.search(text)
        price = _num(row.get(price_col))
        if m and price and 20 < price < 300:
            out.setdefault(_contract(m[1], m[2], today), price)
    as_of = None
    found = re.search(r"(\d{2})-(\d{2})-(\d{4})", name) or re.search(
        r"as of (\d{2})-(\d{2})-(\d{4})", data.decode("utf-8", errors="ignore"))  # fmt: skip
    if found:
        as_of = datetime(int(found[3]), int(found[1]), int(found[2])).date()
    if out and as_of is None:  # no "as of" line: the newest trade date on the board, if any
        cols = {str(c).strip().lower(): c for c in df.columns}
        date_col = next((cols[c] for c in DATE_COLUMNS if c in cols), None)
        if date_col is not None:
            d = pd.to_datetime(df[date_col], errors="coerce", format="mixed").dropna()
            d = d[d.dt.date <= today]
            as_of = pd.Timestamp(str(d.max())).date() if len(d) else None
    if out:
        return out, as_of
    # A single contract's history: symbol in the file name, newest row's price.
    m = SYMBOL.search(name.upper())
    if not m:
        raise ValueError("No lean hog contract symbols found")
    cols = {str(c).strip().lower(): c for c in df.columns}
    date_col = next((cols[c] for c in DATE_COLUMNS if c in cols), None)
    hist = df.assign(_p=df[price_col].map(_num)).dropna(subset=["_p"])
    if date_col is not None:
        hist = hist.assign(_d=pd.to_datetime(hist[date_col], errors="coerce")).dropna(subset=["_d"])
        hist = hist.sort_values("_d")
        as_of = as_of or pd.Timestamp(str(hist["_d"].iloc[-1])).date()
    if hist.empty:
        raise ValueError("No prices found")
    return {_contract(m[1], m[2], today): float(hist["_p"].iloc[-1])}, as_of
