"""
Code crew: virtual software development team for SDLC phases 13-19.

All agent instructions and task descriptions are loaded from OKF markdown files
in knowledge/agents/ and knowledge/tasks/. No prompts are hardcoded here.

Agent definitions are in code_crew/knowledge/agents/. See decisions/CREW-001-fullstack-engineer.md
for the architectural rationale behind the role set.

Knowledge bundle (ADDs, ADRs, role/function/stack docs) is loaded into memory
at startup via KnowledgeReaderTool — no runtime dependency on designs/SDLC/ or platform/ repos.
"""

import os
import warnings
from pathlib import Path

from crewai import Agent, Crew, Process, Task

from shared.bedrock import get_llm_for_tier
from shared.okf_loader import load_bundle_agents, load_bundle_tasks
from shared.tools import (
    ApiSpecTool,
    AskHumanTool,
    BDDTestRunnerTool,
    DoDCheckerTool,
    FigmaReaderTool,
    JiraSprintListTool,
    JiraViewTool,
    KnowledgeReaderTool,
    MemoryTool,
    PlatformShellTool,
    PythonREPLTool,
    WorkspaceReaderTool,
)

_KNOWLEDGE = Path(__file__).parent / "knowledge"


def _kickoff(crew: "Crew", inputs: dict) -> str:
    """Call crew.kickoff() with one automatic retry on the tool-call-as-final-output error.

    Some LLMs (NVIDIA Llama, others) occasionally return a ChatCompletionMessageFunctionCall
    object as the task's final output instead of a text string. CrewAI then fails to construct
    TaskOutput.raw (expects str). Rebuilding the crew resets the agent's conversation history
    and the retry almost always completes cleanly.
    ponytail: one retry is enough — two failures in a row means a real problem.
    """
    try:
        return str(crew.kickoff(inputs=inputs))
    except Exception as exc:
        if "Input should be a valid string" in str(exc) and "ChatCompletion" in str(exc):
            return str(crew.kickoff(inputs=inputs))
        raise


def _mcp_tools_for(agent_name: str) -> list:
    """Return MCPClientTool instances from connected servers available to this agent."""
    try:
        from shared.mcp_registry import MCPRegistry
        from shared.tools.mcp_tool import make_mcp_tools
        registry = MCPRegistry.get()
        result = []
        for server_name, mcp_tool in registry.tools_for_agent(agent_name):
            result.extend(make_mcp_tools(server_name, [mcp_tool]))
        return result
    except Exception:
        return []


def _make_tools(code_path: str = "", relay=None, jira_key: str = "") -> dict:
    """Create tool instances, optionally bound to a specific code_path (worktree)."""
    shell = PlatformShellTool()
    runner = BDDTestRunnerTool()
    if code_path:
        shell = PlatformShellTool(code_path=code_path)
        runner = BDDTestRunnerTool(code_path=code_path)
    return {
        "knowledge_reader": KnowledgeReaderTool(),
        "workspace_reader": WorkspaceReaderTool(),
        "api_spec": ApiSpecTool(),
        "dod_checker": DoDCheckerTool(),
        "figma_reader": FigmaReaderTool(),
        "jira_view": JiraViewTool(),
        "jira_list": JiraSprintListTool(),
        "platform_shell": shell,
        "python_repl": PythonREPLTool(),
        "bdd_runner": runner,
        "memory_tool": MemoryTool(),
        "ask_human": AskHumanTool(relay=relay, jira_key=jira_key),
    }


def build_agents(tools: dict) -> dict:
    """Build all agents from OKF files. Returns a dict keyed by agent name."""
    agents_dir = _KNOWLEDGE / "agents"
    ac = load_bundle_agents(agents_dir)

    kr = tools["knowledge_reader"]
    ws = tools["workspace_reader"]
    ap = tools["api_spec"]
    jv = tools["jira_view"]
    sh = tools["platform_shell"]
    pr = tools["python_repl"]
    br = tools["bdd_runner"]
    mm = tools["memory_tool"]
    dc = tools["dod_checker"]
    ah = tools["ask_human"]
    fr = tools["figma_reader"]

    def _agent(name: str, agent_tools: list, max_iter: int = 15) -> Agent:
        c = ac[name]
        return Agent(
            role=c.role,
            goal=c.goal,
            backstory=c.backstory,
            tools=agent_tools + _mcp_tools_for(name),
            llm=get_llm_for_tier(c.model),
            verbose=True,
            max_iter=max_iter,
            respect_context_window=True,
        )

    return {
        "scrum_master":      _agent("scrum_master",      [kr, dc, jv, mm]),
        "architect":         _agent("architect",         [kr, ws, jv, sh, ah]),
        "engineer":          _agent("engineer",          [kr, ws, ap, jv, sh, pr, ah], max_iter=25),
        "qa_lead":           _agent("qa_lead",           [kr, ws, jv, sh, br, pr, ah]),
        "security_lead":      _agent("security_lead",      [kr, ws, sh, pr], max_iter=25),
        "compliance_officer": _agent("compliance_officer", [kr, ws, jv], max_iter=20),
        "product_owner":     _agent("product_owner",     [kr, jv]),
        "devops_lead":       _agent("devops_lead",       [kr, ws, jv, sh, pr]),
        "release_engineer":  _agent("release_engineer",  [kr, ws, jv, sh]),
        "ux_lead":           _agent("ux_lead",           [fr, kr, ws, ah]),
    }


def _make_guardrail(signal: str, extra: str = ""):
    """Return a guardrail function that rejects output missing the required completion signal."""
    def guardrail(output) -> tuple[bool, str]:
        text = output.raw if hasattr(output, "raw") else str(output)
        if signal in text:
            return True, ""
        if "INCOMPLETE:" in text:
            return False, (
                f"Worker reported INCOMPLETE. Send them back with specific instructions "
                f"to resolve the blocker and complete the work. Required signal: '{signal}'."
            )
        msg = (
            f"Output does not contain the required completion signal '{signal}'. "
            f"The worker appears to have described a plan rather than executing the work. "
            f"Send them back to actually do the work and return '{signal}' when done."
        )
        if extra:
            msg += f" {extra}"
        return False, msg
    return guardrail


def _impl_guardrail(output) -> tuple[bool, str]:
    """Implementation task: require IMPLEMENTATION COMPLETE + FILES CHANGED block."""
    text = output.raw if hasattr(output, "raw") else str(output)
    if "IMPLEMENTATION COMPLETE" in text and "FILES CHANGED:" in text:
        return True, ""
    if "IMPLEMENTATION COMPLETE" in text:
        return False, (
            "Output has IMPLEMENTATION COMPLETE but is missing the 'FILES CHANGED:' block. "
            "Send the engineer back to list every file created or modified before completing."
        )
    if "INCOMPLETE:" in text:
        return False, (
            "Engineer reported INCOMPLETE. Send them back with specific instructions to "
            "resolve the blocker. If they have tried 3+ times with different approaches, "
            "output: ESCALATE TO HUMAN: <reason>."
        )
    return False, (
        "Output does not contain 'IMPLEMENTATION COMPLETE' and a 'FILES CHANGED:' block. "
        "The engineer appears to have planned work rather than executed it. "
        "Send them back to write the code, run the tests, and return with both signals."
    )


def build_tasks(agents: dict, sprint_input: dict, tasks_dir: Path | None = None) -> dict:
    """Build all tasks from OKF files. Returns a dict keyed by task name."""
    td = tasks_dir or (_KNOWLEDGE / "tasks")
    tc = load_bundle_tasks(td)
    ctx = _format_context(sprint_input)

    def task(
        name: str,
        agent_key: str,
        context_tasks: list | None = None,
        guardrail_fn=None,
    ) -> Task:
        t = Task(
            name=name,
            description=f"{ctx}\n\n{tc[name].description}",
            expected_output=tc[name].expected_output,
            agent=agents[agent_key],
            context=context_tasks or [],
        )
        if guardrail_fn is not None:
            t.guardrail = guardrail_fn
            t.guardrail_max_retries = 5
        return t

    _task_complete   = _make_guardrail("TASK COMPLETE")
    _devops_complete = _make_guardrail("DEVOPS COMPLETE", extra="'NO CHANGES NEEDED' is also accepted.")
    _bdd_approved    = _make_guardrail("BDD APPROVED")
    _release_done    = _make_guardrail("RELEASE NOTE COMPLETE")
    _staging_done    = _make_guardrail("STAGING VERIFIED",  extra="'STAGING FAILED' is also accepted — it means the check ran.")
    _smoke_done      = _make_guardrail("SMOKE PASSED",      extra="'SMOKE FAILED' is also accepted — it means the check ran.")

    sprint_planning  = task("sprint_planning_check", "scrum_master")
    arch_review      = task("architecture_review",   "architect",      [sprint_planning])
    scaffold_code    = task("scaffold_code",          "engineer",       [arch_review],                        _task_complete)
    scaffold_test    = task("scaffold_test",          "qa_lead",        [arch_review, scaffold_code],          _task_complete)
    bdd_authoring    = task("bdd_test_authoring",     "qa_lead",        [sprint_planning, arch_review, scaffold_test], _task_complete)
    bdd_po_review    = task("bdd_po_review",          "product_owner",  [bdd_authoring])
    bdd_arch_review  = task("bdd_arch_review",        "architect",      [bdd_authoring])
    bdd_final        = task("bdd_finalization",       "qa_lead",        [bdd_po_review, bdd_arch_review],     _bdd_approved)
    implementation   = task("implementation",          "engineer",       [arch_review, scaffold_code, bdd_final], _impl_guardrail)
    devops_coord     = task("devops_coordination",    "devops_lead",    [arch_review, implementation],        _devops_complete)
    code_review      = task("code_review",            "architect",          [implementation, devops_coord])
    sec_review       = task("security_review",         "security_lead",      [implementation, devops_coord, code_review])
    comp_review      = task("compliance_review",       "compliance_officer", [implementation, devops_coord, code_review, sec_review])
    dod_check        = task("dod_check",               "scrum_master",
                            [sprint_planning, arch_review, scaffold_code, scaffold_test,
                             bdd_authoring, bdd_final, implementation, devops_coord,
                             code_review, sec_review, comp_review])
    release_notes     = task("release_notes",         "release_engineer",   [dod_check],                     _release_done)
    promote_staging   = task("promote_staging",       "devops_lead",        [release_notes])
    staging_verif     = task("staging_verification",  "qa_lead",            [promote_staging],               _staging_done)
    launch_decision   = task("launch_decision",       "release_engineer",   [release_notes, staging_verif])
    smoke_test        = task("smoke_test",             "qa_lead",            [staging_verif],                 _smoke_done)

    return {
        "sprint_planning":      sprint_planning,
        "architecture_review":  arch_review,
        "scaffold_code":        scaffold_code,
        "scaffold_test":        scaffold_test,
        "bdd_authoring":        bdd_authoring,
        "bdd_po_review":        bdd_po_review,
        "bdd_arch_review":      bdd_arch_review,
        "bdd_finalization":     bdd_final,
        "implementation":       implementation,
        "devops_coordination":  devops_coord,
        "code_review":          code_review,
        "security_review":      sec_review,
        "compliance_review":    comp_review,
        "dod_check":            dod_check,
        "release_notes":        release_notes,
        "promote_staging":      promote_staging,
        "staging_verification": staging_verif,
        "launch_decision":      launch_decision,
        "smoke_test":           smoke_test,
    }


# Tasks where agents tend to plan rather than execute — a manager LLM drives
# the worker until work is actually done (files written, tests run, etc.)
# implementation uses standard manager (needs to judge whether a git diff shows
# real code vs a plan); others use fast manager (scaffolding/ops are simpler to verify).
MANAGED_TASKS = frozenset({
    "scaffold_code",
    "scaffold_test",
    "bdd_authoring",
    "bdd_finalization",
    "implementation",
    "devops_coordination",
    "release_notes",
    "promote_staging",
    "staging_verification",
    "smoke_test",
})
_STANDARD_MANAGER_TASKS = frozenset({"implementation"})


def _build_manager_agent(task_name: str) -> Agent:
    """Build a custom manager agent from the manager_engineer OKF definition."""
    ac = load_bundle_agents(_KNOWLEDGE / "agents")
    c = ac["manager_engineer"]
    tier = "standard" if task_name in _STANDARD_MANAGER_TASKS else "fast"
    return Agent(
        role=c.role,
        goal=c.goal,
        backstory=c.backstory,
        llm=get_llm_for_tier(tier),
        verbose=True,
    )


def build_single_task_crew(
    task_name: str,
    sprint_input: dict,
    code_path: str = "",
    relay=None,
) -> Crew:
    """
    Build a minimal crew for a single named task. Used by TicketFlow to run
    one task at a time so progress can be tracked and feedback injected between steps.

    Tasks in MANAGED_TASKS use Process.hierarchical with a custom manager agent that
    drives the worker until the required completion signal is present — rejecting plans
    and sending the agent back to do the actual work.  Guardrails on each task provide
    a second validation layer and trigger auto-retry on missing completion signals.
    """
    from shared.progress_guard import ProgressGuard

    jira_key = sprint_input.get("jira_key", "")
    tools = _make_tools(code_path, relay=relay, jira_key=jira_key)
    agents = build_agents(tools)
    tasks = build_tasks(agents, sprint_input)

    t = tasks[task_name]
    guard = ProgressGuard()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        if task_name in MANAGED_TASKS:
            return Crew(
                agents=[t.agent],   # only the assigned worker; manager delegates back to it
                tasks=[t],
                process=Process.hierarchical,
                manager_agent=_build_manager_agent(task_name),
                verbose=True,
                step_callback=guard,
            )
        return Crew(
            agents=list(agents.values()),
            tasks=[t],
            process=Process.sequential,
            verbose=True,
            step_callback=guard,
        )


def build_crew(sprint_input: dict, code_path: str = "") -> Crew:
    """
    Build the full sequential crew for a single sprint story.

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
        tasks["bdd_po_review"],
        tasks["bdd_arch_review"],
        tasks["bdd_finalization"],
        tasks["implementation"],
        tasks["devops_coordination"],
        tasks["code_review"],
        tasks["security_review"],
        tasks["dod_check"],
        tasks["release_notes"],
        tasks["promote_staging"],
        tasks["staging_verification"],
        tasks["launch_decision"],
        tasks["smoke_test"],
    ]
    return Crew(
        agents=list(agents.values()),
        tasks=task_order,
        process=Process.sequential,
        verbose=True,
    )


_DESIGN_TASK_AGENTS: dict[str, str] = {
    "design_requirements":     "architect",
    "design_add_draft":        "architect",
    "design_security_input":   "security_lead",
    "design_compliance_input": "compliance_officer",
    "design_chief_review":     "architect",
    "design_finalize":         "architect",
}


def build_design_single_task(
    task_name: str,
    design_input: dict,
    relay=None,
    extra_context: str = "",
) -> str:
    """
    Build and run a single design-flow task. Returns the output string.

    Used by DesignFlow to run tasks one at a time so the Chief Architect
    review loop can be managed at the Python level.
    """
    tools = _make_tools(relay=relay, jira_key=design_input.get("issue_key", ""))
    agents = build_agents(tools)
    td = _KNOWLEDGE / "tasks"
    tc = load_bundle_tasks(td)
    ctx = _format_design_context(design_input)
    if extra_context:
        ctx += extra_context

    agent_key = _DESIGN_TASK_AGENTS[task_name]
    t = Task(
        name=task_name,
        description=f"{ctx}\n\n{tc[task_name].description}",
        expected_output=tc[task_name].expected_output,
        agent=agents[agent_key],
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        crew = Crew(
            agents=[agents[agent_key]],
            tasks=[t],
            process=Process.sequential,
            verbose=True,
        )
        return _kickoff(crew, design_input)


def _resolved_designs_path() -> str:
    """Return the absolute designs directory path, or 'designs' as a default hint."""
    explicit = os.environ.get("DESIGNS_PATH", "").strip()
    if explicit:
        return explicit
    local = Path.cwd() / "designs"
    if local.exists():
        return str(local)
    return "designs"


def _designs_context_line() -> str:
    return f"**Designs directory**: `{_resolved_designs_path()}` — use this path for all file operations involving ADRs, ADDs, TMDs, DMDs, SOPs."


def _format_design_context(design_input: dict) -> str:
    acs = "\n".join(f"- {ac}" for ac in design_input.get("acceptance_criteria", []))
    structure = _load_project_structure()
    sections: list[str] = []
    skills = _load_active_skills()
    if skills:
        sections.append(skills)
    sections.append(
        f"## Requirement\n\n"
        f"**Issue key**: {design_input.get('issue_key', 'UNKNOWN')}\n"
        f"**Summary**: {design_input.get('issue_summary', '')}\n"
        f"**Requirement**: {design_input.get('requirement', '')}\n"
        f"{_designs_context_line()}\n\n"
        f"**Acceptance criteria**:\n{acs}"
    )
    raw = design_input.get("raw_ticket", "")
    if raw:
        sections.append(f"## Full ticket content\n\n{raw[:3000]}")
    if structure:
        sections.append(f"## Project structure\n\n{structure}")
    return "\n\n".join(sections)


def _format_context(sprint_input: dict) -> str:
    acs = "\n".join(f"- {ac}" for ac in sprint_input.get("acceptance_criteria", []))
    add_refs = ", ".join(sprint_input.get("add_refs", [])) or "none specified"
    user_context = sprint_input.get("user_context", "")
    comment_context = sprint_input.get("comment_context", "")
    human_feedback = sprint_input.get("human_feedback", "")
    sections: list[str] = []
    skills = _load_active_skills()
    if skills:
        sections.append(skills)
    arch_style = os.environ.get("ARCHITECTURE_STYLE", "").strip()
    sections.append(
        f"## Sprint context\n\n"
        f"**Jira key**: {sprint_input.get('jira_key', 'UNKNOWN')}\n"
        f"**Sprint goal**: {sprint_input.get('sprint_goal', '')}\n"
        f"**Story**: {sprint_input.get('story', '')}\n"
        f"**Figma**: {sprint_input.get('figma_url', '') or 'not provided'}\n"
        f"**HTML design**: {sprint_input.get('html_design_ref', '') or 'not provided'}\n"
        f"**Relevant ADDs**: {add_refs}\n"
        f"{_designs_context_line()}\n"
        + (f"**Architecture pattern**: {arch_style} — load `stacks/arch-{arch_style}.md` via knowledge_reader for layer rules\n" if arch_style else "")
        + f"\n**Acceptance criteria**:\n{acs}"
    )
    if comment_context:
        sections.append(f"## Context from Jira comments\n\n{comment_context}")
    if user_context:
        sections.append(user_context)
    if human_feedback:
        sections.append(human_feedback)
    structure = _load_project_structure()
    if structure:
        sections.append(f"## Project structure\n\n{structure}")
    return "\n\n".join(sections)


def _load_project_structure() -> str:
    """Load .code-crew/structure.md from cwd if present."""
    p = Path.cwd() / ".code-crew" / "structure.md"
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _skill_search_dirs() -> list[Path]:
    """Ordered skill search path: project → user → bundled."""
    return [
        Path.cwd() / ".code-crew" / "skills",
        Path.home() / ".code-crew" / "skills",
        _KNOWLEDGE / "skills",
    ]


def _find_skill(name: str) -> Path | None:
    for d in _skill_search_dirs():
        p = d / f"{name}.md"
        if p.exists():
            return p
    return None


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end >= 0:
            return text[end + 3:].strip()
    return text


def _load_active_skills() -> str:
    """Load skill content for names in CODE_CREW_SKILLS env var (comma-separated)."""
    raw = os.environ.get("CODE_CREW_SKILLS", "").strip()
    if not raw:
        return ""
    parts: list[str] = []
    for name in raw.split(","):
        name = name.strip()
        if not name:
            continue
        path = _find_skill(name)
        if not path:
            continue
        parts.append(_strip_frontmatter(path.read_text(encoding="utf-8").strip()))
    if not parts:
        return ""
    return f"## Active skills (follow these rules throughout this task)\n\n" + "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# UX flow
# ---------------------------------------------------------------------------

_UX_TASK_AGENTS: dict[str, str] = {
    "ux_spec":           "ux_lead",
    "ux_implementation": "engineer",
    "ux_review":         "ux_lead",
}


def build_ux_single_task(
    task_name: str,
    ux_input: dict,
    relay=None,
    extra_context: str = "",
) -> str:
    """Build and run a single UX-flow task. Returns the output string."""
    tools = _make_tools(relay=relay, jira_key=ux_input.get("issue_key", ""))
    agents = build_agents(tools)
    td = _KNOWLEDGE / "tasks"
    tc = load_bundle_tasks(td)
    ctx = _format_ux_context(ux_input)
    if extra_context:
        ctx += extra_context

    agent_key = _UX_TASK_AGENTS[task_name]
    t = Task(
        name=task_name,
        description=f"{ctx}\n\n{tc[task_name].description}",
        expected_output=tc[task_name].expected_output,
        agent=agents[agent_key],
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        crew = Crew(
            agents=[agents[agent_key]],
            tasks=[t],
            process=Process.sequential,
            verbose=True,
        )
        return _kickoff(crew, ux_input)


_VERIFY_TASK_AGENTS: dict[str, str] = {
    "verify_arch_scan":       "architect",
    "verify_security_scan":   "security_lead",
    "verify_compliance_scan": "compliance_officer",
    "verify_domain_scan":     "architect",
    "verify_chief_review":    "architect",
    "verify_report":          "scrum_master",
}

_DOMAIN_TASK_AGENTS: dict[str, str] = {
    "domain_flow_discovery": "architect",
    "domain_event_storming": "architect",
    "domain_synthesis":      "architect",
    "domain_extract":        "architect",
}


def build_verify_crew(project_root: str = "") -> Crew:
    """Build and return a sequential 5-task verification crew."""
    tools = _make_tools(code_path=project_root)
    agents = build_agents(tools)
    td = _KNOWLEDGE / "tasks"
    tc = load_bundle_tasks(td)

    structure = _load_project_structure()
    stacks = os.environ.get("CODE_CREW_STACKS", "")
    arch = os.environ.get("ARCHITECTURE_STYLE", "")
    compliance = os.environ.get("CODE_CREW_COMPLIANCE", "")
    ctx = (
        f"## Verification context\n\n"
        f"**Project root**: {project_root or '.'}\n"
        f"**Stacks**: {stacks or 'not set'}\n"
        f"**Architecture**: {arch or 'not set'}\n"
        f"**Compliance standards in scope**: {compliance or 'not set — check structure.md'}\n"
        f"{_designs_context_line()}\n"
    )
    if structure:
        ctx += f"\n## Project structure\n\n{structure}"

    skills = _load_active_skills()
    if skills:
        ctx = skills + "\n\n" + ctx

    def _vtask(name: str, context_tasks: list | None = None) -> Task:
        agent_key = _VERIFY_TASK_AGENTS[name]
        return Task(
            name=name,
            description=f"{ctx}\n\n{tc[name].description}",
            expected_output=tc[name].expected_output,
            agent=agents[agent_key],
            context=context_tasks or [],
        )

    arch_scan   = _vtask("verify_arch_scan")
    sec_scan    = _vtask("verify_security_scan")
    comp_scan   = _vtask("verify_compliance_scan")
    domain_scan = _vtask("verify_domain_scan")
    chief_rev   = _vtask("verify_chief_review",    [arch_scan, sec_scan, comp_scan, domain_scan])
    report      = _vtask("verify_report",           [arch_scan, sec_scan, comp_scan, domain_scan, chief_rev])

    all_agents = list({id(t.agent): t.agent for t in
                       [arch_scan, sec_scan, comp_scan, domain_scan, chief_rev, report]}.values())

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        return Crew(
            agents=all_agents,
            tasks=[arch_scan, sec_scan, comp_scan, domain_scan, chief_rev, report],
            process=Process.sequential,
            verbose=True,
        )


def build_explore_single_task(explore_input: dict, extra_context: str = "") -> str:
    """Run the LLM phase of /explore. Returns the raw output string."""
    tools = _make_tools()
    agents = build_agents(tools)
    td = _KNOWLEDGE / "tasks"
    tc = load_bundle_tasks(td)

    # Core detections
    stacks = explore_input.get("stacks", [])
    commands = explore_input.get("commands", {})
    ci_methods = explore_input.get("ci_methods", [])
    ci_workflows = explore_input.get("ci_workflows", {})
    terraform = explore_input.get("terraform", {})

    ctx = f"## Project: {explore_input.get('root_name', '.')}\n\n"
    ctx += f"**Phase 1 architecture**: {explore_input.get('arch_style', 'undetected')}\n"
    ctx += f"**Phase 1 migration tool**: {explore_input.get('migration_tool', 'undetected')}\n"
    ctx += f"**Phase 1 migration path**: {explore_input.get('migration_path', 'not detected')}\n"
    ctx += f"**Phase 1 test framework**: {explore_input.get('test_framework', 'not detected')}\n"
    ctx += f"**Phase 1 API doc standard**: {explore_input.get('api_doc', 'not detected')}"
    if explore_input.get("api_doc_path"):
        ctx += f" (at `{explore_input['api_doc_path']}`)"
    ctx += "\n"
    ctx += f"**Service dirs**: {', '.join(explore_input.get('svc_dirs', []))}\n"
    _comp_stds = explore_input.get("compliance_standards", [])
    if _comp_stds:
        ctx += f"**Phase 1 compliance standards detected**: {', '.join(_comp_stds)} — verify by reading designs/ and docs/\n"
    else:
        ctx += f"**Phase 1 compliance standards**: none detected — check designs/ and docs/ for HIPAA/SOC2/GDPR/CCPA/PCI-DSS/FIPS mentions\n"
    ctx += "\n"

    feature_dirs = explore_input.get("feature_dirs", [])
    test_dirs = explore_input.get("test_dirs", [])
    if feature_dirs:
        ctx += f"**BDD feature dirs**: {', '.join(feature_dirs)}\n"
    if test_dirs:
        ctx += f"**Detected test dirs**: {', '.join(test_dirs)}\n"
    ctx += "\n"

    if stacks:
        ctx += f"### Detected stacks (verify each)\n" + "\n".join(f"- {s}" for s in stacks) + "\n\n"

    if commands:
        ctx += "### Detected commands (verify source files exist)\n"
        ctx += "\n".join(f"- `{k}`: `{v}`" for k, v in commands.items()) + "\n\n"

    if ci_methods:
        ctx += "### Detected CI/CD methods (verify config files)\n"
        for m in ci_methods:
            detail = ci_workflows.get(m, "")
            ctx += f"- {m}" + (f": {detail}" if detail else "") + "\n"
        ctx += "\n"

    if terraform:
        ctx += "### Detected Terraform structure (verify by reading files)\n"
        if terraform.get("root"):
            ctx += f"- Root: `{terraform['root']}`\n"
        envs = terraform.get("environments", {})
        if envs:
            for env, layers in sorted(envs.items()):
                ctx += f"- Env `{env}`: {', '.join(layers)}\n"
        if terraform.get("apply_order"):
            ctx += f"- Apply order: {terraform['apply_order']}\n"
        if terraform.get("state_bucket"):
            ctx += f"- State bucket: `{terraform['state_bucket']}`\n"
        if terraform.get("state_region"):
            ctx += f"- State region: `{terraform['state_region']}`\n"
        if terraform.get("state_key_pattern"):
            ctx += f"- State key pattern: `{terraform['state_key_pattern']}`\n"
        if terraform.get("aws_profile"):
            ctx += f"- AWS profile: `{terraform['aws_profile']}`\n"
        modules = terraform.get("modules", [])
        if modules:
            ctx += f"- Modules ({len(modules)} in `{terraform.get('modules_path', 'ops/modules')}/`): {', '.join(modules[:15])}"
            if len(modules) > 15:
                ctx += f" … +{len(modules) - 15} more"
            ctx += "\n"
        ctx += "\n"

    if extra_context:
        ctx += extra_context

    t = Task(
        name="explore_scan",
        description=f"{ctx}\n\n{tc['explore_scan'].description}",
        expected_output=tc["explore_scan"].expected_output,
        agent=agents["architect"],
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        crew = Crew(
            agents=[agents["architect"]],
            tasks=[t],
            process=Process.sequential,
            verbose=True,
        )
        # inputs={} prevents CrewAI from treating {env}/{layer} in embedded
        # values (e.g. Terraform state key patterns) as template variables.
        # All context is already embedded in the task description via f-strings.
        result = crew.kickoff(inputs={})
    return str(result)


def build_domain_single_task(
    task_name: str,
    domain_input: dict,
    relay=None,
    extra_context: str = "",
) -> str:
    """Build and run a single domain-flow task. Returns the output string."""
    tools = _make_tools(relay=relay)
    agents = build_agents(tools)
    td = _KNOWLEDGE / "tasks"
    tc = load_bundle_tasks(td)

    methodology = os.environ.get("DOMAIN_METHODOLOGY", "event-storming")
    diagram_fmt = os.environ.get("DOMAIN_DIAGRAM_FORMAT", "mermaid")
    structure = _load_project_structure()
    sections: list[str] = []
    skills = _load_active_skills()
    if skills:
        sections.append(skills)
    sections.append(
        f"## Domain modeling context\n\n"
        f"**System**: {domain_input.get('system_name', 'not set')}\n"
        f"**Jira key**: {domain_input.get('issue_key', 'not set')}\n"
        f"**Methodology**: {methodology}\n"
        f"**Diagram format**: {diagram_fmt}\n"
        f"{_designs_context_line()}\n"
    )
    if structure:
        sections.append(f"## Project structure\n\n{structure}")
    ctx = "\n\n".join(sections)
    if extra_context:
        ctx += extra_context

    agent_key = _DOMAIN_TASK_AGENTS[task_name]
    t = Task(
        name=task_name,
        description=f"{ctx}\n\n{tc[task_name].description}",
        expected_output=tc[task_name].expected_output,
        agent=agents[agent_key],
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        crew = Crew(
            agents=[agents[agent_key]],
            tasks=[t],
            process=Process.sequential,
            verbose=True,
        )
        return _kickoff(crew, domain_input)


def build_domain_extract_crew(target_path: str = "") -> Crew:
    """Build a single-task crew that extracts a domain model from existing code."""
    tools = _make_tools(code_path=target_path)
    agents = build_agents(tools)
    td = _KNOWLEDGE / "tasks"
    tc = load_bundle_tasks(td)

    structure = _load_project_structure()
    ctx = (
        f"## Domain extract context\n\n"
        f"**Target path**: {target_path or '.'}\n"
        f"**Methodology**: {os.environ.get('DOMAIN_METHODOLOGY', 'event-storming')}\n"
    )
    if structure:
        ctx += f"\n## Project structure\n\n{structure}"

    t = Task(
        name="domain_extract",
        description=f"{ctx}\n\n{tc['domain_extract'].description}",
        expected_output=tc["domain_extract"].expected_output,
        agent=agents["architect"],
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        return Crew(
            agents=[agents["architect"]],
            tasks=[t],
            process=Process.sequential,
            verbose=True,
        )


def build_otm_scope_task(inventory: dict) -> Crew:
    """Return a single-task Crew that decides how to partition the project into OTM files."""
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    agents = build_agents(_make_tools())

    lines = ["## Project inventory\n"]
    if inventory.get("svc_dirs"):
        lines.append("### Source services (top-level directories)\n" +
                     "\n".join(f"- {d}" for d in inventory["svc_dirs"]))
    if inventory.get("cmd_entries"):
        lines.append("### Sub-executables (cmd/ entries)\n" +
                     "\n".join(f"- {e}" for e in inventory["cmd_entries"]))
    if inventory.get("infra_modules"):
        lines.append("### Infrastructure modules (Terraform ops/modules/)\n" +
                     "\n".join(f"- {m}" for m in inventory["infra_modules"]))
    if inventory.get("external_services"):
        lines.append("### External services detected in source\n" +
                     "\n".join(f"- {s}" for s in inventory["external_services"]))
    if inventory.get("stacks"):
        lines.append(f"### Active stacks\n{', '.join(inventory['stacks'])}")
    ctx = "\n\n".join(lines)

    t = Task(
        name="explore_otm_scope",
        description=f"{ctx}\n\n{tc['explore_otm_scope'].description}",
        expected_output=tc["explore_otm_scope"].expected_output,
        agent=agents["architect"],
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        return Crew(
            agents=[agents["architect"]],
            tasks=[t],
            process=Process.sequential,
            verbose=True,
        )


def build_otm_build_task(project: dict, inventory: dict) -> Crew:
    """Return a hierarchical Crew that generates a complete OTM YAML for one project scope.

    Uses a fast manager LLM to guide the Architect agent section-by-section,
    directing it to read key source files via workspace_reader before each section.
    """
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    agents = build_agents(_make_tools())

    stacks = inventory.get("stacks", [])
    structure = _load_project_structure()

    ctx_lines = [
        f"## OTM project scope\n\n"
        f"**Project id**: {project['id']}\n"
        f"**Project name**: {project['name']}\n"
        f"**Description**: {project['description']}\n\n"
        f"**Components in scope**: {', '.join(project['components'])}\n\n"
        f"**Active stacks**: {', '.join(stacks)}"
    ]

    if inventory.get("infra_modules"):
        ctx_lines.append(
            "**Infrastructure modules (Terraform ops/modules/)**: "
            + ", ".join(inventory["infra_modules"])
        )

    if inventory.get("key_files"):
        by_type: dict[str, list[str]] = {}
        for f in inventory["key_files"]:
            kind = f.get("type", "other")
            by_type.setdefault(kind, []).append(f["path"])
        lines = ["## Key files to read (use workspace_reader on each before the relevant section)\n"]
        for kind, paths in by_type.items():
            lines.append(f"**{kind}**:\n" + "\n".join(f"- {p}" for p in paths))
        ctx_lines.append("\n".join(lines))

    if structure:
        ctx_lines.append(f"## Project structure\n\n{structure}")

    ctx = "\n\n".join(ctx_lines)

    t = Task(
        name="explore_otm_build",
        description=f"{ctx}\n\n{tc['explore_otm_build'].description}",
        expected_output=tc["explore_otm_build"].expected_output,
        agent=agents["architect"],
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        return Crew(
            agents=[agents["architect"]],
            tasks=[t],
            process=Process.hierarchical,
            manager_llm=get_llm_for_tier("fast"),
            verbose=True,
        )


def _format_ux_context(ux_input: dict) -> str:
    acs = "\n".join(f"- {ac}" for ac in ux_input.get("acceptance_criteria", []))
    structure = _load_project_structure()
    sections: list[str] = []
    skills = _load_active_skills()
    if skills:
        sections.append(skills)
    sections.append(
        f"## UX context\n\n"
        f"**Issue key**: {ux_input.get('issue_key', 'UNKNOWN')}\n"
        f"**Summary**: {ux_input.get('issue_summary', '')}\n"
        f"**Figma URL**: {ux_input.get('figma_url', '') or 'not provided — ask human'}\n"
        f"**Stack**: {ux_input.get('stack', 'not detected')}\n\n"
        f"**Acceptance criteria**:\n{acs}"
    )
    if structure:
        sections.append(f"## Project structure\n\n{structure}")
    return "\n\n".join(sections)
