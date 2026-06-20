"""
CrewAI tool: read knowledge documents (ADDs, ADRs, SDLC role/function/stack docs)
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
    return Path(explicit) if explicit else default_designs_path()


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
                f"[knowledge_reader] Clone failed — SDLC knowledge unavailable.\n"
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
    """Pre-load OKF .md files from {root}/ADR/, ADD/, SDLC/ into {stem: content}.

    SOP/ is intentionally excluded — all relevant content has been migrated to SDLC/.
    """
    docs: dict[str, str] = {}
    for subdir in ("ADR", "ADD"):
        directory = designs_root / subdir
        if not directory.exists():
            continue
        for md_file in sorted(directory.glob("*.md")):
            if md_file.stem in ("ADR", "ADD", "CRD", "EVAL", "README"):
                continue
            docs[md_file.stem] = md_file.read_text(encoding="utf-8")

    # Load SDLC role/function/stack files (SDLC/**/*.md)
    sdlc_dir = designs_root / "SDLC"
    if sdlc_dir.exists():
        for md_file in sorted(sdlc_dir.rglob("*.md")):
            docs[md_file.stem] = md_file.read_text(encoding="utf-8")

    return docs


class KnowledgeReaderInput(BaseModel):
    document_name: str = Field(
        description=(
            "Filename stem of the document to read (without .md extension). "
            "Examples — ADDs: 'ADD-018-Terraform-Module-Structure'; "
            "ADRs: 'ADR-025-GSD-Agent-Assisted-Development'; "
            "SDLC roles: 'architect', 'engineer', 'product-owner', 'qa-lead'; "
            "SDLC functions: 'code-architecture', 'bdd-authoring', 'definition-of-done', "
            "'domain-driven-design', 'scaffold-code', 'scaffold-test'; "
            "SDLC stacks: 'go-backend', 'typescript-react', 'python', 'terraform-aws'; "
            "Overview: 'overview'"
        )
    )


class KnowledgeReaderTool(BaseTool):
    name: str = "knowledge_reader"
    description: str = (
        "Read a knowledge document from the project's knowledge repo. "
        "Pass the filename stem (without .md) to retrieve the full content. "
        "Use this to look up: architecture design documents (ADD), architecture decisions (ADR), "
        "SDLC role definitions (architect, engineer, product-owner, qa-lead, devops-lead, "
        "scrum-master, security-lead, compliance-officer), "
        "SDLC function guides (code-architecture, bdd-authoring, definition-of-done, "
        "domain-driven-design, scaffold-code, scaffold-test, branching-strategy, etc.), "
        "and tech stack conventions (go-backend, typescript-react, python, terraform-aws). "
        "Always prefer reading a document over relying on memory. "
        "All documents are pre-loaded at startup."
    )
    args_schema: type[BaseModel] = KnowledgeReaderInput
    _docs: dict[str, str] = {}

    def model_post_init(self, __context) -> None:
        root = _ensure_designs(_designs_root())
        self._docs = _load_bundle(root) if root.exists() else {}
        if not self._docs:
            print(
                "[knowledge_reader] Warning: no documents loaded. "
                "Set DESIGNS_PATH or DESIGNS_REPO in your .env."
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
