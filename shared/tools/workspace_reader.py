"""
CrewAI tool: read files from the current project workspace (cwd).

Four operations — read_file, list_dir, find_files, search — load only what the
agent asks for, keeping context small. No external config required.

search returns grouped results with context lines so agents can understand
matches without reading the whole file.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

_NOISE_DIRS = {".git", "vendor", "node_modules", "__pycache__", ".terraform"}
_MAX_FILES_IN_RESULT = 8   # max distinct files returned by search
_CONTEXT_LINES = 3         # lines of context around each match


def _code_path() -> Path:
    return Path.cwd()


class WorkspaceReadInput(BaseModel):
    operation: str = Field(
        default="",
        description=(
            "Operation to perform. One of:\n"
            "  read_file   — return the contents of a file (up to 200 lines)\n"
            "  list_dir    — list files/dirs in a directory (depth-limited)\n"
            "  find_files  — find files by name/glob pattern (e.g. '**/*_handler.go')\n"
            "  search      — search for a pattern; returns grouped matches WITH context lines\n"
            "                so you can understand matches without reading the whole file\n"
            "  search_ast  — structural AST search via ast-grep; finds code by shape not just text\n"
            "                e.g. pattern='$FUNC($$$ARGS)' lang='go' finds all function calls"
        )
    )
    path: str = Field(
        default="",
        description=(
            "Path relative to the project root. Required for read_file and list_dir. "
            "For search/search_ast, limits the search to this subdirectory. "
            "Leave empty to search/list the project root."
        ),
    )
    pattern: str = Field(
        default="",
        description=(
            "Search pattern for the search operation. "
            "Use alternation for variants: 'fhir.proxy|fhir_proxy|fhir/proxy' "
            "searches all three in one call instead of three separate calls.\n"
            "For search_ast: an ast-grep structural pattern, e.g. 'os.Getenv($KEY)' or "
            "'func $NAME($$$) error'."
        ),
    )
    glob: str = Field(
        default="**/*",
        description="Glob to restrict search to specific file types, e.g. '**/*.go' or '**/*.tf'.",
    )
    depth: int = Field(
        default=3,
        description="Max directory depth for list_dir (default 3).",
    )
    language: str = Field(
        default="",
        description=(
            "Language for search_ast (required). "
            "Common values: go, python, typescript, javascript, rust, java, kotlin, c, cpp."
        ),
    )


class WorkspaceReaderTool(BaseTool):
    name: str = "workspace_reader"
    description: str = (
        "Read files, list directories, find files by name, or search the current project workspace.\n"
        "search returns matches WITH context lines — understand code without reading the whole file.\n"
        "search supports alternation: use 'fhir.proxy|fhir_proxy|fhir/proxy' to try multiple name "
        "variants in one call. Results are grouped by file, capped at 8 files.\n"
        "search_ast does structural AST search via ast-grep — finds code by shape, not just text. "
        "Requires ast-grep installed (brew install ast-grep). Specify 'language' parameter.\n"
        "Use read_file to inspect a specific file. Use list_dir for directory layout."
    )
    args_schema: type[BaseModel] = WorkspaceReadInput

    def _run(
        self,
        operation: str,
        path: str = "",
        pattern: str = "",
        glob: str = "**/*",
        depth: int = 3,
        language: str = "",
    ) -> str:
        if not operation:
            return "ERROR: 'operation' is required. Use: read_file, list_dir, find_files, search, search_ast."
        root = _code_path()
        if operation == "read_file":
            return self._read_file(root, path)
        if operation == "list_dir":
            return self._list_dir(root, path, depth)
        if operation == "find_files":
            return self._find_files(root, path, glob)
        if operation == "search":
            return self._search(root, pattern, path, glob)
        if operation == "search_ast":
            return self._search_ast(root, pattern, language, path)
        return f"Unknown operation '{operation}'. Use: read_file, list_dir, find_files, search, search_ast."

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
        matches = sorted(p for p in base.glob(glob) if p.is_file())
        matches = [p for p in matches if not any(part in _NOISE_DIRS for part in p.parts)]
        if not matches:
            return f"No files matching '{glob}' in {rel_path or '.'}"
        lines = [str(p.relative_to(root)) for p in matches[:100]]
        suffix = f"\n… ({len(matches) - 100} more)" if len(matches) > 100 else ""
        return "\n".join(lines) + suffix

    def _search(self, root: Path, pattern: str, rel_path: str, glob: str) -> str:
        """Search with context lines, grouped by file.

        Returns up to _MAX_FILES_IN_RESULT files, each showing matched lines with
        _CONTEXT_LINES lines of surrounding code so the agent can understand the
        match without a separate read_file call.
        """
        if not pattern:
            return "ERROR: pattern is required for search"

        search_root = (root / rel_path).resolve() if rel_path else root
        if not str(search_root).startswith(str(root)):
            return "ERROR: path escapes project root"
        if not search_root.exists():
            return f"ERROR: directory not found: {rel_path or '.'}"

        include = self._glob_to_include(glob)
        try:
            # BSD grep uses "--" as default context group separator (no --group-separator flag).
            # -E for extended regex (supports alternation: foo|bar|baz).
            result = subprocess.run(
                ["grep", "-rn", "-E", f"--include={include}", f"-C", str(_CONTEXT_LINES),
                 pattern, str(search_root)],
                capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            return "ERROR: search timed out"
        except FileNotFoundError:
            return "ERROR: grep not available"

        raw = result.stdout.strip()
        if not raw:
            return (
                f"No matches for '{pattern}' in {rel_path or '.'}. "
                "Try alternation for name variants: 'service_name|service-name|service/name'."
            )

        # Parse BSD grep -C output.
        # Match lines:   "/abs/path/file.go:42:text"  (colon separators)
        # Context lines: "/abs/path/file.go-42-text"  (hyphen separators)
        # Group boundary: "--" alone on a line
        # Paths themselves can contain hyphens (app-infra), so use regex anchored on :\d+: / -\d+-
        root_str = str(root) + "/"
        _LINE_RE = re.compile(r"^(.+?)([:\-])(\d+)\2(.*)$")
        by_file: dict[str, list[str]] = {}
        current_group: list[str] = []
        current_file: str = ""

        def _flush() -> None:
            if current_file and current_group:
                if not any(part in _NOISE_DIRS for part in Path(current_file).parts):
                    by_file.setdefault(current_file, []).extend(current_group)
                    by_file[current_file].append("")  # blank between groups

        for line in raw.splitlines():
            if line == "--":
                _flush()
                current_group = []
                current_file = ""
                continue
            rel_line = line.replace(root_str, "")
            m = _LINE_RE.match(rel_line)
            if m:
                file_part = m.group(1)
                if file_part:
                    current_file = file_part
            current_group.append(rel_line)

        _flush()  # flush last group

        if not by_file:
            return f"No matches for '{pattern}' in {rel_path or '.'}"

        sections: list[str] = []
        for file_path, file_lines in list(by_file.items())[:_MAX_FILES_IN_RESULT]:
            body = "\n".join(file_lines).strip()
            sections.append(f"=== {file_path} ===\n{body}")

        truncation = ""
        if len(by_file) > _MAX_FILES_IN_RESULT:
            truncation = (
                f"\n\n… {len(by_file) - _MAX_FILES_IN_RESULT} more files matched. "
                "Narrow the search with a subdirectory path or more specific pattern."
            )

        return "\n\n".join(sections) + truncation

    def _search_ast(self, root: Path, pattern: str, language: str, rel_path: str) -> str:
        """Structural AST search using ast-grep CLI.

        ast-grep patterns match code by shape, not text — e.g. 'os.Getenv($KEY)' finds
        all calls regardless of variable names. Requires: brew install ast-grep.
        """
        if not pattern:
            return "ERROR: pattern is required for search_ast"
        if not language:
            return (
                "ERROR: language is required for search_ast. "
                "Common values: go, python, typescript, javascript, rust, java, kotlin, c, cpp."
            )

        search_root = (root / rel_path).resolve() if rel_path else root
        if not str(search_root).startswith(str(root)):
            return "ERROR: path escapes project root"
        if not search_root.exists():
            return f"ERROR: directory not found: {rel_path or '.'}"

        # Try ast-grep binary (brew install) then sg (cargo install).
        binary = None
        for candidate in ("ast-grep", "sg"):
            result = subprocess.run(
                ["which", candidate], capture_output=True, text=True
            )
            if result.returncode == 0:
                binary = candidate
                break

        if not binary:
            return (
                "ast-grep not installed. Install with:\n"
                "  brew install ast-grep      # macOS\n"
                "  cargo install ast-grep     # cross-platform (requires Rust)\n"
                "Then retry the search_ast operation."
            )

        try:
            # --json outputs a JSON array; easier to parse than --json=compact NDJSON
            result = subprocess.run(
                [binary, "run", "--pattern", pattern, "--lang", language,
                 "--json", str(search_root)],
                capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            return "ERROR: ast-grep search timed out"

        raw = result.stdout.strip()
        stderr = result.stderr.strip()
        if not raw or raw in ("[]", "[ ]"):
            if stderr:
                return f"No matches (ast-grep stderr: {stderr})"
            return f"No structural matches for pattern '{pattern}' in {language}."

        import json as _json
        try:
            matches = _json.loads(raw)
        except _json.JSONDecodeError:
            return f"ERROR: could not parse ast-grep output: {raw[:200]}"

        if not isinstance(matches, list) or not matches:
            return f"No structural matches for pattern '{pattern}' in {language}."

        by_file: dict[str, list[str]] = {}
        root_str = str(root) + "/"
        for match in matches:
            if not isinstance(match, dict):
                continue
            file_abs = match.get("file", "")
            file_rel = file_abs.replace(root_str, "") if file_abs.startswith(root_str) else file_abs
            if any(part in _NOISE_DIRS for part in Path(file_rel).parts):
                continue
            start_line = match.get("range", {}).get("start", {}).get("line", 0) + 1
            text = match.get("lines", match.get("text", "")).rstrip()
            entry = f"  {start_line}│ {text}"
            by_file.setdefault(file_rel, []).append(entry)

        if not by_file:
            return f"No structural matches for pattern '{pattern}' in {language}."

        sections: list[str] = []
        for file_path, entries in list(by_file.items())[:_MAX_FILES_IN_RESULT]:
            body = "\n".join(entries)
            sections.append(f"=== {file_path} ===\n{body}")

        truncation = ""
        if len(by_file) > _MAX_FILES_IN_RESULT:
            truncation = (
                f"\n\n… {len(by_file) - _MAX_FILES_IN_RESULT} more files matched. "
                "Narrow the search with a subdirectory path."
            )

        return "\n\n".join(sections) + truncation

    @staticmethod
    def _glob_to_include(glob: str) -> str:
        """Convert glob like '**/*.go' to grep --include pattern '*.go'."""
        parts = glob.replace("**/", "").split("/")
        return parts[-1] if parts else "*"
