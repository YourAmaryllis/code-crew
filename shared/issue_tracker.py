"""
Issue tracker abstraction: Jira or Linear.

Routes to the right backend based on ISSUE_TRACKER env var (default: jira).
Provides a unified Ticket type and three operations:
  - get_ticket(key)
  - list_sprint_tickets(sprint_name) -> list[str] of keys
  - post_comment(key, body)

Jira: delegates to jira_client.py (jira CLI + LLM extraction).
Linear: delegates to the linear CLI (npm i -g @linear/linear).
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from shared.jira_client import JiraTicket, MissingACError, MissingStoryError
from shared.jira_client import fetch as _jira_fetch
from shared.sprint_planner import list_sprint_ticket_keys as _jira_list_sprint


# ---------------------------------------------------------------------------
# Unified ticket type (superset of fields from both trackers)
# ---------------------------------------------------------------------------

@dataclass
class Ticket:
    key: str
    summary: str
    status: str
    story: str
    acceptance_criteria: list[str]
    sprint_goal: str
    figma_url: str = ""
    html_design_ref: str = ""
    add_refs: list[str] = field(default_factory=list)
    comment_context: str = ""
    depends: list[str] = field(default_factory=list)
    raw: str = ""

    @classmethod
    def from_jira(cls, t: JiraTicket) -> "Ticket":
        return cls(
            key=t.key,
            summary=t.summary,
            status=t.status,
            story=t.story,
            acceptance_criteria=t.acceptance_criteria,
            sprint_goal=t.sprint_goal,
            figma_url=t.figma_url,
            html_design_ref=t.html_design_ref,
            add_refs=t.add_refs,
            comment_context=t.comment_context,
            depends=t.depends,
            raw=t.raw,
        )


class TrackerError(Exception):
    """Raised for issue tracker CLI or API errors."""


class MissingFieldError(TrackerError):
    """Raised when required ticket fields (story, ACs) are absent."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class IssueTrackerClient:
    """Routes to Jira or Linear based on ISSUE_TRACKER env var."""

    def __init__(self) -> None:
        self._tracker = os.environ.get("ISSUE_TRACKER", "jira").lower()
        self._project_key = os.environ.get("PROJECT_KEY", "")

    @property
    def tracker(self) -> str:
        return self._tracker

    def get_ticket(self, key: str) -> Ticket:
        if self._tracker == "linear":
            return self._linear_get(key)
        return self._jira_get(key)

    def list_sprint_tickets(self, sprint_name: str = "") -> list[str]:
        if self._tracker == "linear":
            return self._linear_list_sprint(sprint_name)
        return self._jira_list_sprint(sprint_name)

    def post_comment(self, key: str, body: str) -> None:
        if self._tracker == "linear":
            self._linear_comment(key, body)
        else:
            self._jira_comment(key, body)

    # ------------------------------------------------------------------
    # Jira backend
    # ------------------------------------------------------------------

    def _jira_get(self, key: str) -> Ticket:
        try:
            t = _jira_fetch(key)
            return Ticket.from_jira(t)
        except MissingStoryError as exc:
            raise MissingFieldError(str(exc)) from exc
        except MissingACError as exc:
            raise MissingFieldError(str(exc)) from exc
        except RuntimeError as exc:
            raise TrackerError(str(exc)) from exc

    def _jira_list_sprint(self, sprint_name: str) -> list[str]:
        try:
            return _jira_list_sprint(
                project=self._project_key,
                sprint_name=sprint_name,
            )
        except RuntimeError as exc:
            raise TrackerError(str(exc)) from exc

    def _jira_comment(self, key: str, body: str) -> None:
        result = subprocess.run(
            ["jira", "issue", "comment", "add", key, "--body", body],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise TrackerError(f"Failed to post Jira comment: {result.stderr.strip()}")

    # ------------------------------------------------------------------
    # Linear backend
    # ------------------------------------------------------------------

    def _linear_get(self, key: str) -> Ticket:
        _require_linear_cli()
        result = subprocess.run(
            ["linear", "issue", "view", key, "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise TrackerError(f"linear CLI error: {result.stderr.strip()}")
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise TrackerError(f"Could not parse linear output: {exc}") from exc
        return _linear_to_ticket(data)

    def _linear_list_sprint(self, sprint_name: str) -> list[str]:
        _require_linear_cli()
        args = ["linear", "issue", "list", "--json"]
        if sprint_name:
            args += ["--cycle", sprint_name]
        if self._project_key:
            args += ["--team", self._project_key]
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise TrackerError(f"linear CLI error: {result.stderr.strip()}")
        try:
            issues = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise TrackerError(f"Could not parse linear output: {exc}") from exc
        return [issue.get("identifier", "") for issue in issues if issue.get("identifier")]

    def _linear_comment(self, key: str, body: str) -> None:
        _require_linear_cli()
        result = subprocess.run(
            ["linear", "issue", "comment", key, "--body", body],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise TrackerError(f"Failed to post Linear comment: {result.stderr.strip()}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_linear_cli() -> None:
    result = subprocess.run(["which", "linear"], capture_output=True, text=True)
    if result.returncode != 0:
        raise TrackerError(
            "linear CLI not found. Install with: npm i -g @linear/linear\n"
            "Then authenticate: linear auth login"
        )


def _linear_to_ticket(data: dict) -> Ticket:
    """Map Linear JSON fields to a Ticket. Best-effort extraction."""
    description = data.get("description", "")
    story, acs = _parse_story_and_acs(description)
    return Ticket(
        key=data.get("identifier", ""),
        summary=data.get("title", ""),
        status=data.get("state", {}).get("name", ""),
        story=story,
        acceptance_criteria=acs,
        sprint_goal=data.get("title", ""),
        raw=json.dumps(data),
    )


def _parse_story_and_acs(description: str) -> tuple[str, list[str]]:
    """Extract user story and ACs from a description string (best-effort)."""
    import re
    story_match = re.search(r"As a .+?so that [^\n]+", description, re.DOTALL | re.IGNORECASE)
    story = story_match.group(0).strip() if story_match else ""

    ac_match = re.search(
        r"(?:acceptance criteria|ac)[:\s]*\n((?:\s*[-\d\.\*].+\n?)+)",
        description, re.IGNORECASE
    )
    acs: list[str] = []
    if ac_match:
        for line in ac_match.group(1).splitlines():
            stripped = re.sub(r"^\s*[-\d\.\*]+\s*", "", line).strip()
            if stripped:
                acs.append(stripped)
    return story, acs
