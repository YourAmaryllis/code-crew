"""
Manages the code-crew home directory at ~/code-crew/.

Structure:
  ~/code-crew/
    config          global configuration (env vars, loaded before local .env)
    repos/          cloned knowledge repos (e.g. repos/designs/)
    outputs/        per-sprint / per-ticket crew output files
    memory/         user memory store
"""

from pathlib import Path

HOME = Path.home() / "code-crew"
REPOS_DIR = HOME / "repos"
OUTPUTS_DIR = HOME / "outputs"
MEMORY_DIR = HOME / "memory"
CONFIG_FILE = HOME / "config"


def ensure_home() -> None:
    """Create the code-crew home directory structure if it doesn't exist."""
    for d in (HOME, REPOS_DIR, OUTPUTS_DIR, MEMORY_DIR):
        d.mkdir(parents=True, exist_ok=True)


def default_designs_path() -> Path:
    return REPOS_DIR / "designs"


def default_memory_path() -> Path:
    return MEMORY_DIR / "crew-memory.jsonl"


def output_path(sprint_name: str, ticket_key: str) -> Path:
    safe_sprint = sprint_name.replace(" ", "-").replace("/", "-")
    return OUTPUTS_DIR / safe_sprint / f"{ticket_key}.md"
