"""Check every live data source on a machine with internet (PLAN Phase 4), in one go.

    uv run python scripts/check_live.py                 # report only
    uv run python scripts/check_live.py --write-sample  # also bundle the sample basis file

Prints PASS / WARN / FAIL per source with the app's own note, so you can see exactly what the
dashboard will show. Nothing here is needed to use the app; it is for whoever maintains it.
"""

import shutil
import sys
from datetime import date, timedelta

from hogproj.basis import lean_hog_contract_for
from hogproj.config import SAMPLE_DIR, get_settings
from hogproj.data.http import cache_path
from hogproj.data.market import (
    BASIS_FILE,
    load_grain_futures,
    load_hog_basis_daily,
    load_hog_futures_curve,
    load_wean_pig_prices,
)

results: list[tuple[str, str, str]] = []


def report(name: str, ok: bool | None, detail: str) -> None:
    status = "PASS" if ok else "WARN" if ok is None else "FAIL"
    results.append((status, name, detail))
    print(f"[{status}] {name}\n       {detail}\n")


def main() -> int:
    if get_settings().offline:
        print("OFFLINE=true in .env: set it to false to check live sources.")
        return 1

    basis = load_hog_basis_daily(years=12, refresh=True)
    s = basis.data
    detail = basis.note
    if basis.live and hasattr(s, "index") and len(s):
        detail += " Last 3 days: " + ", ".join(
            f"{d:%Y-%m-%d} {v:+.2f}"
            for d, v in s.tail(3).items()  # type: ignore[union-attr]
        )
        detail += ". Compare the index with CME's published value for the same day (±$0.05)."
    report("Hog basis (CME Lean Hog Index − front-month futures)", basis.live, detail)

    today = date.today()
    codes = sorted({lean_hog_contract_for(today + timedelta(days=d)) for d in (120, 150, 180)})
    curve = load_hog_futures_curve(codes)
    found = curve.data if isinstance(curve.data, dict) else {}
    report(
        f"Lean hog futures {', '.join(codes)}",
        True if len(found) == len(codes) else None if found else False,
        f"{curve.note} Got: {found or 'nothing'}",
    )

    grain = load_grain_futures()
    report("CBOT corn and soybean meal futures", grain.live, f"{grain.note} {grain.data}")

    has_key = bool(get_settings().usda_mmn_api_key)
    wean = load_wean_pig_prices(2400)
    df = wean.data
    tail = ""
    if hasattr(df, "tail") and len(df):
        last = df.dropna(subset=["cash_usd_hd"]).tail(1).to_dict("records")  # type: ignore[union-attr]
        tail = f" Latest: {last}"
    report(
        "USDA weaned pig price (report 2810)",
        wean.live if has_key else None,
        (wean.note + tail)
        + ("" if has_key else " No USDA_MMN_API_KEY in .env, so this used the fallback."),
    )
    raw = cache_path("usda_2810_raw.json")
    if raw.exists():
        print(
            f"       Raw USDA response saved at {raw}: copy it to tests/fixtures/ if the parser "
            "needed changes.\n"
        )

    if "--write-sample" in sys.argv:
        src = cache_path(BASIS_FILE)
        if basis.live and src.exists():
            SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, SAMPLE_DIR / BASIS_FILE)
            print(f"Wrote {SAMPLE_DIR / BASIS_FILE}. Commit it so offline users get a real basis.")
        else:
            print("Not writing the sample: the basis wasn't downloaded live.")

    failed = [r for r in results if r[0] == "FAIL"]
    print(f"{len(results) - len(failed)} of {len(results)} sources OK or usable.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
