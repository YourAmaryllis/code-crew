"""
CrewAI tool: load the Definition of Done from the project's knowledge repo.

Always reads the live file — never cached. The DoD file path is configurable
so different projects can point to their own DoD document.

Environment variables:
  DESIGNS_PATH    Local path to the knowledge repo
  DOD_PATH        Path to the DoD file — absolute, or relative to DESIGNS_PATH
                  (default: SOP/SOP-DoD-Definition-of-Done.md)
"""

import os
from pathlib import Path

from crewai.tools import BaseTool
from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DOD_REL = "SOP/SOP-DoD-Definition-of-Done.md"


def _dod_path() -> Path:
    explicit = os.environ.get("DOD_PATH", "")
    if explicit:
        p = Path(explicit)
        return p if p.is_absolute() else Path(os.environ.get("DESIGNS_PATH", "")) / p
    designs_root = Path(os.environ.get("DESIGNS_PATH", str(_REPO_ROOT / "designs")))
    return designs_root / _DEFAULT_DOD_REL


class DoDCheckerTool(BaseTool):
    name: str = "dod_checker"
    description: str = (
        "Load the current Definition of Done document for this project. "
        "Always call this before performing a DoD compliance check — do not rely on "
        "a remembered version. Returns the full DoD document content."
    )
    args_schema: type[BaseModel] = type("DoDCheckerInput", (BaseModel,), {})

    def _run(self) -> str:
        path = _dod_path()
        if not path.exists():
            return (
                f"Definition of Done not found at {path}.\n"
                f"Set DOD_PATH in .env (absolute or relative to DESIGNS_PATH), "
                f"or ensure {_DEFAULT_DOD_REL} exists under DESIGNS_PATH."
            )
        return path.read_text(encoding="utf-8")
