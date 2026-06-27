"""
CrewAI tool: read knowledge documents (ADDs, ADRs, role/function/stack docs)
from the project's knowledge repo.

Documents are loaded into memory at construction time. Supports any project's
knowledge repo — point DESIGNS_PATH to a local checkout, or set DESIGNS_REPO
for auto-clone on first use.

Environment variables:
  DESIGNS_PATH    Local path to the knowledge repo (required, or auto-cloned here)
  DESIGNS_REPO    Git URL to clone if DESIGNS_PATH does not exist (optional)
  DESIGNS_BRANCH  Branch to checkout when cloning (default: main)
"""

import os
import subprocess
from pathlib import Path

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from shared.home import default_designs_path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _designs_root() -> Path:
    explicit = os.environ.get("DESIGNS_PATH", "")
    if explicit:
        return Path(explicit)
    # Prefer designs/ submodule in cwd (inside the platform repo)
    local = Path.cwd() / "designs"
    if local.exists():
        return local
    return default_designs_path()


def _ensure_designs(root: Path) -> Path:
    """Clone or pull the knowledge repo. Returns root whether or not it succeeds."""
    repo_url = os.environ.get("DESIGNS_REPO", "")
    branch = os.environ.get("DESIGNS_BRANCH", "main")

    if not root.exists():
        if not repo_url:
            return root  # missing and no repo configured — warn in model_post_init
        print(f"[knowledge_reader] Cloning {repo_url} → {root}")
        try:
            subprocess.run(
                ["git", "clone", "--depth=1", "--branch", branch, repo_url, str(root)],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace").strip() if exc.stderr else ""
            print(
                f"[knowledge_reader] Clone failed — project knowledge unavailable.\n"
                f"  Set DESIGNS_REPO/DESIGNS_PATH in your .env to enable it.\n"
                + (f"  git: {stderr}" if stderr else "")
            )
    elif (root / ".git").exists() and repo_url:
        subprocess.run(
            ["git", "-C", str(root), "pull", "--ff-only"],
            check=False,
            capture_output=True,
        )

    return root


def _load_bundle(designs_root: Path) -> dict[str, str]:
    """Pre-load knowledge docs into {stem: content}.

    Load order (later entries win, enabling project-level overrides):
      1. code_crew/knowledge/{agents,stacks,functions}/  — built-in agent/stack/process guides
      2. designs/ADR/ and ADD/                          — project architecture decisions
      3. .code-crew/stacks/ and functions/              — project-local overrides
    """
    docs: dict[str, str] = {}

    # 1. Built-in agent, stack, and function guides (shipped with code_crew)
    builtin = _REPO_ROOT / "code_crew" / "knowledge"
    for subdir in ("agents", "stacks", "functions"):
        directory = builtin / subdir
        if directory.exists():
            for md_file in sorted(directory.glob("*.md")):
                if md_file.stem == "index":
                    continue
                docs[md_file.stem] = md_file.read_text(encoding="utf-8")

    # 2. Project architecture decisions (ADR, ADD) from designs repo
    for subdir in ("ADR", "ADD"):
        directory = designs_root / subdir
        if not directory.exists():
            continue
        for md_file in sorted(directory.glob("*.md")):
            if md_file.stem in ("ADR", "ADD", "CRD", "EVAL", "README"):
                continue
            docs[md_file.stem] = md_file.read_text(encoding="utf-8")

    # 3. Project-local overrides from .code-crew/stacks/ and .code-crew/functions/
    local = Path.cwd() / ".code-crew"
    for subdir in ("stacks", "functions"):
        directory = local / subdir
        if directory.exists():
            for md_file in sorted(directory.glob("*.md")):
                docs[md_file.stem] = md_file.read_text(encoding="utf-8")

    return docs


class KnowledgeReaderInput(BaseModel):
    document_name: str = Field(
        description=(
            "Filename stem of the document to read (without .md extension). "
            "Examples — ADDs: 'ADD-018-Terraform-Module-Structure'; "
            "ADRs: 'ADR-025-GSD-Agent-Assisted-Development'; "
            "Roles: 'architect', 'engineer', 'product-owner', 'qa-lead', 'devops-lead', "
            "'scrum-master', 'security-lead', 'release-engineer', 'compliance-officer'; "
            "Functions: 'code-architecture', 'bdd-authoring', 'definition-of-done', "
            "'domain-driven-design', 'scaffold-code', 'scaffold-test', 'branching-strategy', "
            "'release-notes', 'versioning', 'sprint-process', etc.; "
            "Tech stacks: 'go-backend', 'typescript-react', 'python', 'terraform', 'terraform-aws', "
            "'bdd-testing', 'ecs-deployment'; "
            "Compliance frameworks: 'owasp', 'hipaa', 'soc2', 'gdpr', 'ccpa', "
            "'fips-140-3', 'nist', 'cfr-part-11', 'ai-ml'; "
            "Overview: 'overview'"
        )
    )


class KnowledgeReaderTool(BaseTool):
    name: str = "knowledge_reader"
    description: str = (
        "Read a knowledge document from the project's knowledge repo. "
        "Pass the filename stem (without .md) to retrieve the full content. "
        "Use this to look up: architecture design documents (ADD), architecture decisions (ADR), "
        "role definitions (architect, engineer, product-owner, qa-lead, devops-lead, "
        "scrum-master, security-lead, release-engineer, compliance-officer), "
        "function guides (code-architecture, bdd-authoring, definition-of-done, "
        "domain-driven-design, scaffold-code, scaffold-test, branching-strategy, "
        "release-notes, versioning, sprint-process, etc.), "
        "tech stack conventions (go-backend, typescript-react, python, terraform, terraform-aws, "
        "bdd-testing, ecs-deployment), "
        "and compliance/security framework checklists (owasp, hipaa, soc2, gdpr, ccpa, "
        "fips-140-3, nist, cfr-part-11, ai-ml). "
        "Always prefer reading a document over relying on memory. "
        "All documents are pre-loaded at startup."
    )
    args_schema: type[BaseModel] = KnowledgeReaderInput
    _docs: dict[str, str] = {}

    def model_post_init(self, __context) -> None:
        root = _ensure_designs(_designs_root())
        self._docs = _load_bundle(root)  # always loads built-ins; designs root optional
        add_count = sum(1 for k in self._docs if k.startswith("ADD-") or k.startswith("ADR-"))
        if add_count == 0:
            print(
                "[knowledge_reader] No project ADDs/ADRs loaded — "
                "set DESIGNS_PATH or DESIGNS_REPO to enable architecture lookup."
            )

    def _run(self, document_name: str) -> str:
        if document_name in self._docs:
            return self._docs[document_name]

        lower = document_name.lower()
        for key, content in self._docs.items():
            if key.lower() == lower:
                return content

        matches = [(k, v) for k, v in self._docs.items() if k.lower().startswith(lower)]
        if matches:
            return matches[0][1]

        matches = [(k, v) for k, v in self._docs.items() if lower in k.lower()]
        if matches:
            return matches[0][1]

        available = sorted(self._docs.keys())
        return (
            f"Document '{document_name}' not found. "
            f"Available ({len(available)} docs): {', '.join(available[:30])}"
        )
