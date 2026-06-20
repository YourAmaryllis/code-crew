"""
Code crew: virtual software development team for SDLC phases 13-19.

All agent instructions and task descriptions are loaded from OKF markdown files
in knowledge/agents/ and knowledge/tasks/. No prompts are hardcoded here.

Knowledge bundle (ADDs, ADRs, SDLC role/function/stack docs) is loaded into memory
at startup via KnowledgeReaderTool — no runtime dependency on designs/ or platform/ repos.
"""

from pathlib import Path

from crewai import Agent, Crew, Process, Task

from shared.bedrock import get_llm_for_tier
from shared.okf_loader import load_bundle_agents, load_bundle_tasks
from shared.tools import (
    BDDTestRunnerTool,
    DoDCheckerTool,
    JiraSprintListTool,
    JiraViewTool,
    KnowledgeReaderTool,
    MemoryTool,
    PlatformShellTool,
    PythonREPLTool,
    WorkspaceReaderTool,
)

_KNOWLEDGE = Path(__file__).parent / "knowledge"


def _make_tools(code_path: str = "") -> dict:
    """Create tool instances, optionally bound to a specific code_path (worktree)."""
    shell = PlatformShellTool()
    runner = BDDTestRunnerTool()
    if code_path:
        shell = PlatformShellTool(code_path=code_path)
        runner = BDDTestRunnerTool(code_path=code_path)
    return {
        "knowledge_reader": KnowledgeReaderTool(),
        "workspace_reader": WorkspaceReaderTool(),
        "dod_checker": DoDCheckerTool(),
        "jira_view": JiraViewTool(),
        "jira_list": JiraSprintListTool(),
        "platform_shell": shell,
        "python_repl": PythonREPLTool(),
        "bdd_runner": runner,
        "memory_tool": MemoryTool(),
    }


def build_agents(tools: dict) -> dict:
    """Build all agents from OKF files. Returns a dict keyed by agent name."""
    agents_dir = _KNOWLEDGE / "agents"
    ac = load_bundle_agents(agents_dir)

    kr = tools["knowledge_reader"]
    ws = tools["workspace_reader"]
    jv = tools["jira_view"]
    sh = tools["platform_shell"]
    pr = tools["python_repl"]
    br = tools["bdd_runner"]
    mm = tools["memory_tool"]
    dc = tools["dod_checker"]

    def _agent(name: str, agent_tools: list) -> Agent:
        c = ac[name]
        return Agent(
            role=c.role,
            goal=c.goal,
            backstory=c.backstory,
            tools=agent_tools,
            llm=get_llm_for_tier(c.model),
            verbose=True,
            max_iter=15,
        )

    return {
        "scrum_master":      _agent("scrum_master",      [kr, dc, jv, mm]),
        "tech_lead":         _agent("tech_lead",         [kr, ws, jv, sh]),
        "backend_developer": _agent("backend_developer", [kr, ws, jv, sh, pr]),
        "frontend_developer":_agent("frontend_developer",[kr, ws, jv, sh, pr]),
        "qa_engineer":       _agent("qa_engineer",       [kr, ws, jv, sh, br, pr]),
        "security_reviewer": _agent("security_reviewer", [kr, ws, sh, pr]),
    }


def build_tasks(agents: dict, sprint_input: dict, tasks_dir: Path | None = None) -> dict:
    """Build all tasks from OKF files. Returns a dict keyed by task name."""
    td = tasks_dir or (_KNOWLEDGE / "tasks")
    tc = load_bundle_tasks(td)
    ctx = _format_context(sprint_input)

    def task(name: str, agent_key: str, context_tasks: list | None = None) -> Task:
        return Task(
            name=name,
            description=f"{ctx}\n\n{tc[name].description}",
            expected_output=tc[name].expected_output,
            agent=agents[agent_key],
            context=context_tasks or [],
        )

    sprint_planning   = task("sprint_planning_check", "scrum_master")
    arch_review       = task("architecture_review",   "tech_lead",   [sprint_planning])
    scaffold_code     = task("scaffold_code",          "backend_developer", [arch_review])
    scaffold_test     = task("scaffold_test",          "qa_engineer", [arch_review, scaffold_code])
    bdd_authoring     = task("bdd_test_authoring",     "qa_engineer", [sprint_planning, arch_review, scaffold_test])
    backend_impl      = task("backend_implementation", "backend_developer", [arch_review, scaffold_code, bdd_authoring])
    frontend_impl     = task("frontend_implementation","frontend_developer",[arch_review, scaffold_code, bdd_authoring])
    code_review       = task("code_review",            "tech_lead",   [backend_impl, frontend_impl])
    sec_review        = task("security_review",        "security_reviewer", [backend_impl, frontend_impl, code_review])
    dod_check         = task("dod_check",              "scrum_master",
                             [sprint_planning, arch_review, scaffold_code, scaffold_test,
                              bdd_authoring, backend_impl, frontend_impl, code_review, sec_review])

    return {
        "sprint_planning": sprint_planning,
        "architecture_review": arch_review,
        "scaffold_code": scaffold_code,
        "scaffold_test": scaffold_test,
        "bdd_authoring": bdd_authoring,
        "backend_implementation": backend_impl,
        "frontend_implementation": frontend_impl,
        "code_review": code_review,
        "security_review": sec_review,
        "dod_check": dod_check,
    }


def build_single_task_crew(task_name: str, sprint_input: dict, code_path: str = "") -> Crew:
    """
    Build a minimal crew for a single named task. Used by TicketFlow to run
    one task at a time so progress can be tracked and feedback injected between steps.
    """
    tools = _make_tools(code_path)
    agents = build_agents(tools)
    tasks = build_tasks(agents, sprint_input)

    t = tasks[task_name]
    return Crew(
        agents=list(agents.values()),
        tasks=[t],
        process=Process.sequential,
        verbose=True,
    )


def build_crew(sprint_input: dict, code_path: str = "") -> Crew:
    """
    Build the full 10-task sequential crew for a single sprint story.

    Kept for backward compatibility with `code-crew run --jira`.
    New code should prefer TicketFlow + build_single_task_crew.
    """
    tools = _make_tools(code_path)
    agents = build_agents(tools)
    tasks = build_tasks(agents, sprint_input)

    task_order = [
        tasks["sprint_planning"],
        tasks["architecture_review"],
        tasks["scaffold_code"],
        tasks["scaffold_test"],
        tasks["bdd_authoring"],
        tasks["backend_implementation"],
        tasks["frontend_implementation"],
        tasks["code_review"],
        tasks["security_review"],
        tasks["dod_check"],
    ]
    return Crew(
        agents=list(agents.values()),
        tasks=task_order,
        process=Process.sequential,
        verbose=True,
    )


def _format_context(sprint_input: dict) -> str:
    acs = "\n".join(f"- {ac}" for ac in sprint_input.get("acceptance_criteria", []))
    add_refs = ", ".join(sprint_input.get("add_refs", [])) or "none specified"
    user_context = sprint_input.get("user_context", "")
    comment_context = sprint_input.get("comment_context", "")
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
    if comment_context:
        sections.append(f"## Context from Jira comments\n\n{comment_context}")
    if user_context:
        sections.append(user_context)
    return "\n\n".join(sections)
