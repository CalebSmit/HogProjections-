import time

import pytest

from hogproj.data.http import FetchError, get_json
from hogproj.data.leanhog import fetch_futures_curve


def test_unreachable_host_fails_fast():
    start = time.monotonic()
    with pytest.raises(FetchError) as e:
        get_json("http://127.0.0.1:9/nothing")  # closed port: connection refused
    assert e.value.unreachable
    assert time.monotonic() - start < 3


def test_futures_curve_stops_after_first_unreachable(monkeypatch):
    calls = []

    def boom(*args, **kwargs):
        calls.append(args)
        raise FetchError("offline", unreachable=True)

    monkeypatch.setattr("hogproj.data.leanhog.fetch_yahoo_daily", boom)
    assert fetch_futures_curve(["2026-12", "2027-02", "2027-04"]) == {}
    assert len(calls) == 1
