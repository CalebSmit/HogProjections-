import pytest
from streamlit.testing.v1 import AppTest

from hogproj.config import ROOT, get_settings


def test_settings_load_without_env():
    s = get_settings()
    assert isinstance(s.offline, bool)


def test_app_renders():
    at = AppTest.from_file(str(ROOT / "app.py")).run(timeout=30)
    assert not at.exception
    assert at.title[0].value == "Farm outlook"


def app() -> AppTest:
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()


@pytest.mark.parametrize("page", sorted(p.name for p in (ROOT / "views").glob("*.py")))
def test_pages_render(page):
    # Run through the router so links between pages resolve, as they do in the real app.
    at = app().switch_page(f"views/{page}").run()
    assert not at.exception
    assert at.metric  # every page leads with headline numbers


def test_overview_follows_inputs_from_other_pages():
    at = app()
    before = at.metric[3].value  # "Next 12 months"
    at.switch_page("views/1_Herd_flow.py").run()
    at.number_input(key="herd_sows").set_value(2000).run()
    at.switch_page("views/0_Overview.py").run()
    assert not at.exception
    assert at.metric[3].value != before
    assert "pigs sold" in str(at.metric[3].delta)


def test_herd_change_flows_to_costs_page():
    at = AppTest.from_file(str(ROOT / "views" / "1_Herd_flow.py")).run(timeout=30)
    at.number_input(key="herd_sows").set_value(2000).run(timeout=30)
    inp = at.session_state["herd_inputs"]
    # No phantom herd cut: with no change entered, the herd stays at today's size.
    assert inp.sows_start == inp.sows_target == 2000
    at.number_input(key="herd_sows_change").set_value(500).run(timeout=30)
    assert at.session_state["herd_inputs"].sows_target == 2500
