"""
AskHumanTool — CrewAI tool that lets an agent ask the human a specific question.

The agent calls this tool when it has a concrete blocker (missing Figma link,
ambiguous requirement, unknown file path) and blocks until the human answers.
The answer is returned as the tool result and injected into the agent's context.
"""

from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class AskHumanInput(BaseModel):
    question: str = Field(
        description=(
            "A specific, concrete question for the human. "
            "Include all relevant context in the question so the human can answer "
            "without needing to look anything up. "
            "Examples: 'The Figma link in PROJ-NNN is missing — where can I find "
            "the UI design for the data dictionary modal?' or "
            "'The ADD mentions a separate audit table but the existing code uses a "
            "column on the datasets table — which pattern should I follow?'"
        )
    )


class AskHumanTool(BaseTool):
    name: str = "ask_human"
    description: str = (
        "Ask a human for specific information that is blocking your progress and "
        "cannot be found in the codebase, documents, or Jira. "
        "Use this when you have a concrete, answerable question — not for general "
        "guidance or when you're unsure how to proceed in general. "
        "The human will see your question and respond directly."
    )
    args_schema: type[BaseModel] = AskHumanInput

    relay: Any = None       # HumanRelay — injected at crew-build time
    jira_key: str = ""      # set per-run

    def _run(self, question: str) -> str:
        if self.relay is None:
            return "[ask_human] No relay configured — human input unavailable."
        return self.relay.ask(self.jira_key, question)
