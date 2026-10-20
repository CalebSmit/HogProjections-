"""Iowa State University Estimated Livestock Returns, farrow to finish (public PDF, monthly).

The app's farrow-to-finish cost model reproduces ISU's line items; this keeps its defaults on
ISU's latest published month instead of a fixed one. Each row of the PDF is a line item with
up to 12 monthly values; the sale months head the columns.
"""

import io
import re
from typing import Literal

import httpx
import pandas as pd

from hogproj.config import CACHE_DIR, SAMPLE_DIR
from hogproj.data.saved import newest

URL = "https://estimatedreturns.econ.iastate.edu/files/inline-files/farrow_to_finish_pdf.pdf"
ISU_FILE = "isu_farrow_to_finish.csv"
Source = Literal["live", "cache", "sample"]
ROWS = {  # PDF label -> column
    "Corn, $/hd": "corn",
    "Soybean meal, $/hd": "sbm",
    "Dried distiller grain, $/hd": "ddgs",
    "Complete feeds & other ingredients, $/hd": "complete_other",
    "Feed processing, $/hd": "processing",
    "Variable costs, $/hd": "variable",
    "Operating interest, $/hd": "interest",
    "Fixed costs, $/hd": "fixed",
    "Death loss, $/hd": "death_loss",
    "Total Costs, $/hd": "total_cost",
    "Breakeven price, $/carcass cwt": "breakeven_carcass",
    "Selling price, $/carcass cwt": "price_carcass",
    "Profit (loss), $/hd": "profit",
    "Manure credit, $/hd": "manure_credit",
}
_NUM = r"-?\d+\.\d{2}"


def parse(text: str) -> pd.DataFrame:
    """PDF text -> one row per sale month with every line item ISU has published."""
    sale = re.search(r"Sale month ((?:\w{3}-\d{2}\s*)+)", text)
    if not sale:
        raise ValueError("Not an ISU farrow-to-finish report")
    months = [pd.Timestamp(pd.to_datetime(m, format="%b-%y")) for m in sale[1].split()]
    data: dict[str, list[float]] = {}
    for line in text.splitlines():
        for label, col in ROWS.items():
            if line.strip().startswith(label):
                data[col] = [float(v) for v in re.findall(_NUM, line[len(label) + 1 :])]
    n = min((len(v) for v in data.values()), default=0)
    if n == 0:
        raise ValueError("No values found")
    df = pd.DataFrame({"sale_month": months[:n], **{k: v[:n] for k, v in data.items()}})
    return df


def fetch(client: httpx.Client | None = None) -> pd.DataFrame:
    from pypdf import PdfReader

    with client or httpx.Client(timeout=60, follow_redirects=True) as c:
        resp = c.get(URL)
        resp.raise_for_status()
    pages = PdfReader(io.BytesIO(resp.content)).pages
    return parse("\n".join(p.extract_text() for p in pages))


def load(offline: bool) -> tuple[pd.DataFrame, Source, str]:
    cache = CACHE_DIR / ISU_FILE
    if not offline:
        try:
            df = fetch()
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            return df, "live", "Live from Iowa State Estimated Livestock Returns."
        except Exception as e:  # network, PDF or layout change: keep the saved copy
            problem = f"Couldn't read Iowa State's report ({type(e).__name__})."
    else:
        problem = "Offline mode."
    path = newest(cache, SAMPLE_DIR / ISU_FILE)
    df = pd.read_csv(path, parse_dates=["sale_month"])
    return df, "cache" if path == cache else "sample", f"{problem} Showing saved figures."
