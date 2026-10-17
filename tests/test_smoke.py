from streamlit.testing.v1 import AppTest

from hogproj.config import ROOT, get_settings


def test_settings_load_without_env():
    s = get_settings()
    assert isinstance(s.offline, bool)


def test_app_renders():
    at = AppTest.from_file(str(ROOT / "app.py")).run(timeout=30)
    assert not at.exception
    assert at.title[0].value == "Hog Projections"
