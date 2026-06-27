"""
Sprint planning: list sprint tickets via Jira REST API, fetch each one,
analyze dependencies (explicit + LLM-inferred), and produce execution waves.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
import urllib.parse
import base64
from pathlib import Path

from crewai import LLM

from shared.jira_client import JiraTicket, MissingACError, MissingStoryError, fetch

_PROMPT_PATH = (
    Path(__file__).parent.parent
    / "code_crew" / "knowledge" / "prompts" / "plan_sprint.md"
)


# ---------------------------------------------------------------------------
# Jira REST API ticket listing
# ---------------------------------------------------------------------------

def list_sprint_ticket_keys(
    project: str,
    sprint_name: str = "",
    jira_url: str = "",
    jira_user: str = "",
    jira_token: str = "",
) -> list[str]:
    """Return Jira issue keys for open tickets in the active (or named) sprint."""
    base_url = (jira_url or os.environ.get("JIRA_URL", "")).rstrip("/")
    user = jira_user or os.environ.get("JIRA_USER", "")
    token = jira_token or os.environ.get("JIRA_TOKEN", "")

    if not (base_url and user and token):
        raise RuntimeError(
            "Jira REST API credentials required for --sprint mode.\n"
            "Set JIRA_URL, JIRA_USER, JIRA_TOKEN in ~/.code-crew/config.\n"
            "Or pass ticket keys directly: code-crew sprint --jira KEY1 KEY2 ..."
        )

    sprint_clause = (
        f'AND sprint = "{sprint_name}"' if sprint_name else "AND sprint in openSprints()"
    )
    jql = f'project = {project} {sprint_clause} AND status != Done ORDER BY priority ASC'
    url = f"{base_url}/rest/api/3/search/jql?{urllib.parse.urlencode({'jql': jql, 'fields': 'summary,status', 'maxResults': '100'})}"

    credentials = base64.b64encode(f"{user}:{token}".encode()).decode()
    req = urllib.request.Request(url, headers={
        "Authorization": f"Basic {credentials}",
        "Accept": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        raise RuntimeError(f"Jira REST API error: {exc}") from exc

    return [issue["key"] for issue in data.get("issues", [])]


# ---------------------------------------------------------------------------
# Sprint planning
# ---------------------------------------------------------------------------

def fetch_sprint_tickets(keys: list[str]) -> tuple[list[JiraTicket], list[dict]]:
    """
    Fetch and extract all tickets. Returns (ready_tickets, skipped).
    skipped entries: {"key": ..., "reason": ...}
    """
    ready: list[JiraTicket] = []
    skipped: list[dict] = []
    for key in keys:
        try:
            ticket = fetch(key)
            ready.append(ticket)
        except (MissingStoryError, MissingACError) as exc:
            skipped.append({"key": key, "reason": str(exc).strip()})
        except RuntimeError as exc:
            skipped.append({"key": key, "reason": str(exc).strip()})
    return ready, skipped


def plan_execution_order(tickets: list[JiraTicket]) -> list[list[JiraTicket]]:
    """
    Analyse dependencies (explicit + LLM-inferred) and return execution waves.
    Each wave is a list of tickets that are independent of each other.
    """
    if not tickets:
        return []

    ticket_map = {t.key: t for t in tickets}
    known_keys = set(ticket_map.keys())

    # Explicit deps from Jira "depends" field (filtered to tickets in this sprint)
    deps: dict[str, set[str]] = {
        t.key: {d for d in t.depends if d in known_keys}
        for t in tickets
    }

    # LLM pass: infer implicit deps from summaries and stories
    if len(tickets) > 1:
        implicit = _infer_deps_llm(tickets, deps)
        for key, implicit_deps in implicit.items():
            if key in deps:
                deps[key] |= (implicit_deps & known_keys)

    return _topo_waves(ticket_map, deps)


def _infer_deps_llm(
    tickets: list[JiraTicket],
    explicit_deps: dict[str, set[str]],
) -> dict[str, set[str]]:
    """Ask the fast LLM to identify implicit dependencies from ticket context."""
    prompt_text = _load_prompt()
    summaries = "\n".join(
        f"- {t.key}: {t.summary} | Story: {t.story[:120] if t.story else 'n/a'}"
        for t in tickets
    )
    explicit_text = "\n".join(
        f"  {k} depends on: {', '.join(sorted(v)) or 'none'}"
        for k, v in sorted(explicit_deps.items())
    )
    user_msg = (
        f"Tickets in this sprint:\n{summaries}\n\n"
        f"Explicit dependencies already known:\n{explicit_text}\n\n"
        f"Identify any IMPLICIT dependencies not already listed."
    )

    llm = LLM(
        model=f"bedrock/{os.environ['BEDROCK_FAST_MODEL_ID']}",
        aws_region_name=os.environ.get("BEDROCK_REGION", "us-east-1"),
        temperature=0.0,
    )
    raw = llm.call(messages=[
        {"role": "system", "content": prompt_text},
        {"role": "user", "content": user_msg},
    ])

    return _parse_deps_json(raw if isinstance(raw, str) else str(raw))


def _load_prompt() -> str:
    text = _PROMPT_PATH.read_text()
    if text.startswith("---"):
        end = text.index("---", 3)
        text = text[end + 3:].lstrip()
    return text.strip()


def _parse_deps_json(content: str) -> dict[str, set[str]]:
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fence:
        content = fence.group(1)
    brace = re.search(r"\{.*\}", content, re.DOTALL)
    if brace:
        content = brace.group(0)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}
    # Expected: {"PROJ-NNN": ["PROJ-NNN"], "PROJ-NNN": []}
    return {k: set(v) for k, v in data.items() if isinstance(v, list)}


def _topo_waves(
    ticket_map: dict[str, JiraTicket],
    deps: dict[str, set[str]],
) -> list[list[JiraTicket]]:
    """Kahn's algorithm — returns tickets in dependency order as waves."""
    in_degree = {k: len(deps.get(k, set())) for k in ticket_map}
    waves: list[list[JiraTicket]] = []
    remaining = set(ticket_map.keys())

    while remaining:
        wave_keys = {k for k in remaining if in_degree.get(k, 0) == 0}
        if not wave_keys:
            # Circular or unresolvable — add all remaining in one wave
            wave_keys = remaining
        sorted_wave = sorted(wave_keys)
        waves.append([ticket_map[k] for k in sorted_wave])
        remaining -= wave_keys
        for k in remaining:
            resolved = deps.get(k, set()) & wave_keys
            in_degree[k] = max(0, in_degree.get(k, 0) - len(resolved))

    return waves
