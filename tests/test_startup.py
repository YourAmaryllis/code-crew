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
    # gh is always required; with no shutil.which it should fail
    missing = [c for c in summary.checks if not c.ok and c.name == "gh"]
    assert missing
