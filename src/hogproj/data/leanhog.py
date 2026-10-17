"""CME Lean Hog Index (rebuilt from USDA LM_HG201) and lean hog futures (Yahoo Finance).

Index: USDA AMS LMR Datamart, report 2511 = LM_HG201 "National Daily Direct Hog Prior Day
Report - Slaughtered Swine". It is keyless JSON. CME builds the Lean Hog Index from the same
report: producer-sold barrows & gilts, purchase types Negotiated + Swine/Pork Market Formula +
Negotiated Formula (that last one only from 2016-10-12, CME SER-7740), weighted by head x
carcass weight, two-day rolling. Reference implementation: github.com/kirkedev/mpr.kirke.dev.

Futures: Yahoo chart API. HE=F is the continuous front month; it rolls at expiry.
"""

from datetime import date, datetime, timedelta

import pandas as pd

from hogproj.data.http import FetchError, get_json

DATAMART = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports/2511"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
NEG_FORMULA_START = date(2016, 10, 12)
MONTH_CODES = {2: "G", 4: "J", 5: "K", 6: "M", 7: "N", 8: "Q", 10: "V", 12: "Z"}


def _num(v: object) -> float | None:
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _purchase_bucket(purchase_type: str) -> str | None:
    """Map an LM_HG201 purchase_type to an index bucket, or None if not in the index."""
    t = purchase_type.lower().strip()
    if not t.startswith("prod"):  # packer-sold rows are excluded
        return None
    if "negotiated formula" in t:
        return "negotiated_formula"
    if "swine or pork market formula" in t or "swine/pork market formula" in t:
        return "spmf"
    if t.endswith("negotiated"):
        return "negotiated"
    return None


def parse_lm_hg201(results: list[dict]) -> pd.DataFrame:
    """Barrows/Gilts rows -> report_date, bucket, head, carcass_lb, net_price_cwt."""
    rows = []
    for rec in results:
        bucket = _purchase_bucket(str(rec.get("purchase_type", "")))
        head = _num(rec.get("head_count"))
        wt = _num(rec.get("avg_carcass_weight"))
        price = _num(rec.get("avg_net_price"))
        if bucket is None or not head or not wt or price is None:
            continue
        rows.append(
            {
                "report_date": datetime.strptime(str(rec["report_date"]), "%m/%d/%Y").date(),
                "bucket": bucket,
                "head": head,
                "carcass_lb": wt,
                "net_price_cwt": price,
            }
        )
    return pd.DataFrame(
        rows, columns=["report_date", "bucket", "head", "carcass_lb", "net_price_cwt"]
    )


def cme_index(rows: pd.DataFrame) -> pd.Series:
    """Two-day weighted Lean Hog Index ($/cwt carcass), indexed by report date."""
    df = rows.copy()
    pre = pd.to_datetime(df["report_date"]) < pd.Timestamp(NEG_FORMULA_START)
    df = df[~(pre & (df["bucket"] == "negotiated_formula"))]
    df["lbs"] = df["head"] * df["carcass_lb"]
    df["value"] = df["lbs"] * df["net_price_cwt"]
    daily = df.groupby("report_date")[["lbs", "value"]].sum().sort_index()
    two_day = daily.rolling(2).sum().dropna()
    out = two_day["value"] / two_day["lbs"]
    out.index = pd.to_datetime(out.index)
    return out.rename("cme_index_cwt")


def fetch_lm_hg201(start: date, end: date) -> pd.DataFrame:
    """Pull Barrows/Gilts rows in ~1-year chunks (the API caps result size)."""
    frames = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(end, chunk_start + timedelta(days=364))
        q = f"report_date={chunk_start:%m/%d/%Y}:{chunk_end:%m/%d/%Y}"
        data = get_json(f"{DATAMART}/Barrows/Gilts", params={"q": q})
        results = data.get("results", []) if isinstance(data, dict) else []
        frames.append(parse_lm_hg201(results))
        chunk_start = chunk_end + timedelta(days=1)
    if not frames:
        return parse_lm_hg201([])
    return pd.concat(frames, ignore_index=True)


def parse_yahoo_chart(data: dict) -> pd.Series:
    try:
        res = data["chart"]["result"][0]
        ts = res["timestamp"]
        close = res["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError) as e:
        raise FetchError(f"unexpected Yahoo response: {e}") from e
    idx = pd.to_datetime(pd.Series(ts), unit="s").dt.normalize()
    s = pd.Series(close, index=idx, dtype="float64").dropna()
    s.index.name = "date"
    return s[~s.index.duplicated(keep="last")]


def fetch_yahoo_daily(symbol: str, start: date, end: date) -> pd.Series:
    p1 = int(datetime(start.year, start.month, start.day).timestamp())
    p2 = int(datetime(end.year, end.month, end.day).timestamp()) + 86400
    data = get_json(
        YAHOO_CHART.format(symbol=symbol),
        params={"period1": str(p1), "period2": str(p2), "interval": "1d"},
    )
    return parse_yahoo_chart(data)


def yahoo_contract_symbol(code: str) -> str:
    """'2027-04' -> 'HEJ27.CME' [VERIFY: Yahoo symbol format for individual HE contracts]."""
    year, month = (int(x) for x in code.split("-"))
    return f"HE{MONTH_CODES[month]}{year % 100:02d}.CME"


def fetch_futures_curve(codes: list[str]) -> dict[str, float]:
    """Latest settle per contract code. Contracts Yahoo doesn't serve are skipped."""
    out: dict[str, float] = {}
    today = date.today()
    for code in codes:
        try:
            s = fetch_yahoo_daily(yahoo_contract_symbol(code), today - timedelta(days=10), today)
        except FetchError:
            continue
        if not s.empty:
            out[code] = float(s.iloc[-1])
    return out
