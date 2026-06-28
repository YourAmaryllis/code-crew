"""
CrewAI tool: read files from the current project workspace (cwd).

Three operations — read_file, list_dir, search — load only what the agent
asks for, keeping context small. No external config required.
"""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


def _code_path() -> Path:
    return Path.cwd()


class WorkspaceReadInput(BaseModel):
    operation: str = Field(
        default="",
        description=(
            "Operation to perform. One of:\n"
            "  read_file   — return the contents of a file\n"
            "  list_dir    — list files/dirs in a directory (depth-limited)\n"
            "  find_files  — find files by name/glob pattern (e.g. '**/*_handler.go')\n"
            "  search      — grep for a pattern across the workspace"
        )
    )
    path: str = Field(
        default="",
        description=(
            "Path relative to the project root. Required for read_file and list_dir. "
            "Leave empty for list_dir to list the root."
        ),
    )
    pattern: str = Field(
        default="",
        description="Search pattern (regex) for the search operation.",
    )
    glob: str = Field(
        default="**/*",
        description="Glob to restrict search to specific file types, e.g. '**/*.go' or '**/*.ts'.",
    )
    depth: int = Field(
        default=3,
        description="Max directory depth for list_dir (default 3).",
    )


class WorkspaceReaderTool(BaseTool):
    name: str = "workspace_reader"
    description: str = (
        "Read files, list directories, find files by name, or search the current project workspace. "
        "Use find_files to locate files by name/glob (e.g. '**/*_handler.go') before reading them. "
        "Use search to find where a pattern appears in file contents. "
        "Use read_file to inspect a specific file. Use list_dir to see the top-level layout."
    )
    args_schema: type[BaseModel] = WorkspaceReadInput

    def _run(
        self,
        operation: str,
        path: str = "",
        pattern: str = "",
        glob: str = "**/*",
        depth: int = 3,
    ) -> str:
        if not operation:
            return "ERROR: 'operation' is required. Use: read_file, list_dir, find_files, search."
        root = _code_path()
        if operation == "read_file":
            return self._read_file(root, path)
        if operation == "list_dir":
            return self._list_dir(root, path, depth)
        if operation == "find_files":
            return self._find_files(root, path, glob)
        if operation == "search":
            return self._search(root, pattern, glob)
        return f"Unknown operation '{operation}'. Use: read_file, list_dir, find_files, search."

    # ------------------------------------------------------------------

    def _read_file(self, root: Path, rel_path: str) -> str:
        if not rel_path:
            return "ERROR: path is required for read_file"
        target = (root / rel_path).resolve()
        if not str(target).startswith(str(root)):
            return "ERROR: path escapes project root"
        if not target.exists():
            return f"ERROR: file not found: {rel_path}"
        if target.is_dir():
            return f"ERROR: {rel_path} is a directory — use list_dir"
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"ERROR: {exc}"
        lines = text.splitlines()
        if len(lines) > 200:
            text = "\n".join(lines[:200]) + f"\n… ({len(lines) - 200} more lines truncated)"
        return text or "(empty file)"

    def _list_dir(self, root: Path, rel_path: str, depth: int) -> str:
        base = (root / rel_path).resolve() if rel_path else root
        if not str(base).startswith(str(root)):
            return "ERROR: path escapes project root"
        if not base.exists():
            return f"ERROR: directory not found: {rel_path or '.'}"
        if not base.is_dir():
            return f"ERROR: {rel_path} is a file — use read_file"
        lines: list[str] = []
        self._walk(base, base, depth, 0, lines)
        return "\n".join(lines) or "(empty directory)"

    def _walk(self, base: Path, current: Path, max_depth: int, cur_depth: int, lines: list[str]) -> None:
        if cur_depth > max_depth:
            lines.append(f"{'  ' * cur_depth}…")
            return
        try:
            entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return
        for entry in entries:
            if entry.name.startswith(".") and entry.name not in {".env.example", ".github"}:
                continue
            indent = "  " * cur_depth
            if entry.is_dir():
                lines.append(f"{indent}{entry.name}/")
                self._walk(base, entry, max_depth, cur_depth + 1, lines)
            else:
                lines.append(f"{indent}{entry.name}")

    def _find_files(self, root: Path, rel_path: str, glob: str) -> str:
        base = (root / rel_path).resolve() if rel_path else root
        if not str(base).startswith(str(root)):
            return "ERROR: path escapes project root"
        if not base.exists():
            return f"ERROR: directory not found: {rel_path or '.'}"
        g = glob if glob != "**/*" else "**/*"
        matches = sorted(p for p in base.glob(g) if p.is_file())
        # Exclude common noise dirs
        matches = [
            p for p in matches
            if not any(part in {".git", "vendor", "node_modules", "__pycache__", ".terraform"}
                       for part in p.parts)
        ]
        if not matches:
            return f"No files matching '{glob}' in {rel_path or '.'}"
        lines = [str(p.relative_to(root)) for p in matches[:100]]
        suffix = f"\n… ({len(matches) - 100} more)" if len(matches) > 100 else ""
        return "\n".join(lines) + suffix

    def _search(self, root: Path, pattern: str, glob: str) -> str:
        if not pattern:
            return "ERROR: pattern is required for search"
        try:
            result = subprocess.run(
                ["grep", "-rn", "--include", self._glob_to_include(glob), pattern, str(root)],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return "ERROR: search timed out"
        except FileNotFoundError:
            return "ERROR: grep not available"
        output = result.stdout.strip()
        if not output:
            return f"No matches for '{pattern}' in {glob}"
        lines = output.splitlines()
        # Make paths relative to root
        rel_lines = []
        for line in lines[:50]:
            if line.startswith(str(root)):
                line = line[len(str(root)):].lstrip("/")
            rel_lines.append(line)
        suffix = f"\n… ({len(lines) - 50} more matches truncated)" if len(lines) > 50 else ""
        return "\n".join(rel_lines) + suffix

    @staticmethod
    def _glob_to_include(glob: str) -> str:
        """Convert glob like '**/*.go' to grep --include pattern '*.go'."""
        parts = glob.replace("**/", "").split("/")
        return parts[-1] if parts else "*"
