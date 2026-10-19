import html
import json
import re
from datetime import date, timedelta

import pytest
from streamlit.testing.v1 import AppTest

from hogproj.config import ROOT, get_settings
from hogproj.inputs import InterestMode, MortalityMode, WeanPigPriceSource

# Bundled futures defaults cover sales from an Oct 2026 placement; later dates need live data.
PLACED = date(2026, 10, 19)


@pytest.fixture(autouse=True)
def isolated_user_data(tmp_path, monkeypatch):
    """Tests never see this machine's Barchart imports, saved profiles or locations."""
    from hogproj.data import barchart, defaults, profiles

    monkeypatch.setattr(barchart, "STORE", tmp_path / "barchart")
    monkeypatch.setattr(profiles, "PROFILE_DIR", tmp_path / "profiles")
    monkeypatch.setattr(defaults, "USER_DIR", tmp_path / "user")


@pytest.fixture
def app(monkeypatch) -> AppTest:
    monkeypatch.setenv("OFFLINE", "true")  # never touch the network in tests
    at = AppTest.from_file(str(ROOT / "app.py")).run(timeout=60)
    at.date_input(key="in_placement").set_value(PLACED).run(timeout=60)
    return at


KPI = re.compile(
    r'hp-kpi-label">([^<]*)(?:<span class="hp-q">\?</span>)?</div><div class="hp-kpi-value">([^<]*)'
)


def metrics(at: AppTest) -> dict[str, str]:
    """KPI cards (ui.kpi_cards / ui.hero_card), label -> value."""
    found = {}
    for h in at.get("html"):
        for label, value in KPI.findall(h.proto.body):
            found[html.unescape(label)] = html.unescape(value)
    return found


def test_settings_load_without_env():
    assert isinstance(get_settings().offline, bool)


def test_app_renders_projection_offline(app):
    assert not app.exception, app.exception
    assert any("Wean-to-Finish Group Projection" in h.proto.body for h in app.get("html"))
    assert "Breakeven $/cwt carcass" in metrics(app)
    assert "Net per head sold" in metrics(app)
    assert not app.error, [e.value for e in app.error]


def test_location_switch_changes_result(app):
    before = metrics(app)["Cost per head sold"]
    app.selectbox(key="loc_name").set_value("Central South Dakota").run(timeout=60)
    assert not app.exception
    assert metrics(app)["Cost per head sold"] != before


def test_manual_wean_price_toggle(app):
    before = metrics(app)["Cost per head sold"]
    app.radio(key="in_source").set_value(WeanPigPriceSource.MANUAL).run(timeout=60)
    app.number_input(key="in_wean_manual").set_value(60.0).run(timeout=60)
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
    assert not metrics(at)  # no misleading projection


def test_cleared_location_number_does_not_loop(app):
    at = edit(app, "loc_editor_", {"edited_rows": {"1": {"ddgs_usd_ton": None}}})
    assert not at.exception
    assert "is missing: ddgs_usd_ton" in errors(at)
    assert metrics(at)  # last good locations still project


def test_deleting_every_location_keeps_app_alive(app):
    at = edit(app, "loc_editor_", {"deleted_rows": list(range(12))})
    assert not at.exception
    assert "at least one location" in errors(at)


def test_renaming_selected_location_keeps_it_selected(app):
    app.selectbox(key="loc_name").set_value("Central South Dakota").run(timeout=60)
    at = edit(app, "loc_editor_", {"edited_rows": {"2": {"name": "Pipestone SD"}}})
    assert not at.exception
    assert at.selectbox(key="loc_name").value == "Pipestone SD"


def test_cleared_basis_cell_counts_as_zero(app):
    at = edit(app, "basis_", {"edited_rows": {"5": {"basis_cwt": None}}})
    assert not at.exception
    assert metrics(at) and all("nan" not in v for v in metrics(at).values())


def test_future_placement_runs_with_copied_futures_warning(monkeypatch):
    monkeypatch.setenv("OFFLINE", "true")
    at = AppTest.from_file(str(ROOT / "app.py")).run(timeout=60)
    at.date_input(key="in_placement").set_value(date.today() + timedelta(days=60)).run(timeout=60)
    assert not at.exception
    assert not at.error, errors(at)
    assert metrics(at)


def test_new_toggles_change_the_numbers(app):
    base_cost = metrics(app)["Cost per head sold"]
    app.radio(key="in_mort_mode").set_value(MortalityMode.USD_PER_PIG).run(timeout=60)
    app.number_input(key="in_mort_cost").set_value(6.0).run(timeout=60)
    app.radio(key="in_interest_mode").set_value(InterestMode.USD_PER_PIG).run(timeout=60)
    app.number_input(key="in_interest_per_pig").set_value(3.0).run(timeout=60)
    app.number_input(key="in_ga").set_value(2.0).run(timeout=60)
    app.number_input(key="in_wean_adder").set_value(7.0).run(timeout=60)
    app.number_input(key="in_principal").set_value(3.0).run(timeout=60)
    assert not app.exception
    assert "Can't run" not in errors(app)  # a projected-loss callout is fine
    m = metrics(app)
    assert m["Cost per head sold"] != base_cost
    assert "Net per head after debt service" in m


def test_whole_group_ration_mode(app):
    app.radio(key="in_ration_mode").set_value("Whole-group ration (lb per pig)").run(timeout=60)
    assert not app.exception
    assert not app.error, errors(app)
    assert any("Total feed: 710 lb" in c.value for c in app.caption)


def test_profile_round_trip(app, tmp_path, monkeypatch):
    from hogproj.data import profiles

    monkeypatch.setattr(profiles, "PROFILE_DIR", tmp_path)
    app.number_input(key="in_ga").set_value(2.5).run(timeout=60)
    app.text_input(key="profile_name").set_value("Test system Q2").run(timeout=60)
    next(b for b in app.button if b.label == "Save profile").click().run(timeout=60)
    assert profiles.list_profiles() == ["Test system Q2"]
    app.number_input(key="in_ga").set_value(0.0).run(timeout=60)
    app.selectbox(key="profile_pick").set_value("Test system Q2").run(timeout=60)
    next(b for b in app.button if b.label == "Load").click().run(timeout=60)
    assert not app.exception
    assert app.number_input(key="in_ga").value == 2.5


def test_weekly_crush_renders(app):
    assert not app.exception
    tables = [h.proto.body for h in app.get("html") if "CME contract" in h.proto.body]
    assert tables, "weekly crush table missing"
    assert "Margin $/pig" in tables[0]
    assert tables[0].count("<th>") >= 13  # row label + 12 weeks back (+ ahead)


def test_save_profile_after_switching_modes(app, tmp_path, monkeypatch):
    from hogproj.data import profiles

    monkeypatch.setattr(profiles, "PROFILE_DIR", tmp_path)
    app.number_input(key="in_mortality").set_value(8.0).run(timeout=60)
    app.radio(key="in_mort_mode").set_value(MortalityMode.USD_PER_PIG).run(timeout=60)
    app.radio(key="in_interest_mode").set_value(InterestMode.USD_PER_PIG).run(timeout=60)
    app.number_input(key="in_ga").set_value(1.0).run(timeout=60)
    app.text_input(key="profile_name").set_value("Dollar modes").run(timeout=60)
    next(b for b in app.button if b.label == "Save profile").click().run(timeout=60)
    assert not app.exception
    saved = profiles.load_profile("Dollar modes")
    assert saved["in_mortality"] == 8.0  # the inactive mode's value survives
    app.radio(key="in_mort_mode").set_value(MortalityMode.PCT_OF_HEAD).run(timeout=60)
    assert app.number_input(key="in_mortality").value == 8.0


def test_hedge_without_a_price_is_reported(app):
    app.number_input(key="in_corn_hedge_pct").set_value(50.0).run(timeout=60)
    assert not app.exception
    assert "Corn is 50% hedged: enter the hedged price." in errors(app)
    app.number_input(key="in_corn_hedged").set_value(4.25).run(timeout=60)
    assert "hedged price" not in errors(app)


def test_summary_sections_and_guide(app):
    bodies = " ".join(h.proto.body for h in app.get("html"))
    assert "Profit and loss" in bodies and "Net margin" in bodies
    assert "pigs</b> placed at" in bodies  # plain-English summary
    assert "How to use it" in bodies  # Guide tab
    assert "Average margin $/pig" in metrics(app)  # weekly crush summary
    assert "Ranking" in bodies  # locations ranking
