"""
Code crew: virtual software development team for SDLC phases 13-19.

All agent instructions and task descriptions are loaded from OKF markdown files
in knowledge/agents/ and knowledge/tasks/. No prompts are hardcoded here.

Knowledge bundle (tools/knowledge/) is loaded into memory at startup — no runtime
dependency on designs/ or platform/ repos.
"""

from pathlib import Path

from crewai import Agent, Crew, Process, Task

from shared.bedrock import get_fast_llm, get_llm
from shared.okf_loader import load_bundle_agents, load_bundle_tasks
from shared.tools import (
    BDDTestRunnerTool,
    DoDCheckerTool,
    JiraSprintListTool,
    JiraViewTool,
    MemoryTool,
    PlatformShellTool,
    PythonREPLTool,
    SOPReaderTool,
)

_KNOWLEDGE = Path(__file__).parent / "knowledge"

# --- Tools (knowledge bundle pre-loaded at import time) ---
sop_reader = SOPReaderTool()
dod_checker = DoDCheckerTool()
jira_view = JiraViewTool()
jira_list = JiraSprintListTool()
platform_shell = PlatformShellTool()
python_repl = PythonREPLTool()
bdd_runner = BDDTestRunnerTool()
memory_tool = MemoryTool()


def build_crew(sprint_input: dict) -> Crew:
    """
    Build the code crew for a single sprint story.

    sprint_input keys:
      jira_key            - e.g. "LOOPLAT-72"
      story               - user story text ("As a ...")
      acceptance_criteria - list of AC strings
      sprint_goal         - one-sentence sprint goal
      figma_url           - Figma design link (required for frontend tasks)
      add_refs            - list of ADD names relevant to this story
    """
    agents_dir = _KNOWLEDGE / "agents"
    tasks_dir = _KNOWLEDGE / "tasks"

    ac = load_bundle_agents(agents_dir)
    tc = load_bundle_tasks(tasks_dir)

    # --- Agents (OKF backstory + role + goal; no hardcoded strings) ---

    scrum_master = Agent(
        role=ac["scrum_master"].role,
        goal=ac["scrum_master"].goal,
        backstory=ac["scrum_master"].backstory,
        tools=[sop_reader, dod_checker, jira_view, memory_tool],
        llm=get_fast_llm(),
        verbose=True,
    )

    tech_lead = Agent(
        role=ac["tech_lead"].role,
        goal=ac["tech_lead"].goal,
        backstory=ac["tech_lead"].backstory,
        tools=[sop_reader, jira_view, platform_shell],
        llm=get_llm(),
        verbose=True,
    )

    backend_developer = Agent(
        role=ac["backend_developer"].role,
        goal=ac["backend_developer"].goal,
        backstory=ac["backend_developer"].backstory,
        tools=[sop_reader, jira_view, platform_shell, python_repl],
        llm=get_llm(),
        verbose=True,
    )

    frontend_developer = Agent(
        role=ac["frontend_developer"].role,
        goal=ac["frontend_developer"].goal,
        backstory=ac["frontend_developer"].backstory,
        tools=[sop_reader, jira_view, platform_shell, python_repl],
        llm=get_llm(),
        verbose=True,
    )

    qa_engineer = Agent(
        role=ac["qa_engineer"].role,
        goal=ac["qa_engineer"].goal,
        backstory=ac["qa_engineer"].backstory,
        tools=[sop_reader, jira_view, platform_shell, bdd_runner, python_repl],
        llm=get_llm(),
        verbose=True,
    )

    security_reviewer = Agent(
        role=ac["security_reviewer"].role,
        goal=ac["security_reviewer"].goal,
        backstory=ac["security_reviewer"].backstory,
        tools=[sop_reader, platform_shell, python_repl],
        llm=get_llm(),
        verbose=True,
    )

    # --- Tasks (OKF description + expected_output; sprint_input injected as context) ---

    context_header = _format_context(sprint_input)

    sprint_planning = Task(
        description=f"{context_header}\n\n{tc['sprint_planning_check'].description}",
        expected_output=tc["sprint_planning_check"].expected_output,
        agent=scrum_master,
    )

    arch_review = Task(
        description=f"{context_header}\n\n{tc['architecture_review'].description}",
        expected_output=tc["architecture_review"].expected_output,
        agent=tech_lead,
        context=[sprint_planning],
    )

    bdd_authoring = Task(
        description=f"{context_header}\n\n{tc['bdd_test_authoring'].description}",
        expected_output=tc["bdd_test_authoring"].expected_output,
        agent=qa_engineer,
        context=[sprint_planning, arch_review],
    )

    backend_impl = Task(
        description=f"{context_header}\n\n{tc['backend_implementation'].description}",
        expected_output=tc["backend_implementation"].expected_output,
        agent=backend_developer,
        context=[arch_review, bdd_authoring],
    )

    frontend_impl = Task(
        description=f"{context_header}\n\n{tc['frontend_implementation'].description}",
        expected_output=tc["frontend_implementation"].expected_output,
        agent=frontend_developer,
        context=[arch_review, bdd_authoring],
    )

    sec_review = Task(
        description=f"{context_header}\n\n{tc['security_review'].description}",
        expected_output=tc["security_review"].expected_output,
        agent=security_reviewer,
        context=[backend_impl, frontend_impl],
    )

    dod_check = Task(
        description=f"{context_header}\n\n{tc['dod_check'].description}",
        expected_output=tc["dod_check"].expected_output,
        agent=scrum_master,
        context=[sprint_planning, arch_review, bdd_authoring, backend_impl, frontend_impl, sec_review],
    )

    return Crew(
        agents=[scrum_master, tech_lead, qa_engineer, backend_developer, frontend_developer, security_reviewer],
        tasks=[sprint_planning, arch_review, bdd_authoring, backend_impl, frontend_impl, sec_review, dod_check],
        process=Process.sequential,
        verbose=True,
    )


def _format_context(sprint_input: dict) -> str:
    acs = "\n".join(f"- {ac}" for ac in sprint_input.get("acceptance_criteria", []))
    add_refs = ", ".join(sprint_input.get("add_refs", [])) or "none specified"
    user_context = sprint_input.get("user_context", "")
    sections = [
        f"## Sprint context\n\n"
        f"**Jira key**: {sprint_input.get('jira_key', 'UNKNOWN')}\n"
        f"**Sprint goal**: {sprint_input.get('sprint_goal', '')}\n"
        f"**Story**: {sprint_input.get('story', '')}\n"
        f"**Figma**: {sprint_input.get('figma_url', '') or 'not provided'}\n"
        f"**HTML design**: {sprint_input.get('html_design_ref', '') or 'not provided'}\n"
        f"**Relevant ADDs**: {add_refs}\n\n"
        f"**Acceptance criteria**:\n{acs}",
    ]
    if user_context:
        sections.append(user_context)
    return "\n\n".join(sections)
