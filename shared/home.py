"""
Manages the code-crew home directory at ~/.code-crew/.

Structure:
  ~/.code-crew/
    config.yaml         global configuration (YAML; env: + structured keys)
    config              legacy global config (dotenv; used if config.yaml absent)
    profiles/           named config profiles
      <name>.yaml       profile — env: section + stacks: + any structured keys
    repos/              cloned knowledge repos (e.g. repos/designs/)
    outputs/            per-sprint / per-ticket crew output files
    memory/             user memory store

Load order (later entries override earlier ones):
  1. ~/.code-crew/config.yaml (or config)  — shared defaults
  2. ~/.code-crew/profiles/<n>.yaml        — profile overrides
  3. ./.code-crew.yaml  env:               — project-level env overrides
  4. ./.env                                — local secrets (highest priority)

Profile selection (first match wins):
  • --profile CLI flag
  • CODE_CREW_PROFILE env var
  • profile: key in ./.code-crew.yaml
"""

from pathlib import Path

HOME = Path.home() / ".code-crew"
REPOS_DIR = HOME / "repos"
OUTPUTS_DIR = HOME / "outputs"
MEMORY_DIR = HOME / "memory"
PROFILES_DIR = HOME / "profiles"
CONFIG_FILE = HOME / "config"        # legacy dotenv
CONFIG_YAML = HOME / "config.yaml"  # preferred YAML


def ensure_home() -> None:
    """Create the code-crew home directory structure if it doesn't exist."""
    for d in (HOME, REPOS_DIR, OUTPUTS_DIR, MEMORY_DIR, PROFILES_DIR):
        d.mkdir(parents=True, exist_ok=True)


def list_profiles() -> list[str]:
    """Return sorted names of all available profiles (yaml and legacy env)."""
    if not PROFILES_DIR.exists():
        return []
    names: set[str] = set()
    for p in PROFILES_DIR.glob("*.yaml"):
        names.add(p.stem)
    for p in PROFILES_DIR.glob("*.env"):   # legacy — shown with deprecation note
        names.add(p.stem)
    return sorted(names)


def profile_path(name: str) -> Path:
    """Return the preferred (YAML) path for a profile."""
    return PROFILES_DIR / f"{name}.yaml"


def legacy_profile_path(name: str) -> Path:
    """Return the legacy dotenv path for a profile (for migration detection)."""
    return PROFILES_DIR / f"{name}.env"


def default_designs_path() -> Path:
    return REPOS_DIR / "designs"


def default_memory_path() -> Path:
    return MEMORY_DIR / "crew-memory.jsonl"


def output_path(sprint_name: str, ticket_key: str) -> Path:
    safe_sprint = sprint_name.replace(" ", "-").replace("/", "-")
    return OUTPUTS_DIR / safe_sprint / f"{ticket_key}.md"
