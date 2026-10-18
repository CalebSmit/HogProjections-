import json
from datetime import date, timedelta

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


# ---- regressions from the dashboard review (data_editor edits sent as widget state) ----


def editor_id(at: AppTest, key_prefix: str) -> str:
    return next(d.proto.id for d in at.dataframe if key_prefix in d.proto.id)


def edit(at: AppTest, key_prefix: str, state: dict) -> AppTest:
    """Send a data_editor edit the way the browser does (private but stable API)."""
    wid = editor_id(at, key_prefix)
    ws = at._tree.get_widget_states()
    w = next((w for w in ws.widgets if w.id == wid), None) or ws.widgets.add()
    w.id = wid
    w.string_value = json.dumps({"edited_rows": {}, "added_rows": [], "deleted_rows": [], **state})
    return at._run(widget_state=ws)


def errors(at: AppTest) -> str:
    return " ".join(e.value for e in at.error)


def test_two_consecutive_editor_edits_both_apply(app):
    at = edit(app, "cuts_", {"edited_rows": {"0": {"pct_of_marketed": 30}}})
    assert "add up to 100" in errors(at)
    at = edit(
        at, "cuts_", {"edited_rows": {"0": {"pct_of_marketed": 30}, "2": {"pct_of_marketed": 30}}}
    )
    assert not at.error, errors(at)


def test_cleared_phase_cell_is_reported_not_dropped(app):
    at = edit(app, "phases_", {"edited_rows": {"4": {"feed_lb_per_pig": None}}})
    assert "is missing: feed_lb_per_pig" in errors(at)
    assert not at.metric  # no misleading projection


def test_cleared_location_number_does_not_loop(app):
    at = edit(app, "loc_editor_", {"edited_rows": {"1": {"ddgs_usd_ton": None}}})
    assert not at.exception
    assert "is missing: ddgs_usd_ton" in errors(at)
    assert at.metric  # last good locations still project


def test_deleting_every_location_keeps_app_alive(app):
    at = edit(app, "loc_editor_", {"deleted_rows": list(range(12))})
    assert not at.exception
    assert "at least one location" in errors(at)


def test_renaming_selected_location_keeps_it_selected(app):
    app.sidebar.selectbox[0].set_value("Central South Dakota").run(timeout=60)
    at = edit(app, "loc_editor_", {"edited_rows": {"2": {"name": "Pipestone SD"}}})
    assert not at.exception
    assert at.sidebar.selectbox[0].value == "Pipestone SD"


def test_cleared_basis_cell_counts_as_zero(app):
    at = edit(app, "basis_", {"edited_rows": {"5": {"basis_cwt": None}}})
    assert not at.exception
    assert all("nan" not in m.value for m in at.metric)


def test_future_placement_runs_with_copied_futures_warning(monkeypatch):
    monkeypatch.setenv("OFFLINE", "true")
    at = AppTest.from_file(str(ROOT / "app.py")).run(timeout=60)
    at.sidebar.date_input[0].set_value(date.today() + timedelta(days=60)).run(timeout=60)
    assert not at.exception
    assert not at.error, errors(at)
    assert at.metric
