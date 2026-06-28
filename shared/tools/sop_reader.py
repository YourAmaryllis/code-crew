"""
CrewAI tool: read architecture documents (SOPs, ADDs, ADRs) from a knowledge repo.

Documents are loaded into memory at construction time. Point DESIGNS_PATH to
your designs directory, or place a designs/ submodule in your project root
(auto-detected).

Environment variables:
  DESIGNS_PATH    Local path to the designs directory (auto-detected from ./designs/)
"""

import os
from pathlib import Path

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from shared.home import default_designs_path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _designs_root() -> Path:
    explicit = os.environ.get("DESIGNS_PATH", "")
    if explicit:
        return Path(explicit)
    local = Path.cwd() / "designs"
    if local.exists():
        return local
    return default_designs_path()



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

    # Load SDLC role/function files (SDLC/**/*.md)
    sdlc_dir = designs_root / "SDLC"
    if sdlc_dir.exists():
        for md_file in sorted(sdlc_dir.rglob("*.md")):
            docs[md_file.stem] = md_file.read_text(encoding="utf-8")

    return docs


class SOPReaderInput(BaseModel):
    document_name: str = Field(
        description=(
            "Filename stem of the document to read (without .md extension). "
            "Examples: 'SOP-3-Dev-Process', 'ADD-018-Terraform-Module-Structure', "
            "'ADR-025-GSD-Agent-Assisted-Development', 'SOP-DoD-Definition-of-Done', "
            "'code-architecture', 'bdd-authoring', 'definition-of-done', 'overview'"
        )
    )


class SOPReaderTool(BaseTool):
    name: str = "sop_reader"
    description: str = (
        "Read an architecture or process document (ADD, ADR, SDLC) from the project's "
        "knowledge repo. Pass the filename stem (without .md) to retrieve the full "
        "document content. Use this to look up design documents, process guidelines, "
        "and role-based SDLC knowledge rather than relying on memory. "
        "All documents are pre-loaded at startup."
    )
    args_schema: type[BaseModel] = SOPReaderInput
    _docs: dict[str, str] = {}

    def model_post_init(self, __context) -> None:
        root = _designs_root()
        self._docs = _load_bundle(root) if root.exists() else {}
        if not self._docs:
            print(
                "[sop_reader] No documents loaded — "
                "run /init to create a designs directory or set DESIGNS_PATH."
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
