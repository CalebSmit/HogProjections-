import pytest
from streamlit.testing.v1 import AppTest

from hogproj.config import ROOT, get_settings


def test_settings_load_without_env():
    s = get_settings()
    assert isinstance(s.offline, bool)


def headline_figures(at: AppTest) -> str:
    """Text of the page's headline numbers: native metrics or the stat strip / quote hero."""
    parts = [f"{m.label} {m.value} {m.delta}" for m in at.metric]
    parts += [
        md.value
        for md in at.markdown
        if not md.value.lstrip().startswith("<style")  # the global stylesheet names the classes
        and ('class="hp-stat"' in md.value or 'class="hp-quote' in md.value)
    ]
    return " ".join(parts)


def test_app_renders():
    at = AppTest.from_file(str(ROOT / "app.py")).run(timeout=60)
    assert not at.exception
    assert at.title[0].value.startswith("Hogs ")  # This week leads with the week's move
    assert any("weekly brief" in str(b.proto.label) for b in at.get("download_button"))
    at.switch_page("views/0_Overview.py").run()
    assert not at.exception
    assert (
        at.title[0].value.replace("\\", "").startswith("At $")
    )  # the farm outlook headline states the finding


def app() -> AppTest:
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()


@pytest.mark.parametrize("page", sorted(p.name for p in (ROOT / "views").glob("*.py")))
def test_pages_render(page):
    # Run through the router so links between pages resolve, as they do in the real app.
    at = app().switch_page(f"views/{page}").run()
    assert not at.exception
    if page != "7_Guide.py":  # the guide is prose by design
        assert headline_figures(at)  # every other page leads with headline numbers


def test_overview_follows_inputs_from_other_pages():
    at = app().switch_page("views/0_Overview.py").run()
    before = headline_figures(at)
    at.switch_page("views/1_Herd_flow.py").run()
    at.number_input(key="herd_sows").set_value(2000).run()
    at.switch_page("views/0_Overview.py").run()
    assert not at.exception
    after = headline_figures(at)
    assert after != before
    assert "pigs sold" in after


def test_herd_change_flows_to_costs_page():
    at = AppTest.from_file(str(ROOT / "views" / "1_Herd_flow.py")).run(timeout=30)
    at.number_input(key="herd_sows").set_value(2000).run(timeout=30)
    inp = at.session_state["herd_inputs"]
    # No phantom herd cut: with no change entered, the herd stays at today's size.
    assert inp.sows_start == inp.sows_target == 2000
    at.number_input(key="herd_sows_change").set_value(500).run(timeout=30)
    assert at.session_state["herd_inputs"].sows_target == 2500


def test_saved_inputs_drive_every_page_without_visiting_them():
    # Loading a setup file sets widget keys directly; the Overview must use them even though
    # the Herd flow and Costs pages were never opened.
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.session_state["herd_sows"] = 2400
    at.session_state["cost_hog"] = 95.0
    at.run()
    at.switch_page("views/0_Overview.py").run()
    assert not at.exception
    kicker = " ".join(md.value for md in at.markdown if "hp-kicker" in md.value)
    assert "2,400 sows" in kicker
    assert at.title[0].value.replace("\\", "").startswith("At $95.00")


def test_wean_to_finish_follows_its_inputs():
    at = app().switch_page("views/8_Wean_to_finish.py").run()
    before = at.title[0].value
    at.number_input(key="w2f_adder").set_value(10.0).run()
    assert not at.exception
    assert at.title[0].value != before  # $10 more per pig changes the margin in the headline


def test_crush_history_follows_wean_to_finish_inputs():
    at = app().switch_page("views/9_Crush_history.py").run()
    before = at.title[0].value
    at.session_state["w2f_adder"] = 10.0
    at.run()
    assert not at.exception
    assert at.title[0].value != before  # a $10 adder lowers every past margin


def test_hedging_page_follows_hedges():
    at = app().switch_page("views/10_Hedging.py").run()
    assert "none of it hedged" in at.title[0].value
    pct = [w for w in at.number_input if str(w.key).startswith("w2f_hedge_") and
           str(w.key).endswith("_pct")]  # fmt: skip
    assert pct  # one per contract that prices pigs on feed
    pct[-1].set_value(50.0).run()
    assert not at.exception
    assert "locked in" in at.title[0].value


def test_sow_farm_follows_herd_productivity():
    at = app().switch_page("views/11_Sow_farm.py").run()
    before = at.title[0].value
    at.session_state["herd_born"] = 16.0  # more pigs per litter -> cheaper weaned pig
    at.run()
    assert not at.exception
    assert at.title[0].value != before
