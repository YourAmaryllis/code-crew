"""
CrewAI tool: read SOP, ADD, or ADR documents directly from the designs/ submodule.

All documents are loaded into memory at construction time (no filesystem reads during
crew execution). Reads OKF files from designs/SOP/, designs/ADR/, designs/ADD/.
"""

from pathlib import Path

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _designs_root() -> Path:
    import os
    return Path(os.environ.get("DESIGNS_PATH", str(_REPO_ROOT / "designs")))


def _load_bundle(designs_root: Path) -> dict[str, str]:
    """Pre-load all .md files from designs/SOP/, ADR/, ADD/ into a {stem: content} dict."""
    docs: dict[str, str] = {}
    search_dirs = [
        designs_root / "SOP",
        designs_root / "ADR",
        designs_root / "ADD",
    ]
    for directory in search_dirs:
        if not directory.exists():
            continue
        for md_file in sorted(directory.glob("*.md")):
            if md_file.stem in ("SOP", "ADR", "ADD", "CRD", "EVAL", "README"):
                continue
            docs[md_file.stem] = md_file.read_text(encoding="utf-8")
    return docs


class SOPReaderInput(BaseModel):
    document_name: str = Field(
        description=(
            "Filename stem of the document to read (without .md extension). "
            "Examples: 'SOP-3-Dev-Process', 'ADD-018-Terraform-Module-Structure', "
            "'ADR-025-GSD-Agent-Assisted-Development', 'SOP-DoD-Definition-of-Done'"
        )
    )


class SOPReaderTool(BaseTool):
    name: str = "sop_reader"
    description: str = (
        "Read a YourAmaryllis SOP, ADD, or ADR document from the designs/ submodule. "
        "Pass the filename stem (without .md) to retrieve the full document content. "
        "Use this to look up SOPs, architectural decisions, and design documents "
        "rather than relying on memory. All documents are pre-loaded — no external reads needed."
    )
    args_schema: type[BaseModel] = SOPReaderInput
    _docs: dict[str, str] = {}

    def model_post_init(self, __context) -> None:
        root = _designs_root()
        self._docs = _load_bundle(root) if root.exists() else {}

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
            f"Document '{document_name}' not found in designs/. "
            f"Available ({len(available)} docs): {', '.join(available[:30])}"
        )
