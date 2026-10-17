"""Shared HTTP client and a small on-disk cache. The only module that opens network sockets."""

import json
import time
from pathlib import Path
from typing import Any

import httpx

from hogproj.config import CACHE_DIR

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 HogProjections/0.1"
)


class FetchError(RuntimeError):
    """A data source could not be reached or returned something unusable."""


def get_json(
    url: str,
    params: dict[str, str] | None = None,
    auth: tuple[str, str] | None = None,
    retries: int = 3,
    timeout: float = 30.0,
) -> Any:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = httpx.get(
                url,
                params=params,
                auth=auth,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=timeout,
                follow_redirects=True,
            )
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise FetchError(f"{url}: {last}") from last


def cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


def read_cached_json(name: str, max_age_hours: float) -> Any | None:
    path = cache_path(name)
    if not path.exists() or (time.time() - path.stat().st_mtime) > max_age_hours * 3600:
        return None
    return json.loads(path.read_text())


def write_cached_json(name: str, data: Any) -> None:
    cache_path(name).write_text(json.dumps(data))
