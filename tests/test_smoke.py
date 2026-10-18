from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from hogproj.config import ROOT, get_settings

# Bundled futures defaults cover sales from an Oct 2026 placement; later dates need live data.
PLACED = date(2026, 10, 19)


@pytest.fixture
def app(monkeypatch) -> AppTest:
    monkeypatch.setenv("OFFLINE", "true")  # never touch the network in tests
    at = AppTest.from_file(str(ROOT / "app.py")).run(timeout=60)
    at.sidebar.date_input[0].set_value(PLACED).run(timeout=60)
    return at


def metrics(at: AppTest) -> dict[str, str]:
    return {m.label: m.value for m in at.metric}


def test_settings_load_without_env():
    assert isinstance(get_settings().offline, bool)


def test_app_renders_projection_offline(app):
    assert not app.exception, app.exception
    assert app.title[0].value == "Wean-to-Finish Group Projection"
    assert "Breakeven $/cwt carcass" in metrics(app)
    assert not app.error, [e.value for e in app.error]


def test_location_switch_changes_result(app):
    before = metrics(app)["Cost per head sold"]
    app.sidebar.selectbox[0].set_value("Central South Dakota").run(timeout=60)
    assert not app.exception
    assert metrics(app)["Cost per head sold"] != before


def test_manual_wean_price_toggle(app):
    before = metrics(app)["Cost per head sold"]
    app.sidebar.radio[0].set_value(app.sidebar.radio[0].options[2]).run(timeout=60)  # Manual
    app.sidebar.number_input[3].set_value(60.0).run(timeout=60)  # Manual $/head
    assert not app.exception
    assert metrics(app)["Cost per head sold"] != before
