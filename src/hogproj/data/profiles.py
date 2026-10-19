"""Named settings profiles (e.g. "Pipestone 2026 Q2") saved on this computer only.

A profile is a JSON dict of the dashboard's settings: costs, ration, toggles. It holds no
market prices. Files live in data/user/profiles/, which git ignores, so company figures never
reach the repo.
"""

import json
import re
from pathlib import Path
from typing import Any

from hogproj.config import DATA_DIR

PROFILE_DIR = DATA_DIR / "user" / "profiles"


def _path(name: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9 _.-]+", "", name).strip()
    if not slug:
        raise ValueError("Give the profile a name (letters, numbers, spaces).")
    return PROFILE_DIR / f"{slug}.json"


def list_profiles() -> list[str]:
    if not PROFILE_DIR.exists():
        return []
    return sorted(p.stem for p in PROFILE_DIR.glob("*.json"))


def save_profile(name: str, settings: dict[str, Any]) -> str:
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2, default=str))
    return path.stem


def load_profile(name: str) -> dict[str, Any]:
    return json.loads(_path(name).read_text())


def delete_profile(name: str) -> None:
    _path(name).unlink(missing_ok=True)
