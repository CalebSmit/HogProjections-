"""EIA weekly fuel prices: workbook parsing and the offline fallback."""

import io

import pandas as pd

from hogproj.data import eia


def _workbook() -> bytes:
    """Laid out like EIA's history files: a 'Data 1' sheet with two title rows."""
    buf = io.BytesIO()
    body = pd.DataFrame({"Date": pd.to_datetime(["2014-12-29", "2015-01-05", "2026-10-19"]),
                         "Price": [3.2, 3.137, 6.28]})  # fmt: skip
    with pd.ExcelWriter(buf) as xw:
        pd.DataFrame({"x": ["Back to Contents"]}).to_excel(xw, sheet_name="Data 1", index=False)
        body.to_excel(xw, sheet_name="Data 1", index=False, startrow=2)
    return buf.getvalue()


def test_parse_reads_data_sheet_from_2015():
    df = eia.parse(_workbook(), "diesel_us")
    assert list(df.columns) == ["date", "series", "usd_per_gal"]
    assert df["date"].min() == pd.Timestamp("2015-01-05")  # 2014 dropped
    assert df["usd_per_gal"].iloc[-1] == 6.28
    assert set(df["series"]) == {"diesel_us"}


def test_offline_load_uses_bundled_sample():
    df, source, _ = eia.load(offline=True)
    assert source in ("cache", "sample")
    assert {"diesel_us", "propane_mn"} <= set(df["series"])
    assert df["usd_per_gal"].between(0.5, 10).all()
