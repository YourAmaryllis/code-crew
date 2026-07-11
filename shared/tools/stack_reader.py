"""Stack reader tool — loads technology stack conventions for the current project.

Replaces knowledge_reader for stack lookups. Two modes:
  - Named stacks: load specific stacks/*.md files by name
  - Auto-detect: scan project markers → detect stacks → load docs → write back to inventory

Agents only call this when stacks were not pre-injected into the task description.
If inventory.stacks is populated (set by /explore), crew builders pre-inject the stack
docs directly and this tool is never needed.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# File-existence → stack name
_FILE_RULES: list[tuple[str, str]] = [
    ("go.mod",           "go-backend"),
    ("go.sum",           "go-backend"),
    ("package.json",     "typescript-react"),
    ("tsconfig.json",    "typescript-react"),
    ("requirements.txt", "python"),
    ("pyproject.toml",   "python"),
    ("setup.py",         "python"),
]

_KNOWLEDGE_STACKS = Path(__file__).parent.parent.parent / "code_crew" / "knowledge" / "stacks"


def _detect_stacks(root: Path) -> list[str]:
    detected: set[str] = set()

    for marker, stack in _FILE_RULES:
        if (root / marker).exists():
            detected.add(stack)

    tf_files = list(root.rglob("*.tf"))[:10]
    if tf_files:
        detected.add("terraform")
        content = "\n".join(f.read_text(errors="ignore")[:2000] for f in tf_files[:5])
        if re.search(r'provider\s+"aws"', content):
            detected.add("terraform-aws")
        if "aws_ecs" in content or "aws_ecs_task" in content:
            detected.add("ecs-deployment")

    if list(root.rglob("*.feature"))[:3]:
        detected.add("bdd-testing")

    # AI/ML detection via dependency manifest content
    for manifest in ["requirements.txt", "pyproject.toml", "go.mod", "package.json"]:
        mp = root / manifest
        if mp.exists():
            txt = mp.read_text(errors="ignore")
            if any(k in txt for k in ("torch", "transformers", "openai", "langchain", "crewai")):
                detected.add("ai-ml")
            break

    return sorted(detected)


def _load_docs(stacks: list[str]) -> str:
    parts = []
    for name in stacks:
        p = _KNOWLEDGE_STACKS / f"{name}.md"
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8")
        if txt.startswith("---"):
            body = re.split(r"^---\s*$", txt, maxsplit=2, flags=re.MULTILINE)
            txt = body[2].strip() if len(body) >= 3 else txt
        parts.append(f"### Stack: `{name}`\n\n{txt}")
    return "\n\n---\n\n".join(parts)


def _write_back(root: Path, stacks: list[str]) -> None:
    inv_path = root / ".code-crew" / "inventory.json"
    if not inv_path.exists():
        return
    try:
        data = json.loads(inv_path.read_text(encoding="utf-8"))
        existing = data.get("inventory", {}).get("stacks", [])
        merged = sorted(set(existing) | set(stacks))
        data.setdefault("inventory", {})["stacks"] = merged
        inv_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


class _Input(BaseModel):
    stacks: Optional[list[str]] = Field(
        default=None,
        description=(
            "Stack names to load, e.g. ['go-backend', 'ecs-deployment']. "
            "Omit to auto-detect from the project."
        ),
    )


class StackReaderTool(BaseTool):
    name: str = "stack_reader"
    description: str = (
        "Load technology stack conventions (naming rules, patterns, commands) for this project. "
        "Pass specific stack names to load known stacks, or omit args to auto-detect from "
        "project files. Only call this if stack docs were not already injected in the task context."
    )
    args_schema: Type[BaseModel] = _Input

    def _run(self, stacks: Optional[list[str]] = None) -> str:
        root = Path(os.environ.get("PROJECT_ROOT", "")).resolve() or Path.cwd()

        if not stacks:
            stacks = _detect_stacks(root)
            if stacks:
                _write_back(root, stacks)

        if not stacks:
            return "No stacks detected. Project may be a new or generic codebase with no recognised markers."

        docs = _load_docs(stacks)
        if not docs:
            return f"Stacks detected ({', '.join(stacks)}) but no matching docs found in stacks/."

        return f"Stack conventions for: {', '.join(stacks)}\n\n{docs}"
