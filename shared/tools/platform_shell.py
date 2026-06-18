"""
CrewAI tool: run shell commands in the current project directory (cwd).

Safe-listed command prefixes only. Always executes in the project root
(Path.cwd()) unless overridden via code_path on the tool instance.
Used by engineer agents for git, go, aws (readonly), and issue tracker CLI operations.
"""

import subprocess
from pathlib import Path

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# Commands allowed to run. Prefix match — "git " allows all git subcommands.
_ALLOWED_PREFIXES = (
    "git ",
    "go test",
    "go build",
    "go vet",
    "go fmt",
    "gofmt",
    "go run",
    "pytest",
    "python3 ",
    "python ",
    "npm test",
    "npm run",
    "npx ",
    "aws sts get-caller-identity",
    "aws ecs describe",
    "aws ecs list",
    "aws s3 ls",
    "aws cloudwatch",
    "aws logs",
    "jira view",
    "jira list",
    "jira issue",
    "linear issue",
    "pre-commit",
    "make ",
    "ls ",
    "find ",
    "cat ",
    "grep ",
    "echo ",
)

_BLOCKED_PATTERNS = (
    "rm -rf",
    "sudo ",
    "chmod 777",
    "> /dev/",
    "dd if=",
    "mkfs",
    ":(){:|:&};:",
)


def _is_allowed(command: str) -> tuple[bool, str]:
    for blocked in _BLOCKED_PATTERNS:
        if blocked in command:
            return False, f"Blocked pattern '{blocked}' detected."
    normalized = command.lstrip()
    for prefix in _ALLOWED_PREFIXES:
        if normalized.startswith(prefix):
            return True, ""
    return False, (
        f"Command not in allowlist. Allowed prefixes: {', '.join(_ALLOWED_PREFIXES[:10])}…"
    )


class PlatformShellInput(BaseModel):
    command: str = Field(
        description=(
            "Shell command to run in the project directory. "
            "Allowed: git, go test/build/vet/fmt, pytest, python3, npm, "
            "aws (readonly: describe/list/logs), jira/linear issue commands, "
            "grep, find, ls. No destructive operations."
        )
    )
    working_dir: str = Field(
        default="",
        description=(
            "Subdirectory relative to the project root to run the command in. "
            "Example: 'integration' to run tests in the integration/ subdirectory. "
            "Leave empty to run in the project root."
        ),
    )


class PlatformShellTool(BaseTool):
    name: str = "platform_shell"
    description: str = (
        "Run git, go, aws (readonly), jira/linear, or test commands in the project repo. "
        "Use for: creating branches (git checkout -b), running unit tests (go test ./...), "
        "running BDD tests, checking git status/diff, "
        "and other safe read/write operations in the codebase."
    )
    args_schema: type[BaseModel] = PlatformShellInput
    code_path: str = ""  # set by Flow per worktree; empty = use cwd

    def _root(self) -> Path:
        return Path(self.code_path).resolve() if self.code_path else Path.cwd()

    def _run(self, command: str, working_dir: str = "") -> str:
        allowed, reason = _is_allowed(command)
        if not allowed:
            return f"BLOCKED: {reason}"

        cwd = self._root()
        if working_dir:
            cwd = cwd / working_dir
        if not cwd.exists():
            return f"ERROR: directory does not exist: {cwd}"

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout
            if result.stderr:
                output += f"\n--- stderr ---\n{result.stderr}"
            if result.returncode != 0:
                output = f"Exit code {result.returncode}\n{output}"
            return output.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return "ERROR: command timed out after 120 seconds"
        except Exception as e:
            return f"ERROR: {e}"
