"""
CrewAI tool: read and drift-check OpenAPI specs in the workspace.

Operations:
  read_spec      — return the full spec as JSON/YAML text
  list_routes    — list all (method, path) pairs from the spec
  check_drift    — compare spec routes against route handler files in the workspace
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


_SPEC_CANDIDATES = [
    "docs/swagger.json",
    "docs/swagger.yaml",
    "docs/openapi.json",
    "docs/openapi.yaml",
    "openapi.yaml",
    "openapi.json",
]

# Patterns that indicate a route definition per stack
_ROUTE_PATTERNS: list[tuple[str, str]] = [
    (r'@Router\s+(\S+)\s+\[(\w+)\]', "go-swaggo"),         # // @Router /v1/x [get]
    (r'@app\.(get|post|put|patch|delete)\(["\']([^"\']+)', "python-flask"),
    (r'router\.(GET|POST|PUT|PATCH|DELETE)\(["\']([^"\']+)', "go-gorilla"),
    (r'\.(get|post|put|patch|delete)\(["\']([^"\']+)', "express"),
    (r'@(Get|Post|Put|Patch|Delete)\(["\']([^"\']+)', "nestjs"),
]


def _find_spec(root: Path) -> Path | None:
    for candidate in _SPEC_CANDIDATES:
        p = root / candidate
        if p.exists():
            return p
    return None


def _load_spec(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        raise RuntimeError("PyYAML not installed — run `pip install pyyaml`")


def _spec_routes(spec: dict) -> list[tuple[str, str]]:
    routes = []
    for path, methods in (spec.get("paths") or {}).items():
        for method in methods:
            if method.lower() in ("get", "post", "put", "patch", "delete", "head", "options"):
                routes.append((method.upper(), path))
    return sorted(routes)


def _code_routes(root: Path) -> list[tuple[str, str]]:
    """Grep source files for route registrations. Best-effort, not exhaustive."""
    routes: set[tuple[str, str]] = set()
    extensions = ["*.go", "*.py", "*.ts", "*.js"]
    files: list[Path] = []
    for ext in extensions:
        files.extend(root.rglob(ext))

    for fpath in files:
        try:
            text = fpath.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern, _ in _ROUTE_PATTERNS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                groups = m.groups()
                if len(groups) == 2:
                    method_or_path, path_or_method = groups
                    # swaggo: groups are (path, method)
                    if "/" in method_or_path:
                        routes.add((path_or_method.upper(), method_or_path))
                    else:
                        routes.add((method_or_path.upper(), path_or_method))
    return sorted(routes)


class ApiSpecInput(BaseModel):
    operation: str = Field(
        description=(
            "Operation to perform:\n"
            "  read_spec    — return the spec file content (truncated to 4000 chars)\n"
            "  list_routes  — list all (METHOD, /path) pairs defined in the spec\n"
            "  check_drift  — compare spec routes against route registrations in source files"
        )
    )
    spec_path: str = Field(
        default="",
        description="Optional: explicit path to the spec file relative to project root. "
                    "Auto-detected if omitted.",
    )


class ApiSpecTool(BaseTool):
    name: str = "api_spec"
    description: str = (
        "Read, inspect, and drift-check the project's OpenAPI spec. "
        "Use read_spec to see the full contract, list_routes to enumerate endpoints, "
        "check_drift to find routes in code that are missing from the spec or vice versa."
    )
    args_schema: type[BaseModel] = ApiSpecInput

    def _run(self, operation: str, spec_path: str = "") -> str:
        root = Path.cwd()
        path = (root / spec_path) if spec_path else _find_spec(root)

        if operation == "read_spec":
            if not path or not path.exists():
                return "No spec file found. Expected one of: " + ", ".join(_SPEC_CANDIDATES)
            text = path.read_text(encoding="utf-8")
            if len(text) > 4000:
                text = text[:4000] + f"\n... (truncated — full spec at {path})"
            return f"Spec: {path}\n\n{text}"

        if operation == "list_routes":
            if not path or not path.exists():
                return "No spec file found."
            spec = _load_spec(path)
            routes = _spec_routes(spec)
            if not routes:
                return "No routes found in spec."
            lines = [f"{m:7} {p}" for m, p in routes]
            return f"{len(routes)} routes in {path}:\n\n" + "\n".join(lines)

        if operation == "check_drift":
            if not path or not path.exists():
                return (
                    "No spec file found — cannot check drift. "
                    "Generate the spec first (swag init / export_openapi)."
                )
            spec = _load_spec(path)
            spec_routes = set(_spec_routes(spec))
            code_routes = set(_code_routes(root))

            in_code_not_spec = sorted(code_routes - spec_routes)
            in_spec_not_code = sorted(spec_routes - code_routes)

            if not in_code_not_spec and not in_spec_not_code:
                return "No drift detected — spec matches source route registrations."

            lines = [f"Drift detected (spec: {path}):"]
            if in_code_not_spec:
                lines.append("\nIn source code but NOT in spec (missing from spec):")
                lines += [f"  {m:7} {p}" for m, p in in_code_not_spec]
            if in_spec_not_code:
                lines.append("\nIn spec but NOT found in source code (stale spec entry or handler not yet written):")
                lines += [f"  {m:7} {p}" for m, p in in_spec_not_code]
            lines.append(
                "\nNote: drift check uses pattern matching and may have false positives "
                "for dynamically registered routes."
            )
            return "\n".join(lines)

        return f"Unknown operation: {operation}. Use read_spec, list_routes, or check_drift."
