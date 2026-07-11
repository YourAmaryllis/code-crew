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

# Canonical names the REPL accepts, mapped to the OKF agent file name.
AGENT_ALIASES: dict[str, str] = {
    "architect":          "architect",
    "arch":               "architect",
    "engineer":           "engineer",
    "eng":                "engineer",
    "security":           "security_lead",
    "security_lead":      "security_lead",
    "sec":                "security_lead",
    "qa":                 "qa_lead",
    "qa_lead":            "qa_lead",
    "compliance":         "compliance_officer",
    "compliance_officer": "compliance_officer",
    "devops":             "devops_lead",
    "devops_lead":        "devops_lead",
    "product_owner":      "product_owner",
    "po":                 "product_owner",
    "scrum_master":       "scrum_master",
    "sm":                 "scrum_master",
    "release":            "release_engineer",
    "release_engineer":   "release_engineer",
    "ux":                 "ux_lead",
    "ux_lead":            "ux_lead",
    "chief_architect":    "chief_architect",
    "chief":              "chief_architect",
}


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


def ask_agent(
    agent_name: str,
    question: str,
    sprint_context: str = "",
) -> str:
    """
    Ask a specific named crew agent a question.

    agent_name: canonical name or alias from AGENT_ALIASES
                (e.g. "architect", "arch", "security", "qa")
    """
    from shared.okf_loader import load_bundle_agents
    from code_crew.crews.core import _make_tools, _KNOWLEDGE, _mcp_tools_for

    canonical = AGENT_ALIASES.get(agent_name.lower())
    if not canonical:
        known = ", ".join(sorted(set(AGENT_ALIASES.values())))
        raise ValueError(f"Unknown agent '{agent_name}'. Known agents: {known}")

    # Load OKF definition
    agents_dir = _KNOWLEDGE / "agents"
    ac = load_bundle_agents(agents_dir)
    if canonical not in ac:
        raise ValueError(f"No OKF definition found for agent '{canonical}'")
    c = ac[canonical]

    # Build tools — use empty code_path (interactive session, no active sprint)
    tools = _make_tools("")
    kr = tools["knowledge_reader"]
    ws = tools["workspace_reader"]
    jv = tools["jira_view"]
    sh = tools["platform_shell"]
    pr = tools["python_repl"]
    mm = tools["memory_tool"]
    dc = tools["dod_checker"]

    _tool_map: dict[str, list] = {
        "architect":          [kr, ws, jv, sh],
        "chief_architect":    [kr, ws, jv, sh],
        "engineer":           [kr, ws, jv, sh, pr],
        "qa_lead":            [kr, ws, jv, sh, pr],
        "security_lead":      [kr, ws, sh, pr],
        "compliance_officer": [kr, ws, jv],
        "product_owner":      [kr, jv],
        "devops_lead":        [kr, ws, jv, sh, pr],
        "release_engineer":   [kr, ws, jv, sh],
        "scrum_master":       [kr, dc, jv, mm],
        "ux_lead":            [kr, ws],
    }
    agent_tools = _tool_map.get(canonical, [kr, ws]) + _mcp_tools_for(canonical)

    context_block = f"\n\n## Active sprint state\n\n{sprint_context}" if sprint_context else ""

    agent = Agent(
        role=c.role,
        goal=c.goal,
        backstory=c.backstory,
        tools=agent_tools,
        llm=get_llm_for_tier(c.model),
        verbose=False,
        max_iter=15,
        respect_context_window=True,
    )

    task = Task(
        description=f"{question}{context_block}",
        expected_output="A concise, accurate answer. Cite file paths or doc names when relevant.",
        agent=agent,
    )

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    return str(result).strip()
