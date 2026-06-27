"""
Manages the code-crew home directory at ~/.code-crew/.

Structure:
  ~/.code-crew/
    config.yaml         global configuration (structured YAML)
    profiles/           named config profiles
      <name>.yaml       profile — structured YAML with optional stacks:
    repos/              cloned knowledge repos (e.g. repos/designs/)
    outputs/            per-sprint / per-ticket crew output files
    memory/             user memory store

Load order (later entries override earlier ones):
  1. ~/.code-crew/config.yaml    — shared defaults
  2. ~/.code-crew/profiles/<n>.yaml  — profile overrides
  3. ./.code-crew/config.yaml    — project-level overrides

Profile selection (first match wins):
  • --profile CLI flag
  • CODE_CREW_PROFILE env var
  • profile: key in ./.code-crew/config.yaml
"""

from pathlib import Path

HOME = Path.home() / ".code-crew"
REPOS_DIR = HOME / "repos"
OUTPUTS_DIR = HOME / "outputs"
MEMORY_DIR = HOME / "memory"
PROFILES_DIR = HOME / "profiles"
CONFIG_YAML = HOME / "config.yaml"
MCP_CONFIG = HOME / "mcp.yaml"


def ensure_home() -> None:
    """Create the code-crew home directory structure if it doesn't exist."""
    for d in (HOME, REPOS_DIR, OUTPUTS_DIR, MEMORY_DIR, PROFILES_DIR):
        d.mkdir(parents=True, exist_ok=True)


def list_profiles() -> list[str]:
    """Return sorted names of all available profiles."""
    if not PROFILES_DIR.exists():
        return []
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml"))


def profile_path(name: str) -> Path:
    return PROFILES_DIR / f"{name}.yaml"


def default_designs_path() -> Path:
    return REPOS_DIR / "designs"


def default_memory_path() -> Path:
    return MEMORY_DIR / "crew-memory.jsonl"


def output_path(sprint_name: str, ticket_key: str) -> Path:
    safe_sprint = sprint_name.replace(" ", "-").replace("/", "-")
    return OUTPUTS_DIR / safe_sprint / f"{ticket_key}.md"
