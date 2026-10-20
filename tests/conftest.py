import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Tests never touch the network: pages fall back to cached or bundled sample data."""
    monkeypatch.setenv("OFFLINE", "true")
