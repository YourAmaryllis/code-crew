"""
CrewAI tool: query user-managed memory during a crew run.

Agents (primarily Scrum Master) can call this to retrieve user context
on a topic mid-run — e.g. "are there any blockers for PROJ-NNN?"
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class MemoryQueryInput(BaseModel):
    query: str = Field(
        description=(
            "Topic or keyword to search for in user memory. "
            "Examples: 'PROJ-NNN blockers', 'staging environment', 'auth decisions'."
        )
    )
    category: str = Field(
        default="",
        description="Optional category filter: decisions, blockers, env, jira, security, notes, always.",
    )


class MemoryTool(BaseTool):
    name: str = "memory_recall"
    description: str = (
        "Query user-managed memory for context relevant to a topic or Jira ticket. "
        "Use this to check for known blockers, team decisions, environment notes, "
        "or any context the user has saved with 'code-crew memory add'. "
        "Returns matching entries or empty if nothing relevant is stored."
    )
    args_schema: type[BaseModel] = MemoryQueryInput

    def _run(self, query: str, category: str = "") -> str:
        from shared.user_memory import UserMemory
        mem = UserMemory()
        terms = query.split()
        # Find Jira key in query (e.g. PROJ-NNN)
        import re
        jira_match = re.search(r"[A-Z]+-\d+", query.upper())
        jira_key = jira_match.group(0) if jira_match else ""

        entries = mem.recall(jira_key=jira_key, terms=terms)
        if category:
            entries = [e for e in entries if e.category == category]

        if not entries:
            return "No relevant memory entries found."

        lines = [f"Found {len(entries)} relevant memory entries:"]
        for e in entries:
            tag_str = f" [{', '.join(e.tags)}]" if e.tags else ""
            lines.append(f"- ({e.category}{tag_str}) {e.content}")
        return "\n".join(lines)
