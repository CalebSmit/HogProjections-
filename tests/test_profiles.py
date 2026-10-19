import pytest

from hogproj.data import profiles


def test_save_load_list_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "PROFILE_DIR", tmp_path / "profiles")
    assert profiles.list_profiles() == []
    stem = profiles.save_profile("My System 2026 Q2", {"in_ga": 2.5, "phases": [{"a": 1}]})
    assert stem == "My System 2026 Q2"
    assert profiles.list_profiles() == ["My System 2026 Q2"]
    assert profiles.load_profile("My System 2026 Q2")["in_ga"] == 2.5
    profiles.delete_profile("My System 2026 Q2")
    assert profiles.list_profiles() == []


def test_names_are_sanitised(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "PROFILE_DIR", tmp_path)
    assert profiles.save_profile("../../etc/passwd", {}) == "....etcpasswd"
    assert (tmp_path / "....etcpasswd.json").exists()
    with pytest.raises(ValueError):
        profiles.save_profile("///", {})
