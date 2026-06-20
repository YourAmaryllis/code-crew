"""
YAML-based configuration loader for code-crew.

Profile and global config files use YAML with two kinds of content:

  env:                  # flat key→value pairs injected into os.environ
    BEDROCK_MODEL_ID: us.anthropic.claude-...
    AWS_PROFILE: myprofile

  stacks:               # tech stack list (profile-level; project yaml overrides)
    - python
    - typescript-react

All other top-level keys (project:, profile:, issue_tracker:, etc.) are
structured data used directly — they are NOT injected as env vars.

Load order — each layer overrides the previous:
  1. ~/.code-crew/config[.yaml]      global defaults
  2. ~/.code-crew/profiles/<n>.yaml  profile overrides
  3. ./.code-crew.yaml  env:         project-level env overrides
  4. ./.env                          legacy / secrets (highest priority)

Stack resolution order (first match wins):
  1. CODE_CREW_STACKS env var        explicit shell override
  2. ./.code-crew.yaml stacks:       project declaration
  3. _CODE_CREW_STACKS_PROFILE       set when a profile with stacks: is loaded
  4. file-based auto-detection
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml


def load_yaml_config(path: Path, override: bool = True) -> dict:
    """
    Parse a code-crew YAML config file and apply its env: section to os.environ.

      env: keys  →  os.environ (respecting `override` flag)
      stacks:    →  os.environ["_CODE_CREW_STACKS_PROFILE"] (internal, profile-level)

    Returns the full parsed dict for callers that need structured keys
    (project:, profile:, stacks:, etc.).
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    for key, val in data.get("env", {}).items():
        if override or key not in os.environ:
            os.environ[str(key)] = str(val)

    stacks = data.get("stacks")
    if isinstance(stacks, list) and stacks:
        stacks_str = ",".join(str(s) for s in stacks)
        if override or "_CODE_CREW_STACKS_PROFILE" not in os.environ:
            os.environ["_CODE_CREW_STACKS_PROFILE"] = stacks_str

    return data


def yaml_env_keys(path: Path) -> set[str]:
    """
    Return the set of os.environ keys that load_yaml_config(path) would set.
    Used by _switch_profile() to clean up when switching away from a profile.
    """
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return set()
    keys = {str(k) for k in data.get("env", {})}
    if data.get("stacks"):
        keys.add("_CODE_CREW_STACKS_PROFILE")
    return keys
