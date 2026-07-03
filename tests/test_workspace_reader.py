"""Tests for shared.tools.workspace_reader.WorkspaceReaderTool."""

from pathlib import Path
from unittest.mock import patch

import pytest

from shared.tools.workspace_reader import WorkspaceReaderTool


@pytest.fixture()
def workspace(tmp_path):
    """A temp directory with a few files simulating a project."""
    (tmp_path / "main.go").write_text("package main\n\nfunc main() {}\n")
    sub = tmp_path / "internal" / "repo"
    sub.mkdir(parents=True)
    (sub / "user_repo.go").write_text("package repo\n\ntype UserRepo interface{}\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".env").write_text("SECRET=abc")
    return tmp_path


@pytest.fixture()
def tool(workspace):
    t = WorkspaceReaderTool()
    with patch("shared.tools.workspace_reader._code_path", return_value=workspace):
        yield t, workspace


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

def test_read_file_ok(tool):
    t, ws = tool
    with patch("shared.tools.workspace_reader._code_path", return_value=ws):
        result = t._run(operation="read_file", path="main.go")
    assert "package main" in result


def test_read_file_not_found(tool):
    t, ws = tool
    with patch("shared.tools.workspace_reader._code_path", return_value=ws):
        result = t._run(operation="read_file", path="missing.go")
    assert "ERROR" in result


def test_read_file_no_path(tool):
    t, ws = tool
    with patch("shared.tools.workspace_reader._code_path", return_value=ws):
        result = t._run(operation="read_file", path="")
    assert "ERROR" in result


def test_read_file_escape_rejected(tool):
    t, ws = tool
    with patch("shared.tools.workspace_reader._code_path", return_value=ws):
        result = t._run(operation="read_file", path="../../etc/passwd")
    assert "ERROR" in result


def test_read_file_directory(tool):
    t, ws = tool
    with patch("shared.tools.workspace_reader._code_path", return_value=ws):
        result = t._run(operation="read_file", path="internal")
    assert "ERROR" in result


# ---------------------------------------------------------------------------
# list_dir
# ---------------------------------------------------------------------------

def test_list_dir_root(tool):
    t, ws = tool
    with patch("shared.tools.workspace_reader._code_path", return_value=ws):
        result = t._run(operation="list_dir")
    assert "main.go" in result
    assert "internal/" in result


def test_list_dir_subdir(tool):
    t, ws = tool
    with patch("shared.tools.workspace_reader._code_path", return_value=ws):
        result = t._run(operation="list_dir", path="internal/repo")
    assert "user_repo.go" in result


def test_list_dir_hidden_git_excluded(tool):
    t, ws = tool
    with patch("shared.tools.workspace_reader._code_path", return_value=ws):
        result = t._run(operation="list_dir")
    assert ".git" not in result


def test_list_dir_missing(tool):
    t, ws = tool
    with patch("shared.tools.workspace_reader._code_path", return_value=ws):
        result = t._run(operation="list_dir", path="nonexistent")
    assert "ERROR" in result


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def test_search_finds_pattern(tool):
    t, ws = tool
    with patch("shared.tools.workspace_reader._code_path", return_value=ws):
        result = t._run(operation="search", pattern="UserRepo", glob="**/*.go")
    assert "user_repo.go" in result
    assert "UserRepo" in result


def test_search_no_matches(tool):
    t, ws = tool
    with patch("shared.tools.workspace_reader._code_path", return_value=ws):
        result = t._run(operation="search", pattern="XYZ_NOT_HERE", glob="**/*.go")
    assert "No matches" in result


def test_search_no_pattern(tool):
    t, ws = tool
    with patch("shared.tools.workspace_reader._code_path", return_value=ws):
        result = t._run(operation="search", pattern="")
    assert "ERROR" in result


# ---------------------------------------------------------------------------
# unknown operation
# ---------------------------------------------------------------------------

def test_unknown_operation(tool):
    t, ws = tool
    with patch("shared.tools.workspace_reader._code_path", return_value=ws):
        result = t._run(operation="delete_everything")
    assert "Unknown operation" in result


# ---------------------------------------------------------------------------
# truncation limits
# ---------------------------------------------------------------------------

def test_read_file_truncates_at_200_lines(workspace):
    big = workspace / "big.go"
    big.write_text("\n".join(f"// line {i}" for i in range(300)))
    t = WorkspaceReaderTool()
    with patch("shared.tools.workspace_reader._code_path", return_value=workspace):
        result = t._run(operation="read_file", path="big.go")
    assert "100 more lines truncated" in result
    assert result.count("// line") == 200


def test_search_truncates_at_max_files(workspace):
    # 20 Go files each matching the pattern; result is capped at _MAX_FILES_IN_RESULT files
    from shared.tools.workspace_reader import _MAX_FILES_IN_RESULT
    src = workspace / "src"
    src.mkdir()
    for i in range(20):
        (src / f"f{i}.go").write_text("package src\n// FINDME\n")
    t = WorkspaceReaderTool()
    with patch("shared.tools.workspace_reader._code_path", return_value=workspace):
        result = t._run(operation="search", pattern="FINDME", glob="**/*.go")
    # Should show truncation notice and exactly _MAX_FILES_IN_RESULT file sections
    assert "more files matched" in result
    assert result.count("=== ") == _MAX_FILES_IN_RESULT
