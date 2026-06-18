"""
CrewAI tool: load the Definition of Done from designs/SOP/SOP-DoD-Definition-of-Done.md.

Always reads the live file at task execution time — never cached. The Scrum Master
agent uses this to perform DoD compliance checks before closing any work item.
"""

from pathlib import Path

from crewai.tools import BaseTool
from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _dod_path() -> Path:
    import os
    designs_root = Path(os.environ.get("DESIGNS_PATH", str(_REPO_ROOT / "designs")))
    return designs_root / "SOP" / "SOP-DoD-Definition-of-Done.md"


class DoDCheckerInput(BaseModel):
    pass


class DoDCheckerTool(BaseTool):
    name: str = "dod_checker"
    description: str = (
        "Load the current Definition of Done from designs/SOP/SOP-DoD-Definition-of-Done.md. "
        "Always call this before performing a DoD check — do not rely on a cached or "
        "remembered version of the DoD. Returns the full DoD document content."
    )
    args_schema: type[BaseModel] = DoDCheckerInput

    def _run(self) -> str:
        dod_path = _dod_path()

        if not dod_path.exists():
            return (
                f"SOP-DoD-Definition-of-Done.md not found at {dod_path}. "
                f"Ensure designs/SOP/SOP-DoD-Definition-of-Done.md exists "
                f"(current resolved path: {dod_path.resolve()})."
            )

        return dod_path.read_text(encoding="utf-8")
