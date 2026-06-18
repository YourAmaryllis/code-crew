"""Tests for code_crew.worktree.WorktreeManager."""

import subprocess
import os
from pathlib import Path

import pytest

from code_crew.worktree import WorktreeManager, WorktreeError


@pytest.fixture()
def git_repo(tmp_path):
    """A real git repo with one commit, usable for worktree operations."""
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@test.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@test.com",
    }
    subprocess.run(["git", "init", "-b", "main"], cwd=str(tmp_path), capture_output=True, env=env)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"],
                   cwd=str(tmp_path), capture_output=True, env=env)
    return tmp_path


def test_create_worktree(git_repo):
    wm = WorktreeManager(git_repo)
    wt = wm.create("PROJ-1", "feature/proj-1-test")
    assert wt.path.exists()
    assert wt.ticket_key == "PROJ-1"
    assert "proj-1" in wt.branch


def test_create_idempotent(git_repo):
    wm = WorktreeManager(git_repo)
    wt1 = wm.create("PROJ-2", "feature/proj-2-test")
    wt2 = wm.create("PROJ-2", "feature/proj-2-test")
    assert wt1.path == wt2.path


def test_worktree_path(git_repo):
    wm = WorktreeManager(git_repo)
    expected = git_repo.parent / f"{git_repo.name}-PROJ-3"
    assert wm.path("PROJ-3") == expected


def test_exists_false_before_create(git_repo):
    wm = WorktreeManager(git_repo)
    assert not wm.exists("PROJ-99")


def test_exists_true_after_create(git_repo):
    wm = WorktreeManager(git_repo)
    wm.create("PROJ-4", "feature/proj-4-test")
    assert wm.exists("PROJ-4")


def test_remove_worktree(git_repo):
    wm = WorktreeManager(git_repo)
    wm.create("PROJ-5", "feature/proj-5-test")
    assert wm.exists("PROJ-5")
    wm.remove("PROJ-5")
    assert not wm.exists("PROJ-5")


def test_remove_nonexistent_is_noop(git_repo):
    wm = WorktreeManager(git_repo)
    wm.remove("PROJ-NONE")  # should not raise


def test_list_returns_created(git_repo):
    wm = WorktreeManager(git_repo)
    wm.create("PROJ-6", "feature/proj-6-test")
    listed = wm.list()
    keys = [w.ticket_key for w in listed]
    assert "PROJ-6" in keys


def test_run_raises_on_bad_repo(tmp_path):
    wm = WorktreeManager(tmp_path)
    with pytest.raises(WorktreeError):
        wm.create("PROJ-X", "feature/proj-x-test")
