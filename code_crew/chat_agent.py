"""
Conversational agent for the REPL chat mode.

Answers questions about the codebase, SDLC docs, and active sprint state.
Uses the fast Bedrock model and the workspace_reader + knowledge_reader tools
to load only what it needs, keeping context small.
"""

from __future__ import annotations

import os
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.tools import BaseTool

from shared.bedrock import get_llm_for_tier
from shared.tools import KnowledgeReaderTool, WorkspaceReaderTool


_SYSTEM = (
    "You are a helpful AI assistant embedded in a software development workflow. "
    "You can read files in the current project (workspace_reader) and SDLC/ADR/ADD docs "
    "(knowledge_reader). Answer questions about the codebase, architecture, and process. "
    "Be concise. When you read a file, quote the relevant section rather than the whole file."
)


def ask(
    question: str,
    sprint_context: str = "",
    extra_tools: list[BaseTool] | None = None,
) -> str:
    """
    Send a question to the chat agent and return the response.

    sprint_context: optional string describing the active sprint state,
                    injected so the agent can answer "why did code review fail?" etc.
    """
    tools: list[BaseTool] = [WorkspaceReaderTool(), KnowledgeReaderTool()]
    if extra_tools:
        tools.extend(extra_tools)

    context_block = ""
    if sprint_context:
        context_block = f"\n\n## Active sprint state\n\n{sprint_context}"

    agent = Agent(
        role="Development Assistant",
        goal="Answer developer questions accurately, using workspace and SDLC knowledge tools.",
        backstory=_SYSTEM,
        tools=tools,
        llm=get_llm_for_tier("fast"),
        verbose=False,
    )

    task = Task(
        description=f"{question}{context_block}",
        expected_output="A concise, accurate answer. Cite file paths or document names when relevant.",
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff()
    return str(result).strip()
