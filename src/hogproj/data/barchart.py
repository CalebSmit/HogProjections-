"""Import price history the user downloaded from Barchart (CSV or Excel).

Two layouts are handled:
- the website "Download" CSV: header `Time,Open,High,Low,Latest,...`, footer
  "Downloaded from Barchart.com as of ...";
- the Barchart for Excel layout: a `1 Day | SYMBOL` row, then `Date,Open,High,Low,Close`, with
  `---` rows on holidays.
An Excel workbook may hold several series, one per sheet (e.g. the owner's crush workbook).

Each series is stored as data/cache/barchart/<kind>[_<contract>].csv (date, value). Barchart's
terms don't allow redistribution, so imports stay on this computer and are never committed.
"""

import io
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pandas as pd

from hogproj.config import CACHE_DIR

STORE = CACHE_DIR / "barchart"
MONTH_CODE = {"G": 2, "J": 4, "K": 5, "M": 6, "N": 7, "Q": 8, "V": 10, "Z": 12}


class Kind(StrEnum):
    CME_INDEX = "CME Lean Hog Index"
    HOG_FUTURES = "Lean hog futures (one contract)"
    CORN_CASH = "Corn cash ($/bu)"  # e.g. CORN$ cash index: already includes basis
    CORN_FUTURES = "Corn futures ($/bu)"
    SBM = "Soybean meal ($/ton)"
    WEAN_PIG = "USDA weaned pig ($/head)"


@dataclass(frozen=True)
class Series:
    name: str  # where it came from: file / sheet / symbol
    symbol: str
    kind: Kind | None  # best guess; the user can change it
    contract: str | None  # "2027-04" for one lean hog contract
    data: pd.Series  # date -> value


def _number(text: str) -> float:
    """'4.73', '1,234.5', and grain-style eighths '420-2' (= 420 2/8)."""
    t = text.replace(",", "").strip()
    m = re.fullmatch(r"(-?\d+)-([0-7])", t)
    if m:
        return float(m.group(1)) + int(m.group(2)) / 8
    return float(t)


def to_dollars(series: pd.Series, kind: Kind) -> pd.Series:
    """Corn futures/cash are often quoted in cents per bushel; store $/bu."""
    if kind in (Kind.CORN_CASH, Kind.CORN_FUTURES) and len(series) and series.median() > 50:
        return series / 100
    return series


PLAUSIBLE = {
    Kind.CME_INDEX: (30, 200),
    Kind.HOG_FUTURES: (30, 200),
    Kind.CORN_CASH: (1, 15),
    Kind.CORN_FUTURES: (1, 15),
    Kind.SBM: (100, 1000),
    Kind.WEAN_PIG: (0, 200),
}


def implausible(series: pd.Series, kind: Kind) -> str | None:
    """A warning if the latest value is far outside the usual range for this series."""
    lo, hi = PLAUSIBLE[kind]
    v = float(to_dollars(series, kind).iloc[-1]) if len(series) else 0.0
    if not lo <= v <= hi:
        return f"latest value {v:,.2f} looks wrong for {kind} (usually {lo}–{hi})"
    return None


def _cell(v: object) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def normalise_contract(text: str) -> str:
    """'2027-04', 'HEJ27' or '@HEJ27' -> '2027-04'; anything else is an error."""
    t = text.strip()
    if re.fullmatch(r"\d{4}-(02|04|05|06|07|08|10|12)", t):
        return t
    code = hog_contract_from_symbol(t)
    if code:
        return code
    raise ValueError(
        f"'{text}' isn't a lean hog contract. Use YYYY-MM for a listed month (Feb, Apr, May, "
        "Jun, Jul, Aug, Oct, Dec), e.g. 2027-04, or a symbol like HEJ27."
    )


def hog_contract_from_symbol(text: str) -> str | None:
    """'HEJ27', '@HEJ27', 'hej27_price-history.csv' -> '2027-04'."""
    m = re.search(r"HE([GJKMNQVZ])(\d{2})", text.upper())
    if not m:
        return None
    return f"{2000 + int(m.group(2))}-{MONTH_CODE[m.group(1)]:02d}"


def guess_kind(text: str) -> Kind | None:
    t = text.upper()
    if "LS255" in t or "WEAN" in t or " WP" in f" {t}" or "ISOWEAN" in t:
        return Kind.WEAN_PIG
    if "INDEX" in t or "KTCI" in t or re.search(r"(^|[^A-Z])LHI($|[^A-Z])", t):
        return Kind.CME_INDEX
    if hog_contract_from_symbol(t):
        return Kind.HOG_FUTURES
    if "MEAL" in t or "SBM" in t or re.search(r"(^|[^A-Z])(@SM|ZM)[A-Z]?\d", t):
        return Kind.SBM
    if re.search(r"(^|[^A-Z])(@C|ZC)[FHKNUZ]\d", t) or "CORN FUT" in t:
        return Kind.CORN_FUTURES
    if "CORN" in t or "ZCPAUS" in t:
        return Kind.CORN_CASH  # cash indexes / spot series (e.g. CORN$.5328, "Corn Spot")
    return None


def parse_grid(grid: pd.DataFrame, name: str, hint: str = "") -> Series | None:
    """Find the header row (a 'Date'/'Time' column + 'Close'/'Latest'/'Last'), read rows below."""
    rows = grid.astype(object).values.tolist()
    symbol = ""
    for i, row in enumerate(rows[:10]):
        cells = [_cell(c) for c in row]
        lower = [c.lower() for c in cells]
        if cells and lower[0] in ("1 day", "1 wk", "1 week", "1 month") and len(cells) > 1:
            symbol = cells[1]
        date_col = next((j for j, c in enumerate(lower) if c in ("date", "time")), None)
        value_col = next(
            (j for j, c in enumerate(lower) if c in ("close", "latest", "last", "settle")), None
        )
        if date_col is None or value_col is None:
            continue
        dates, values = [], []
        for r in rows[i + 1 :]:
            d = pd.to_datetime(_cell(r[date_col]), errors="coerce")
            try:
                v = _number(_cell(r[value_col]))
            except ValueError:
                continue  # '---', footer lines, blanks
            if pd.notna(d):
                dates.append(d)
                values.append(v)
        if not values:
            return None
        idx = pd.DatetimeIndex(pd.to_datetime(pd.Series(dates)).dt.normalize())
        s = pd.Series(values, index=idx, dtype="float64")
        s = s.loc[~s.index.duplicated(keep="last")].sort_index()
        s.index.name = "date"
        # Guess from the series' own label (sheet name + symbol) before the file name: a
        # workbook called "...Wean Pig Crush.xlsx" holds corn and meal sheets too.
        label = f"{hint} {symbol}".strip() or name
        kind = guess_kind(label) or guess_kind(name)
        return Series(
            name=name,
            symbol=symbol,
            kind=kind,
            contract=hog_contract_from_symbol(label) if kind is Kind.HOG_FUTURES else None,
            data=s,
        )
    return None


def read_upload(filename: str, content: bytes) -> list[Series]:
    """Every series found in an uploaded CSV or Excel file (one per sheet)."""
    if filename.lower().endswith((".xlsx", ".xlsm", ".xls")):
        sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)
        found = [
            parse_grid(g, f"{filename} / {sheet}", hint=str(sheet)) for sheet, g in sheets.items()
        ]
    else:
        text = content.decode("utf-8-sig", errors="replace")
        width = max(len(line.split(",")) for line in text.splitlines() if line) if text else 1
        grid = pd.read_csv(
            io.StringIO(text), header=None, names=range(width), dtype=str, skip_blank_lines=False
        )
        found = [parse_grid(grid, filename, hint=Path(filename).stem)]
    return [s for s in found if s is not None]


def _file(kind: Kind, contract: str | None) -> Path:
    slug = {
        Kind.CME_INDEX: "cme_index",
        Kind.HOG_FUTURES: "hog_futures",
        Kind.CORN_CASH: "corn_cash",
        Kind.CORN_FUTURES: "corn_futures",
        Kind.SBM: "sbm",
        Kind.WEAN_PIG: "wean_pig",
    }[kind]
    return STORE / (f"{slug}_{contract}.csv" if contract else f"{slug}.csv")


def save(series: pd.Series, kind: Kind, contract: str | None = None) -> Path:
    """Merge into any stored history for the same series (new values win)."""
    if kind is Kind.HOG_FUTURES:
        contract = normalise_contract(contract or "")
    series = to_dollars(series, kind)
    path = _file(kind, contract)
    path.parent.mkdir(parents=True, exist_ok=True)
    old = load(kind, contract)
    merged = pd.concat([old, series])
    merged = merged.loc[~merged.index.duplicated(keep="last")].sort_index()
    pd.DataFrame({"date": merged.index, "value": merged.to_numpy()}).to_csv(path, index=False)
    return path


def load(kind: Kind, contract: str | None = None) -> pd.Series:
    path = _file(kind, contract)
    if not path.exists():
        return pd.Series(dtype="float64")
    df = pd.read_csv(path, parse_dates=["date"])
    return pd.Series(df["value"].to_numpy(), index=pd.DatetimeIndex(df["date"]), dtype="float64")


def hog_contracts() -> dict[str, pd.Series]:
    """All stored lean hog contract histories, by contract code."""
    out = {}
    for path in sorted(STORE.glob("hog_futures_*.csv")):
        code = path.stem.removeprefix("hog_futures_")
        out[code] = load(Kind.HOG_FUTURES, code)
    return out


def inventory() -> pd.DataFrame:
    """What's been imported: one row per stored series."""
    rows = []
    for path in sorted(STORE.glob("*.csv")) if STORE.exists() else []:
        df = pd.read_csv(path, parse_dates=["date"])
        rows.append(
            {
                "file": path.name,
                "rows": len(df),
                "from": df["date"].min().date() if len(df) else None,
                "to": df["date"].max().date() if len(df) else None,
            }
        )
    return pd.DataFrame(rows, columns=["file", "rows", "from", "to"])


def delete(file_name: str) -> None:
    (STORE / Path(file_name).name).unlink(missing_ok=True)
