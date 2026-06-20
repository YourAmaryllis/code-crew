"""Tests for code_crew.startup: git check, stack detection, CLI checks."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from code_crew.startup import detect_stacks, run_checks, _check_git


# ---------------------------------------------------------------------------
# detect_stacks
# ---------------------------------------------------------------------------

def test_detect_go_backend(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/myapp\n\ngo 1.23\n")
    assert "go-backend" in detect_stacks(tmp_path)


def test_detect_typescript_react(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "myapp"}')
    assert "typescript-react" in detect_stacks(tmp_path)


def test_detect_python(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'myapp'\n")
    assert "python" in detect_stacks(tmp_path)


def test_detect_python_setup_py(tmp_path):
    (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup(name='myapp')\n")
    assert "python" in detect_stacks(tmp_path)


def test_detect_terraform(tmp_path):
    (tmp_path / "main.tf").write_text('provider "aws" {}\n')
    assert "terraform-aws" in detect_stacks(tmp_path)


def test_detect_multiple(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/app\n\ngo 1.23\n")
    (tmp_path / "main.tf").write_text('provider "aws" {}\n')
    stacks = detect_stacks(tmp_path)
    assert "go-backend" in stacks
    assert "terraform-aws" in stacks


def test_detect_empty(tmp_path):
    assert detect_stacks(tmp_path) == []


# ---------------------------------------------------------------------------
# detect_stacks — .code-crew.yaml override
# ---------------------------------------------------------------------------

def test_env_var_stacks_override_yaml_and_auto(tmp_path, monkeypatch):
    # Even with yaml and go.mod present, env var wins
    (tmp_path / "go.mod").write_text("module example.com/foo\n")
    (tmp_path / ".code-crew.yaml").write_text("stacks:\n  - python\n")
    monkeypatch.setenv("CODE_CREW_STACKS", "terraform-aws,typescript-react")
    assert detect_stacks(tmp_path) == ["terraform-aws", "typescript-react"]


def test_env_var_stacks_strips_whitespace(tmp_path, monkeypatch):
    monkeypatch.setenv("CODE_CREW_STACKS", " python , typescript-react ")
    assert detect_stacks(tmp_path) == ["python", "typescript-react"]


def test_empty_env_var_falls_through(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    monkeypatch.setenv("CODE_CREW_STACKS", "")
    assert detect_stacks(tmp_path) == ["python"]


def test_yaml_stacks_override_auto_detection(tmp_path):
    # Even though go.mod exists, yaml stacks take precedence
    (tmp_path / "go.mod").write_text("module example.com/foo\n")
    (tmp_path / ".code-crew.yaml").write_text("stacks:\n  - python\n  - terraform-aws\n")
    assert detect_stacks(tmp_path) == ["python", "terraform-aws"]


def test_yaml_stacks_empty_list_falls_back_to_auto(tmp_path):
    # Empty stacks: [] in yaml → fall back to file detection
    (tmp_path / "go.mod").write_text("module example.com/foo\n")
    (tmp_path / ".code-crew.yaml").write_text("stacks: []\n")
    assert "go-backend" in detect_stacks(tmp_path)


def test_yaml_without_stacks_key_falls_back_to_auto(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    (tmp_path / ".code-crew.yaml").write_text("profile: dev\n")
    assert detect_stacks(tmp_path) == ["python"]


def test_yaml_stacks_invalid_yaml_falls_back_to_auto(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    (tmp_path / ".code-crew.yaml").write_text("stacks: [\nbad yaml{{{\n")
    # Should not raise; falls back to auto-detection
    result = detect_stacks(tmp_path)
    assert "python" in result


# ---------------------------------------------------------------------------
# _check_git
# ---------------------------------------------------------------------------

def test_check_git_ok(tmp_path):
    import subprocess
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"],
                   cwd=str(tmp_path), capture_output=True,
                   env={**__import__("os").environ, "GIT_AUTHOR_NAME": "T",
                        "GIT_AUTHOR_EMAIL": "t@t.com", "GIT_COMMITTER_NAME": "T",
                        "GIT_COMMITTER_EMAIL": "t@t.com"})
    ok, branch = _check_git(tmp_path)
    assert ok
    assert branch  # "main" or "master"


def test_check_git_not_a_repo(tmp_path):
    ok, branch = _check_git(tmp_path)
    assert not ok
    assert branch == ""


# ---------------------------------------------------------------------------
# run_checks
# ---------------------------------------------------------------------------

def test_run_checks_git_error(tmp_path):
    summary = run_checks(code_path=tmp_path)
    assert not summary.git_ok
    assert summary.errors >= 1


def test_run_checks_git_ok(tmp_path):
    import subprocess, os
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"],
                   cwd=str(tmp_path), capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "T",
                        "GIT_AUTHOR_EMAIL": "t@t.com", "GIT_COMMITTER_NAME": "T",
                        "GIT_COMMITTER_EMAIL": "t@t.com"})
    with patch("code_crew.startup._designs_path", return_value=None):
        summary = run_checks(code_path=tmp_path)
    assert summary.git_ok
    assert summary.errors == 0


def test_run_checks_missing_cli(tmp_path):
    import subprocess, os
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"],
                   cwd=str(tmp_path), capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "T",
                        "GIT_AUTHOR_EMAIL": "t@t.com", "GIT_COMMITTER_NAME": "T",
                        "GIT_COMMITTER_EMAIL": "t@t.com"})
    with patch("code_crew.startup._designs_path", return_value=None):
        with patch("shutil.which", return_value=None):
            summary = run_checks(code_path=tmp_path)
    # gh and aws are always required; with no shutil.which they should both fail
    always_required = {"gh", "aws"}
    missing_names = {c.name for c in summary.checks if not c.ok}
    assert always_required.issubset(missing_names)
