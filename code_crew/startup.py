"""
Startup checks: git repo, required CLIs, stack detection.

Reads stack OKFs from DESIGNS_PATH to know which CLIs are required
for the detected stacks. Prints a status banner and returns a summary.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    fix: str = ""


@dataclass
class StartupSummary:
    git_ok: bool
    git_branch: str
    detected_stacks: list[str]
    checks: list[CheckResult]
    warnings: int
    errors: int

    @property
    def ok(self) -> bool:
        return self.errors == 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_checks(code_path: Path | None = None) -> StartupSummary:
    """Run all startup checks and return a summary (does not print)."""
    root = code_path or Path.cwd()
    checks: list[CheckResult] = []

    git_ok, git_branch = _check_git(root)
    checks.append(CheckResult(
        name="git repo",
        ok=git_ok,
        detail=git_branch if git_ok else "not a git repository",
        fix="" if git_ok else "Run /init to scaffold a new project",
    ))

    stacks = detect_stacks(root)
    required_clis = _required_clis_for_stacks(stacks)

    # Always require gh
    required_clis.setdefault("gh", "brew install gh  # then: gh auth login")

    for cli, install_hint in sorted(required_clis.items()):
        found = shutil.which(cli) is not None
        checks.append(CheckResult(
            name=cli,
            ok=found,
            detail=shutil.which(cli) or "",
            fix=install_hint if not found else "",
        ))

    warnings = sum(1 for c in checks if not c.ok and c.name != "git repo")
    errors = sum(1 for c in checks if not c.ok and c.name == "git repo")

    return StartupSummary(
        git_ok=git_ok,
        git_branch=git_branch,
        detected_stacks=stacks,
        checks=checks,
        warnings=warnings,
        errors=errors,
    )


def detect_stacks(root: Path | None = None) -> list[str]:
    """Return list of stack names detected from project files in root."""
    root = root or Path.cwd()
    detected: list[str] = []
    if (root / "go.mod").exists():
        detected.append("go-backend")
    if (root / "package.json").exists():
        detected.append("typescript-react")
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists():
        detected.append("python")
    tf_files = list(root.glob("*.tf")) + list((root / "terraform").glob("*.tf") if (root / "terraform").is_dir() else [])
    if tf_files:
        detected.append("terraform-aws")
    return detected


# ---------------------------------------------------------------------------
# Git check
# ---------------------------------------------------------------------------

def _check_git(root: Path) -> tuple[bool, str]:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, ""
    branch = result.stdout.strip()
    # Also get clean/dirty status
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(root), capture_output=True, text=True,
    )
    dirty = " (dirty)" if status.stdout.strip() else ""
    return True, f"{branch}{dirty}"


# ---------------------------------------------------------------------------
# Stack OKF → required CLIs
# ---------------------------------------------------------------------------

def _required_clis_for_stacks(stacks: list[str]) -> dict[str, str]:
    """Load stack OKFs and collect required-cli entries. Returns {cli: install_hint}."""
    designs_path = _designs_path()
    if not designs_path:
        return {}

    stacks_dir = designs_path / "SDLC" / "stacks"
    if not stacks_dir.exists():
        return {}

    install_hints = _cli_install_hints()
    result: dict[str, str] = {}

    for stack_name in stacks:
        okf_path = stacks_dir / f"{stack_name}.md"
        if not okf_path.exists():
            continue
        try:
            text = okf_path.read_text(encoding="utf-8")
            if not text.startswith("---"):
                continue
            end = text.index("---", 3)
            fm = yaml.safe_load(text[3:end]) or {}
            metadata = fm.get("metadata", {})
            for cli in metadata.get("required-cli", []):
                result[cli] = install_hints.get(cli, f"install {cli}")
        except Exception:
            continue

    return result


def _designs_path() -> Path | None:
    raw = os.environ.get("DESIGNS_PATH", "")
    if raw:
        p = Path(raw).expanduser()
        return p if p.exists() else None
    # Fall back to sibling designs/ relative to this file's package root
    candidate = Path(__file__).parent.parent / "designs"
    return candidate if candidate.exists() else None


def _cli_install_hints() -> dict[str, str]:
    return {
        "gh": "brew install gh && gh auth login",
        "go": "brew install go",
        "golangci-lint": "brew install golangci-lint",
        "godog": "go install github.com/cucumber/godog/cmd/godog@latest",
        "node": "brew install node",
        "npm": "brew install node",
        "npx": "brew install node",
        "python3": "brew install python",
        "ruff": "pip install ruff",
        "terraform": "brew install terraform",
        "tfsec": "brew install tfsec",
        "checkov": "pip install checkov",
        "aws": "brew install awscli",
        "pre-commit": "pip install pre-commit",
        "linear": "npm i -g @linear/linear && linear auth login",
        "jira": "brew install jira-cli",
    }
