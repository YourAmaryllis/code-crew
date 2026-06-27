"""
CrewAI tool: read Jira issues via the jira CLI.

Read-only by default. Supports viewing tickets and listing sprint work.
Write operations (comment, transition) are gated behind explicit fields.
"""

import os
import subprocess

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


def _jira_project() -> str:
    return os.environ.get("JIRA_PROJECT", "PROJ")


class JiraViewInput(BaseModel):
    issue_key: str = Field(
        description=(
            "Jira issue key to view (e.g. 'PROJ-NNN' or 'CTO-11'). "
            "Returns full issue details: summary, description, acceptance criteria, status, assignee."
        )
    )


class JiraViewTool(BaseTool):
    name: str = "jira_view"
    description: str = (
        "View a Jira issue by key (e.g. PROJ-NNN). Returns the full issue details "
        "including summary, description, acceptance criteria, status, assignee, and labels. "
        "Use this to get the full story context, ACs, and design references for a ticket."
    )
    args_schema: type[BaseModel] = JiraViewInput

    def _run(self, issue_key: str) -> str:
        issue_key = issue_key.strip().upper()
        if not issue_key:
            return "ERROR: issue_key is required."
        try:
            result = subprocess.run(
                ["jira", "view", issue_key],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return f"ERROR (exit {result.returncode}): {result.stderr.strip()}"
            return result.stdout.strip() or "(no output)"
        except FileNotFoundError:
            return "ERROR: 'jira' CLI not found. Install via: brew install jira-cli"
        except subprocess.TimeoutExpired:
            return "ERROR: jira CLI timed out after 30 seconds"
        except Exception as e:
            return f"ERROR: {e}"


class JiraListInput(BaseModel):
    sprint: str = Field(
        default="active",
        description="Sprint name or 'active' (default) to list current sprint issues.",
    )
    assignee: str = Field(
        default="",
        description="Filter by assignee username. Leave empty for all.",
    )
    status: str = Field(
        default="",
        description="Filter by status (e.g. 'In Progress', 'To Do'). Leave empty for all.",
    )


class JiraSprintListTool(BaseTool):
    name: str = "jira_sprint_list"
    description: str = (
        "List Jira issues in the active sprint (or a named sprint). "
        "Optional filters: assignee, status. Use to understand sprint scope "
        "and find related issues."
    )
    args_schema: type[BaseModel] = JiraListInput

    def _run(self, sprint: str = "active", assignee: str = "", status: str = "") -> str:
        project = _jira_project()
        cmd = ["jira", "list", "--project", project]
        if sprint == "active":
            cmd += ["--current-sprint"]
        if assignee:
            cmd += ["--assignee", assignee]
        if status:
            cmd += ["--status", status]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return f"ERROR (exit {result.returncode}): {result.stderr.strip()}"
            return result.stdout.strip() or "(no issues found)"
        except FileNotFoundError:
            return "ERROR: 'jira' CLI not found."
        except subprocess.TimeoutExpired:
            return "ERROR: jira CLI timed out"
        except Exception as e:
            return f"ERROR: {e}"
