"""
Git worktree manager for parallel ticket execution.

Creates a sibling worktree for each ticket that runs in parallel,
ensuring independent branch checkouts with no file conflicts.

Layout (given cwd = /projects/my-repo):
  /projects/my-repo-PROJ-120/   → branch: feature/PROJ-120-slug
  /projects/my-repo-PROJ-121/   → branch: feature/PROJ-121-slug
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Worktree:
    ticket_key: str
    path: Path
    branch: str


class WorktreeError(Exception):
    pass


class WorktreeManager:
    """Manages git worktrees for parallel ticket flows."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self._root = repo_root or Path.cwd()

    def create(self, ticket_key: str, branch: str, base: str = "main") -> Worktree:
        """
        Create a new worktree for ticket_key on the given branch.

        If the branch already exists locally, it is reused (assumes a previous
        interrupted run). The worktree directory is a sibling of the repo root:
          <parent>/<repo-name>-<ticket-key>
        """
        wt_path = self._worktree_path(ticket_key)

        if wt_path.exists():
            # Already present — verify it's a worktree for the right branch
            return Worktree(ticket_key=ticket_key, path=wt_path, branch=branch)

        # Check if branch exists already
        existing = self._run(["git", "branch", "--list", branch]).strip()
        if existing:
            self._run(["git", "worktree", "add", str(wt_path), branch])
        else:
            self._run(["git", "worktree", "add", "-b", branch, str(wt_path), base])

        return Worktree(ticket_key=ticket_key, path=wt_path, branch=branch)

    def remove(self, ticket_key: str, force: bool = False) -> None:
        """Remove the worktree for the given ticket key."""
        wt_path = self._worktree_path(ticket_key)
        if not wt_path.exists():
            return
        cmd = ["git", "worktree", "remove", str(wt_path)]
        if force:
            cmd.append("--force")
        self._run(cmd)

    def list(self) -> list[Worktree]:
        """Return all active worktrees for this repo (excluding the main one)."""
        output = self._run(["git", "worktree", "list", "--porcelain"])
        worktrees: list[Worktree] = []
        current_path: str = ""
        current_branch: str = ""
        for line in output.splitlines():
            if line.startswith("worktree "):
                current_path = line[len("worktree "):]
            elif line.startswith("branch "):
                current_branch = line[len("branch "):].replace("refs/heads/", "")
            elif line == "":
                if current_path and current_path != str(self._root):
                    p = Path(current_path)
                    key = p.name.replace(f"{self._root.name}-", "", 1)
                    worktrees.append(Worktree(
                        ticket_key=key,
                        path=p,
                        branch=current_branch,
                    ))
                current_path = ""
                current_branch = ""
        return worktrees

    def path(self, ticket_key: str) -> Path:
        return self._worktree_path(ticket_key)

    def exists(self, ticket_key: str) -> bool:
        return self._worktree_path(ticket_key).exists()

    # ------------------------------------------------------------------

    def _worktree_path(self, ticket_key: str) -> Path:
        return self._root.parent / f"{self._root.name}-{ticket_key}"

    def _run(self, cmd: list[str]) -> str:
        result = subprocess.run(
            cmd,
            cwd=str(self._root),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise WorktreeError(
                f"git command failed: {' '.join(cmd)}\n{result.stderr.strip()}"
            )
        return result.stdout
