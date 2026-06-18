"""
Jira ticket fetcher for code-crew pre-flight.

Fetches a ticket via the jira CLI, then uses a fast LLM to extract user story
and acceptance criteria from the raw text — handles any Jira ticket format.
Refuses early (before the crew starts) if required fields are missing.

Extraction prompt: code/knowledge/prompts/extract_jira_ticket.md
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from crewai import LLM

_PROMPT_PATH = Path(__file__).parent.parent / "code_crew" / "knowledge" / "prompts" / "extract_jira_ticket.md"

# Project key used in Jira URLs (override via JIRA_PROJECT env)
_JIRA_PROJECT = os.environ.get("JIRA_PROJECT", "LOOPLAT")
_JIRA_BASE_URL = f"https://youramaryllis.atlassian.net/browse"


class MissingStoryError(Exception):
    """Raised when a Jira ticket has no user story."""


class MissingACError(Exception):
    """Raised when a Jira ticket has no acceptance criteria."""


@dataclass
class JiraTicket:
    key: str
    summary: str
    status: str
    story: str
    acceptance_criteria: list[str]
    sprint_goal: str
    figma_url: str
    html_design_ref: str
    add_refs: list[str]
    comment_context: str
    depends: list[str] = field(default_factory=list)
    raw: str = ""


def _run_jira_cli(issue_key: str) -> str:
    """Run `jira issue view <key>` and return raw stdout."""
    try:
        result = subprocess.run(
            ["jira", "view", issue_key],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise RuntimeError("'jira' CLI not found. Install with: brew install jira-cli")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Timed out fetching {issue_key} from Jira.")

    if result.returncode != 0:
        raise RuntimeError(
            f"Could not fetch {issue_key}.\n{result.stderr.strip()}\n"
            "Check: jira login, VPN, issue key spelling."
        )
    return result.stdout


def fetch(issue_key: str) -> JiraTicket:
    """Fetch a Jira ticket and extract fields via LLM. Raises on CLI errors or missing fields."""
    raw = _run_jira_cli(issue_key)
    summary = _extract_summary_line(raw) or issue_key
    status = _extract_status_line(raw) or "Unknown"
    depends = _extract_depends_line(raw)

    extracted = _extract_with_llm(raw)

    story = extracted.get("story") or ""
    acs = extracted.get("acceptance_criteria") or []
    sprint_goal = extracted.get("sprint_goal") or summary
    figma_url = extracted.get("figma_url") or ""
    html_design_ref = extracted.get("html_design_ref") or ""
    add_refs = extracted.get("add_refs") or []
    comment_context = extracted.get("comment_context") or ""

    if not story:
        raise MissingStoryError(
            f"\n{issue_key} is missing a user story.\n\n"
            f"Expected format in the Jira description:\n"
            f"  As a <role>, I want to <action> so that <outcome>.\n\n"
            f"Please update the ticket before running the crew:\n"
            f"  {_JIRA_BASE_URL}/{issue_key}"
        )

    if not acs:
        raise MissingACError(
            f"\n{issue_key} is missing Acceptance Criteria.\n\n"
            f"Expected format in the Jira description:\n"
            f"  Acceptance Criteria\n"
            f"  1. ...\n"
            f"  2. ...\n\n"
            f"Please update the ticket before running the crew:\n"
            f"  {_JIRA_BASE_URL}/{issue_key}"
        )

    return JiraTicket(
        key=issue_key,
        summary=summary,
        status=status,
        story=story,
        acceptance_criteria=acs,
        sprint_goal=sprint_goal,
        figma_url=figma_url,
        html_design_ref=html_design_ref,
        add_refs=add_refs,
        comment_context=comment_context,
        depends=depends,
        raw=raw,
    )


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

def _load_extraction_prompt() -> str:
    """Load the extraction prompt from the external OKF file (strip frontmatter)."""
    text = _PROMPT_PATH.read_text()
    # Strip YAML frontmatter block (--- ... ---)
    if text.startswith("---"):
        end = text.index("---", 3)
        text = text[end + 3:].lstrip()
    return text.strip()


def _extract_with_llm(raw_ticket: str) -> dict:
    """Call the fast LLM to extract story, ACs, sprint_goal, figma_url, add_refs."""
    system_prompt = _load_extraction_prompt()
    model_id = os.environ["BEDROCK_FAST_MODEL_ID"]
    region = os.environ.get("BEDROCK_REGION", "us-east-1")

    llm = LLM(
        model=f"bedrock/{model_id}",
        aws_region_name=region,
        temperature=0.0,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Extract from this Jira ticket:\n\n{raw_ticket}"},
    ]
    content = llm.call(messages=messages)
    return _parse_json_response(content if isinstance(content, str) else str(content))


def _parse_json_response(content: str) -> dict:
    """Parse JSON from the LLM response, tolerating markdown code fences."""
    # Strip ```json ... ``` or ``` ... ``` wrappers if present
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fence_match:
        content = fence_match.group(1)
    # Find first { ... } block
    brace_match = re.search(r"\{.*\}", content, re.DOTALL)
    if brace_match:
        content = brace_match.group(0)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------------------
# Lightweight field extractors (no regex story/AC parsing — LLM handles that)
# ---------------------------------------------------------------------------

def _extract_summary_line(raw: str) -> str:
    m = re.search(r"^summary:\s*(.+)$", raw, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _extract_status_line(raw: str) -> str:
    m = re.search(r"^status:\s*(.+)$", raw, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _extract_depends_line(raw: str) -> list[str]:
    m = re.search(r"^depends:\s*(.+)$", raw, re.MULTILINE)
    if not m:
        return []
    return re.findall(r"[A-Z]+-\d+", m.group(1))
