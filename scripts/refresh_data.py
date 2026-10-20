"""Refresh the USDA data bundled with the app (data/sample) and check every source still reads.

    uv run python scripts/refresh_data.py

Run weekly by .github/workflows/refresh-data.yml so a fresh download is never old and a USDA
format change is caught within a week. Keyless sources always run; My Market News and NASS run
only when their keys are set (as environment variables or GitHub secrets). Exits 1 if any
source that should work didn't, after saving everything that did.
"""

import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hogproj.config import CACHE_DIR, SAMPLE_DIR, get_settings  # noqa: E402
from hogproj.data import ams, eia, ers, feed, feeder, isu, lmr, mars, nass, regional, wasde  # noqa: E402


def main() -> int:
    os.environ["OFFLINE"] = "false"
    s = get_settings()
    checks = {
        "LM_HG201 hog prices": (lambda: ams.load_hg201(False), ams.HG201_FILE),
        "LM_PK602 cutout": (lambda: lmr.load(lmr.CUTOUT, False), lmr.CUTOUT.file),
        "Feeder pig report": (lambda: feeder.load(False), feeder.FEEDER_FILE),
        "Iowa grain + feedstuffs": (lambda: feed.load(False), feed.FEED_FILE),
        "WASDE": (lambda: wasde.load(False), wasde.WASDE_FILE),
        "WASDE history": (lambda: wasde.load_history(False), wasde.HISTORY_FILE),
        "ERS cold storage": (lambda: ers.load(False), ers.ERS_FILE),
        "Iowa State returns": (lambda: isu.load(False), isu.ISU_FILE),
        "EIA fuel prices": (lambda: eia.load(False), eia.EIA_FILE),
    }
    for name, (_, _, file, _) in regional.DATASETS.items():
        checks[f"LMR regional {name}"] = (lambda n=name: regional.load(n, False), file)
    if s.nass_api_key.strip():
        nk = s.nass_api_key.strip()
        checks["NASS Hogs and Pigs"] = (lambda: nass.load(nk, False), nass.NASS_FILE)
        checks["NASS Iowa corn"] = (lambda: nass.load_corn(nk, False), nass.CORN_FILE)
    if s.usda_mmn_api_key.strip():
        mk = s.usda_mmn_api_key.strip()
        for name in mars.DATASETS:
            checks[f"My Market News {name}"] = (lambda n=name: mars.load(n, mk, False), None)
        for name, spec in mars.MULTI.items():
            checks[f"My Market News {name}"] = (lambda n=name: mars.load(n, mk, False), spec[3])
    failed = []
    for label, (run, sample_file) in checks.items():
        df, source, note = run()
        if source != "live":  # USDA servers hiccup; one retry before calling it broken
            time.sleep(20)
            df, source, note = run()
        ok = source == "live" and len(df) > 0
        print(f"{'ok  ' if ok else 'FAIL'} {label}: {len(df)} rows · {note}")
        if not ok:
            failed.append(label)
        elif sample_file and (CACHE_DIR / sample_file).exists():
            shutil.copyfile(CACHE_DIR / sample_file, SAMPLE_DIR / sample_file)
    if failed:
        print("Sources that didn't refresh: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
