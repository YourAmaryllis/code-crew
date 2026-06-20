"""Tests for profile loading and switching."""

import os
from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# home.py helpers
# ---------------------------------------------------------------------------

def test_list_profiles_empty(tmp_path):
    from shared.home import list_profiles
    with patch("shared.home.PROFILES_DIR", tmp_path / "profiles"):
        result = list_profiles()
    assert result == []


def test_list_profiles_returns_stems(tmp_path):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "prod.yaml").write_text("env:\n  X: '1'\n")
    (profiles_dir / "staging.yaml").write_text("env:\n  X: '2'\n")
    (profiles_dir / "dev.yaml").write_text("env:\n  X: '3'\n")

    with patch("shared.home.PROFILES_DIR", profiles_dir):
        from shared.home import list_profiles as _lp
        result = _lp()

    assert result == ["dev", "prod", "staging"]


def test_list_profiles_includes_legacy_env(tmp_path):
    """Legacy .env files are still listed (for migration awareness)."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "legacy.env").write_text("X=1\n")
    (profiles_dir / "modern.yaml").write_text("env:\n  X: '1'\n")

    with patch("shared.home.PROFILES_DIR", profiles_dir):
        from shared.home import list_profiles as _lp
        result = _lp()

    assert result == ["legacy", "modern"]


def test_profile_path(tmp_path):
    with patch("shared.home.PROFILES_DIR", tmp_path / "profiles"):
        from shared.home import profile_path
        p = profile_path("prod")
    assert p.name == "prod.yaml"


def test_legacy_profile_path(tmp_path):
    with patch("shared.home.PROFILES_DIR", tmp_path / "profiles"):
        from shared.home import legacy_profile_path
        p = legacy_profile_path("prod")
    assert p.name == "prod.env"


# ---------------------------------------------------------------------------
# _bootstrap profile loading
#
# Strategy: use monkeypatch.chdir(tmp_path) so Path.cwd() returns the temp
# dir — avoids patching Path itself, which causes yaml.safe_load to receive a
# MagicMock and loop infinitely consuming all RAM.
# ---------------------------------------------------------------------------

def test_bootstrap_loads_global_config(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.write_text("SOME_GLOBAL_KEY=global_value\n")

    monkeypatch.delenv("CODE_CREW_PROFILE", raising=False)
    monkeypatch.delenv("SOME_GLOBAL_KEY", raising=False)
    monkeypatch.chdir(tmp_path)   # no .env / .code-crew.yaml here

    with patch("code_crew.repl.CONFIG_FILE", config), \
         patch("code_crew.repl.CONFIG_YAML", tmp_path / "config.yaml"), \
         patch("code_crew.repl.ensure_home"), \
         patch("code_crew.repl._read_project_profile", return_value=None):
        from code_crew.repl import _bootstrap
        _bootstrap()

    assert os.environ.get("SOME_GLOBAL_KEY") == "global_value"
    os.environ.pop("SOME_GLOBAL_KEY", None)


def test_bootstrap_loads_named_yaml_profile(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.write_text("")
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    profile_file = profiles_dir / "myprofile.yaml"
    profile_file.write_text("env:\n  PROFILE_KEY: from_profile\n")

    monkeypatch.setenv("CODE_CREW_PROFILE", "myprofile")
    monkeypatch.delenv("PROFILE_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    with patch("code_crew.repl.CONFIG_FILE", config), \
         patch("code_crew.repl.CONFIG_YAML", tmp_path / "config.yaml"), \
         patch("code_crew.repl.profile_path", return_value=profile_file), \
         patch("code_crew.repl.legacy_profile_path", return_value=profiles_dir / "myprofile.env"), \
         patch("code_crew.repl.ensure_home"), \
         patch("code_crew.repl._read_project_profile", return_value=None):
        from code_crew.repl import _bootstrap
        _bootstrap()

    assert os.environ.get("PROFILE_KEY") == "from_profile"
    os.environ.pop("PROFILE_KEY", None)
    os.environ.pop("CODE_CREW_PROFILE", None)


def test_bootstrap_falls_back_to_legacy_env(tmp_path, monkeypatch):
    """If no .yaml profile exists, falls back to .env with deprecation warning."""
    config = tmp_path / "config"
    config.write_text("")
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    legacy_file = profiles_dir / "oldprofile.env"
    legacy_file.write_text("LEGACY_KEY=from_legacy\n")

    monkeypatch.setenv("CODE_CREW_PROFILE", "oldprofile")
    monkeypatch.delenv("LEGACY_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    with patch("code_crew.repl.CONFIG_FILE", config), \
         patch("code_crew.repl.CONFIG_YAML", tmp_path / "config.yaml"), \
         patch("code_crew.repl.profile_path", return_value=profiles_dir / "oldprofile.yaml"), \
         patch("code_crew.repl.legacy_profile_path", return_value=legacy_file), \
         patch("code_crew.repl.ensure_home"), \
         patch("code_crew.repl._read_project_profile", return_value=None):
        from code_crew.repl import _bootstrap
        _bootstrap()

    assert os.environ.get("LEGACY_KEY") == "from_legacy"
    os.environ.pop("LEGACY_KEY", None)
    os.environ.pop("CODE_CREW_PROFILE", None)


def test_bootstrap_missing_profile_warns(tmp_path, monkeypatch, capsys):
    config = tmp_path / "config"
    config.write_text("")
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    monkeypatch.setenv("CODE_CREW_PROFILE", "missing")
    monkeypatch.chdir(tmp_path)

    with patch("code_crew.repl.CONFIG_FILE", config), \
         patch("code_crew.repl.CONFIG_YAML", tmp_path / "config.yaml"), \
         patch("code_crew.repl.profile_path", return_value=profiles_dir / "missing.yaml"), \
         patch("code_crew.repl.legacy_profile_path", return_value=profiles_dir / "missing.env"), \
         patch("code_crew.repl.ensure_home"), \
         patch("code_crew.repl._read_project_profile", return_value=None):
        from code_crew.repl import _bootstrap
        _bootstrap()

    captured = capsys.readouterr()
    assert "missing" in captured.err


# ---------------------------------------------------------------------------
# _switch_profile
# ---------------------------------------------------------------------------

def test_switch_profile_loads_yaml_vars(tmp_path, monkeypatch):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    yaml_file = profiles_dir / "client_a.yaml"
    yaml_file.write_text("env:\n  CLIENT_KEY: client_a_value\n")

    monkeypatch.delenv("CLIENT_KEY", raising=False)
    monkeypatch.delenv("CODE_CREW_PROFILE", raising=False)

    with patch("code_crew.repl.profile_path", return_value=yaml_file), \
         patch("code_crew.repl.legacy_profile_path", return_value=profiles_dir / "client_a.env"):
        from code_crew.repl import _switch_profile
        result = _switch_profile("client_a")

    assert result is True
    assert os.environ.get("CLIENT_KEY") == "client_a_value"
    assert os.environ.get("CODE_CREW_PROFILE") == "client_a"
    os.environ.pop("CLIENT_KEY", None)
    os.environ.pop("CODE_CREW_PROFILE", None)


def test_switch_profile_returns_false_for_missing(tmp_path):
    with patch("code_crew.repl.profile_path", return_value=tmp_path / "missing.yaml"), \
         patch("code_crew.repl.legacy_profile_path", return_value=tmp_path / "missing.env"):
        from code_crew.repl import _switch_profile
        result = _switch_profile("nonexistent")

    assert result is False


def test_switch_profile_clears_previous_profile_keys(tmp_path, monkeypatch):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    old_file = profiles_dir / "old.yaml"
    old_file.write_text("env:\n  OLD_KEY: old_value\n")
    new_file = profiles_dir / "new.yaml"
    new_file.write_text("env:\n  NEW_KEY: new_value\n")

    monkeypatch.setenv("CODE_CREW_PROFILE", "old")
    monkeypatch.setenv("OLD_KEY", "old_value")

    def _profile_path(name):
        return profiles_dir / f"{name}.yaml"

    def _legacy_path(name):
        return profiles_dir / f"{name}.env"

    with patch("code_crew.repl.profile_path", side_effect=_profile_path), \
         patch("code_crew.repl.legacy_profile_path", side_effect=_legacy_path):
        from code_crew.repl import _switch_profile
        _switch_profile("new")

    assert os.environ.get("OLD_KEY") is None
    assert os.environ.get("NEW_KEY") == "new_value"
    assert os.environ.get("CODE_CREW_PROFILE") == "new"
    os.environ.pop("NEW_KEY", None)
    os.environ.pop("CODE_CREW_PROFILE", None)


def test_switch_profile_falls_back_to_legacy_env(tmp_path, monkeypatch):
    """If no yaml profile exists, falls back to loading the legacy .env file."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    legacy_file = profiles_dir / "legacy.env"
    legacy_file.write_text("LEGACY_SWITCH_KEY=legacy_val\n")

    monkeypatch.delenv("LEGACY_SWITCH_KEY", raising=False)
    monkeypatch.delenv("CODE_CREW_PROFILE", raising=False)

    with patch("code_crew.repl.profile_path", return_value=profiles_dir / "legacy.yaml"), \
         patch("code_crew.repl.legacy_profile_path", return_value=legacy_file):
        from code_crew.repl import _switch_profile
        result = _switch_profile("legacy")

    assert result is True
    assert os.environ.get("LEGACY_SWITCH_KEY") == "legacy_val"
    os.environ.pop("LEGACY_SWITCH_KEY", None)
    os.environ.pop("CODE_CREW_PROFILE", None)


# ---------------------------------------------------------------------------
# _read_project_profile
# ---------------------------------------------------------------------------

def test_read_project_profile_from_yaml(tmp_path, monkeypatch):
    (tmp_path / ".code-crew.yaml").write_text("profile: staging\nproject: myapp\n")
    monkeypatch.chdir(tmp_path)

    import code_crew.repl as repl_mod
    assert repl_mod._read_project_profile() == "staging"


def test_read_project_profile_returns_none_when_no_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    import code_crew.repl as repl_mod
    assert repl_mod._read_project_profile() is None
