"""
Parse OKF (Open Knowledge Format) markdown files into typed concepts.

OKF spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

Each file is a markdown document with YAML frontmatter. This loader extracts:
  - Frontmatter fields into a typed dataclass
  - The markdown body as the prompt/backstory text

AgentConcept maps to a CrewAI Agent:
  - role    <- frontmatter.role
  - goal    <- frontmatter.goal
  - backstory <- markdown body (stripped of heading lines)

TaskConcept maps to a CrewAI Task:
  - description     <- markdown body
  - expected_output <- frontmatter.expected_output
  - agent           <- frontmatter.agent (key into agents dict)
  - context_agents  <- frontmatter.context_agents (list of agent keys)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split OKF markdown into (frontmatter_dict, body_text)."""
    if not text.startswith("---"):
        return {}, text
    end = text.index("---", 3)
    frontmatter = yaml.safe_load(text[3:end])
    body = text[end + 3:].lstrip("\n")
    return frontmatter or {}, body


def _strip_leading_citations(body: str) -> str:
    """Remove the conventional '# Citations' or '# References' section from body.

    These sections are for human navigation; agents don't need them in their backstory.
    """
    return re.split(r"\n# (?:Citations|References)\b", body)[0].rstrip()


@dataclass
class AgentConcept:
    """Parsed OKF agent concept document."""

    path: Path
    title: str
    description: str
    role: str
    goal: str
    backstory: str
    tags: list[str] = field(default_factory=list)
    sop_refs: list[str] = field(default_factory=list)
    raw_frontmatter: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "AgentConcept":
        fm, body = _split_frontmatter(path.read_text(encoding="utf-8"))
        backstory = _strip_leading_citations(body)
        return cls(
            path=path,
            title=fm.get("title", path.stem),
            description=fm.get("description", ""),
            role=fm.get("role", "").strip(),
            goal=fm.get("goal", "").strip(),
            backstory=backstory.strip(),
            tags=fm.get("tags", []),
            sop_refs=fm.get("sop_refs", []),
            raw_frontmatter=fm,
        )


@dataclass
class TaskConcept:
    """Parsed OKF task concept document."""

    path: Path
    title: str
    description: str
    expected_output: str
    agent: str
    context_agents: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    raw_frontmatter: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "TaskConcept":
        fm, body = _split_frontmatter(path.read_text(encoding="utf-8"))
        return cls(
            path=path,
            title=fm.get("title", path.stem),
            description=body.strip(),
            expected_output=fm.get("expected_output", "").strip(),
            agent=fm.get("agent", ""),
            context_agents=fm.get("context_agents", []),
            tags=fm.get("tags", []),
            raw_frontmatter=fm,
        )


def load_agent_concept(path: Path | str) -> AgentConcept:
    return AgentConcept.from_file(Path(path))


def load_task_concept(path: Path | str) -> TaskConcept:
    return TaskConcept.from_file(Path(path))


def load_bundle_agents(agents_dir: Path) -> dict[str, AgentConcept]:
    """Load all agent OKF docs from a directory. Keys are file stems."""
    return {
        p.stem: AgentConcept.from_file(p)
        for p in sorted(agents_dir.glob("*.md"))
        if p.stem != "index"
    }


def load_bundle_tasks(tasks_dir: Path) -> dict[str, TaskConcept]:
    """Load all task OKF docs from a directory. Keys are file stems."""
    return {
        p.stem: TaskConcept.from_file(p)
        for p in sorted(tasks_dir.glob("*.md"))
        if p.stem != "index"
    }
