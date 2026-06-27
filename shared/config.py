"""
YAML-based configuration loader for code-crew.

Config files use structured YAML — each section maps to a set of env vars:

  bedrock:
    model_id: us.anthropic.claude-...
    region: us-east-1

  aws:
    profile: myprofile

  designs:
    repo: git@github.com:org/designs.git
    branch: main

  issue_tracker:
    type: jira
    project_key: PROJ
    jira:
      url: https://org.atlassian.net
      token: abc123

  stacks:
    - python
    - typescript-react

  flow:
    max_retries: 3

All structured keys are mapped to os.environ by _apply_section().

Load order — each layer overrides the previous:
  1. ~/.code-crew/config.yaml      global defaults
  2. ~/.code-crew/profiles/<n>.yaml  profile overrides
  3. ./.code-crew/config.yaml  (project-level)
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

# Mapping from structured YAML keys → env var names.
# Nested dicts represent nested YAML sections.
_ENV_MAP: dict[str, object] = {
    "bedrock": {
        "model_id": "BEDROCK_MODEL_ID",
        "fast_model_id": "BEDROCK_FAST_MODEL_ID",
        "powerful_model_id": "BEDROCK_POWERFUL_MODEL_ID",
        "region": "BEDROCK_REGION",
        "temperature": "BEDROCK_TEMPERATURE",
        "guardrail_id": "BEDROCK_GUARDRAIL_ID",
        "guardrail_version": "BEDROCK_GUARDRAIL_VERSION",
    },
    "aws": {
        "profile": "AWS_PROFILE",
    },
    "designs": {
        "repo": "DESIGNS_REPO",
        "branch": "DESIGNS_BRANCH",
        "path": "DESIGNS_PATH",
        "dod_path": "DOD_PATH",
    },
    "issue_tracker": {
        "type": "ISSUE_TRACKER",
        "project_key": "PROJECT_KEY",
        "jira": {
            "url": "JIRA_URL",
            "user": "JIRA_USER",
            "token": "JIRA_TOKEN",
        },
    },
    "flow": {
        "max_retries": "MAX_RETRIES",
    },
    "figma": {
        "token": "FIGMA_TOKEN",
    },
    "architecture": {
        "style": "ARCHITECTURE_STYLE",
    },
    "db": {
        "migration_tool": "DB_MIGRATION_TOOL",
        "schema_path": "DB_SCHEMA_PATH",
    },
    "testing": {
        "framework": "TESTING_FRAMEWORK",
        "bdd": "TESTING_BDD",
    },
    "api": {
        "doc_standard": "API_DOC_STANDARD",
    },
    "domain": {
        "methodology": "DOMAIN_METHODOLOGY",
        "diagram_format": "DOMAIN_DIAGRAM_FORMAT",
    },
    "telemetry": {
        "langfuse_public_key": "LANGFUSE_PUBLIC_KEY",
        "langfuse_secret_key": "LANGFUSE_SECRET_KEY",
        "langfuse_host": "LANGFUSE_HOST",
    },
}


def _apply_section(data: dict, mapping: dict, override: bool) -> None:
    for key, val in data.items():
        if key not in mapping:
            continue
        target = mapping[key]
        if isinstance(target, dict) and isinstance(val, dict):
            _apply_section(val, target, override)
        elif isinstance(target, str) and val is not None:
            if override or target not in os.environ:
                os.environ[target] = str(val)


def _collect_env_keys(mapping: dict) -> set[str]:
    keys: set[str] = set()
    for v in mapping.values():
        if isinstance(v, str):
            keys.add(v)
        elif isinstance(v, dict):
            keys |= _collect_env_keys(v)
    return keys


def load_yaml_config(path: Path, override: bool = True) -> dict:
    """
    Parse a code-crew YAML config file and apply its settings to os.environ.

    Returns the full parsed dict for callers that need structured keys.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    # Structured format (preferred)
    for section, mapping in _ENV_MAP.items():
        if section in data and isinstance(data[section], dict):
            _apply_section(data[section], mapping, override)

    # Legacy env: section — deprecated, kept for backward compat
    if "env" in data:
        import sys
        print(
            f"[config] {path.name}: 'env:' section is deprecated — "
            "migrate to structured YAML (bedrock:, aws:, designs:, …)",
            file=sys.stderr,
        )
        for key, val in data["env"].items():
            if override or key not in os.environ:
                os.environ[str(key)] = str(val)

    # stacks: at top level
    stacks = data.get("stacks")
    if isinstance(stacks, list) and stacks:
        stacks_str = ",".join(str(s) for s in stacks)
        if override or "_CODE_CREW_STACKS_PROFILE" not in os.environ:
            os.environ["_CODE_CREW_STACKS_PROFILE"] = stacks_str

    # llm: section — serialised as JSON into LLM_CONFIG for llm_factory to consume
    if "llm" in data and isinstance(data["llm"], dict):
        import json as _json
        if override or "LLM_CONFIG" not in os.environ:
            os.environ["LLM_CONFIG"] = _json.dumps(data["llm"])

    return data


def yaml_env_keys(path: Path) -> set[str]:
    """
    Return the set of os.environ keys that load_yaml_config(path) would set.
    Used by _switch_profile() to clean up when switching profiles.
    """
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return set()

    keys: set[str] = set()

    for section, mapping in _ENV_MAP.items():
        if section in data and isinstance(mapping, dict):
            keys |= _collect_env_keys(mapping)

    # Legacy env: section
    keys |= {str(k) for k in data.get("env", {})}

    if data.get("stacks"):
        keys.add("_CODE_CREW_STACKS_PROFILE")

    if data.get("llm"):
        keys.add("LLM_CONFIG")

    return keys
