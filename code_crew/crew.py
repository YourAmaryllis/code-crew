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
    AsyncJobTool,
    AskHumanTool,
    BDDTestRunnerTool,
    CodeIndexTool,
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
        "code_index": CodeIndexTool(),
        "api_spec": ApiSpecTool(),
        "async_job": AsyncJobTool(),
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
    ci = tools["code_index"]
    ap = tools["api_spec"]
    cs = tools["async_job"]
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
        "architect":         _agent("architect",         [kr, ws, ci, jv, sh, ah]),
        "engineer":          _agent("engineer",          [kr, ws, ci, ap, jv, sh, pr, ah], max_iter=25),
        "qa_lead":           _agent("qa_lead",           [kr, ws, jv, sh, br, pr, ah, cs]),
        "security_lead":      _agent("security_lead",      [kr, ws, sh, pr], max_iter=25),
        "compliance_officer": _agent("compliance_officer", [kr, ws, jv], max_iter=20),
        "product_owner":     _agent("product_owner",     [kr, jv]),
        "devops_lead":       _agent("devops_lead",       [kr, ws, jv, sh, pr, cs]),
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


def _make_ci_guardrail(success_signal: str, fail_signal: str = ""):
    """Guardrail for CI tasks: accepts success_signal, fail_signal, or RUN_HANDLE: (async path)."""
    def guardrail(output) -> tuple[bool, str]:
        text = output.raw if hasattr(output, "raw") else str(output)
        if success_signal in text:
            return True, ""
        if fail_signal and fail_signal in text:
            return True, ""
        if "RUN_HANDLE:" in text:
            return True, ""
        if "INCOMPLETE:" in text:
            return False, (
                f"Worker reported INCOMPLETE. Send them back to resolve the blocker. "
                f"Required: '{success_signal}', '{fail_signal}', or a RUN_HANDLE: JSON line."
            )
        return False, (
            f"Output missing the required completion signal. Expected '{success_signal}', "
            f"'{fail_signal}', or a RUN_HANDLE: {{...}} line (async CI path). "
            "Send the worker back to complete the work or trigger the CI run and emit RUN_HANDLE."
        )
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
    _staging_done    = _make_ci_guardrail("STAGING VERIFIED",  fail_signal="STAGING FAILED")
    _smoke_done      = _make_ci_guardrail("SMOKE PASSED",      fail_signal="SMOKE FAILED")

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
_STANDARD_MANAGER_TASKS = frozenset({"implementation", "threat_gate"})


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


# ---------------------------------------------------------------------------
# Drift flow
# ---------------------------------------------------------------------------

_DRIFT_TASK_AGENTS: dict[str, str] = {
    "drift_assess":  "devops_lead",
    "drift_resolve": "devops_lead",
}


def build_drift_single_task(
    task_name: str,
    drift_input: dict,
    relay=None,
    extra_context: str = "",
) -> str:
    """Build and run a single drift-flow task. Returns the output string."""
    tools = _make_tools(relay=relay, jira_key="")
    agents = build_agents(tools)
    td = _KNOWLEDGE / "tasks"
    tc = load_bundle_tasks(td)
    ctx = _format_drift_context(drift_input)
    if extra_context:
        ctx += extra_context

    agent_key = _DRIFT_TASK_AGENTS[task_name]
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
        return _kickoff(crew, drift_input)


def _format_drift_context(drift_input: dict) -> str:
    structure = _load_project_structure()
    sections: list[str] = []
    skills = _load_active_skills()
    if skills:
        sections.append(skills)
    envs = ", ".join(drift_input.get("environments", ["dev", "staging", "prod"]))
    cats = ", ".join(drift_input.get("categories", ["terraform", "cicd", "monitoring", "config"]))
    header = (
        f"## Drift context\n\n"
        f"**Project root**: {drift_input.get('project_root', str(Path.cwd()))}\n"
        f"**Environments to check**: {envs}\n"
        f"**Categories to check**: {cats}\n"
    )
    focus = drift_input.get("focus", "")
    if focus:
        header += f"**Focus**: {focus}\n"
    sections.append(header)
    if structure:
        sections.append(f"## Project structure\n\n{structure}")
    return "\n\n".join(sections)


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


def _parse_arch_components(root: "Path") -> list[tuple[str, str, str]]:
    """Parse ## Architectural components table from structure.md.
    Returns list of (name, directory, type) tuples."""
    import re as _re
    structure_path = root / ".code-crew" / "structure.md"
    if not structure_path.exists():
        return []
    text = structure_path.read_text(errors="replace")
    # Find the ## Architectural components section
    section_m = _re.search(r"## Architectural components.*?\n(.*?)(?=\n## |\Z)", text, _re.DOTALL)
    if not section_m:
        return []
    section = section_m.group(1)
    # Parse markdown table rows: | name | `dir/` | type | notes |
    row_pat = _re.compile(r"^\|\s*([^|]+?)\s*\|\s*`?([^|`]+?)`?\s*\|\s*([^|]+?)\s*\|", _re.MULTILINE)
    results = []
    for m in row_pat.finditer(section):
        name = m.group(1).strip()
        directory = m.group(2).strip().rstrip("/")
        typ = m.group(3).strip().lower()
        if name.lower() in ("sad component", "---", "name"):
            continue
        results.append((name, directory, typ))
    return results


def _validate_tmd(f: "Path") -> tuple[bool, str]:
    """Check if a TMD YAML file is valid OTM. Returns (is_valid, reason)."""
    try:
        content = f.read_text(errors="replace")
    except OSError:
        return False, "file unreadable"
    content_lines = content.splitlines()
    json_line = next(
        (ln.strip() for ln in content_lines
         if ln.strip().startswith("{") and not ln.strip().startswith("#")), None
    )
    if json_line:
        return False, f"JSON dump (starts with `{json_line[:30]}`)"
    has_otm_key = any(
        ln.strip().startswith("otmVersion:") and not ln.strip().startswith("#")
        for ln in content_lines
    )
    if not has_otm_key:
        return False, "missing `otmVersion:` as YAML key (only found in comment or absent)"
    has_sections = any(
        k in content for k in ("components:", "threats:", "dataFlows:", "trustZones:")
    )
    if not has_sections:
        return False, "missing components/threats/dataFlows/trustZones sections"
    return True, "valid"


def _precheck_security(project_root: str) -> str:
    """Pre-validate TMD files and scan for hardcoded secrets in Python.
    Returns a context block injected into the security scan task."""
    import re as _re
    root = Path(project_root) if project_root else Path.cwd()
    lines: list[str] = ["## Pre-computed security facts (Python check — treat as authoritative)\n"]

    # TMD file validation
    tmd_dir = root / "designs" / "TMD"
    tmd_results: dict[str, tuple[bool, str]] = {}
    if tmd_dir.exists():
        lines.append("### TMD file validation")
        for f in sorted(tmd_dir.glob("*.yaml")):
            valid, reason = _validate_tmd(f)
            tmd_results[f.name] = (valid, reason)
            status = "VALID" if valid else f"**INVALID** — {reason}"
            lines.append(f"- designs/TMD/{f.name}: {status}")
    else:
        lines.append("### TMD file validation\n- designs/TMD/ does not exist — no threat models found")

    # Component → TMD mapping for deployable services
    components = _parse_arch_components(root)
    deployable = [(name, d, t) for name, d, t in components if t == "deployable service"]
    if deployable and tmd_dir.exists():
        lines.append("\n### Component TMD coverage (deployable services only)")
        for name, _dir, _typ in deployable:
            # Normalise name to expected TMD filename: lowercase, spaces/special→hyphens
            slug = _re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            match = next(
                (fname for fname in tmd_results
                 if slug in fname.lower() or fname.lower().replace(".yaml", "") in slug), None
            )
            if match:
                valid, reason = tmd_results[match]
                if valid:
                    lines.append(f"- {name}: TMD VALID — designs/TMD/{match}")
                else:
                    lines.append(f"- {name}: TMD INVALID — designs/TMD/{match} ({reason})")
            else:
                lines.append(f"- {name}: NO TMD FILE FOUND — no matching file in designs/TMD/")

    # Hardcoded secrets scan
    lines.append("\n### Hardcoded secrets scan")
    secret_pat = _re.compile(
        r'(secret|password|api_key|apikey|private_key)\s*[=:]\s*["\'][^"\']{8,}["\']',
        _re.IGNORECASE,
    )
    scan_dirs = [root / "portal" / "backend", root / "healthcare-calculator", root / "attestation"]
    findings: list[str] = []
    seen_findings: set[str] = set()
    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for src in scan_dir.rglob("*.go"):
            if any(p in src.parts for p in ("vendor", "node_modules", ".git")):
                continue
            try:
                for i, line in enumerate(src.read_text(errors="replace").splitlines(), 1):
                    if secret_pat.search(line):
                        rel = src.relative_to(root)
                        severity = "LOW" if src.name.endswith("_test.go") else "HIGH"
                        key = f"{rel}:{i}"
                        if key not in seen_findings:
                            seen_findings.add(key)
                            snippet = line.strip()[:80]
                            findings.append(f"- {rel}:{i}: `{snippet}` [{severity}]")
            except OSError:
                pass
    if findings:
        lines.extend(findings)
    else:
        lines.append("- No hardcoded secrets found in scanned Go source files")

    return "\n".join(lines)


def _precheck_architecture(project_root: str) -> str:
    """Pre-check SAD drift and ADR coverage in Python.
    Returns a context block injected into the arch scan task."""
    import re as _re
    root = Path(project_root) if project_root else Path.cwd()
    lines: list[str] = ["## Pre-computed architecture facts (Python check — treat as authoritative)\n"]

    # SAD vs structure.md comparison — use structure.md as ground truth, SAD as reference
    sad_file = root / "designs" / "SAD" / "SAD-3-Decomposition-View.md"
    components = _parse_arch_components(root)
    lines.append("### SAD decomposition drift")
    if not sad_file.exists():
        lines.append("- designs/SAD/SAD-3-Decomposition-View.md not found — SAD drift check skipped")
    elif not components:
        lines.append("- structure.md has no ## Architectural components table — SAD drift check skipped")
    else:
        sad_text = sad_file.read_text(errors="replace")
        sad_lower = sad_text.lower()
        external_types = {"test suite", "infrastructure", "infrastructure + test fixtures", "external"}
        for name, directory, typ in components:
            if typ in external_types:
                lines.append(f"- {name} ({typ}): not a deployable service — SAD entry not expected")
                continue
            code_exists = (root / directory).exists() if directory else False
            name_in_sad = name.lower() in sad_lower or directory.lower().replace("-", " ") in sad_lower
            if code_exists and name_in_sad:
                lines.append(f"- {name} → {directory}/: EXISTS in code and in SAD")
            elif code_exists and not name_in_sad:
                lines.append(f"- {name} → {directory}/: EXISTS in code but NOT IN SAD (newer than SAD)")
            elif not code_exists:
                lines.append(f"- {name} → {directory}/: directory MISSING from code")

        # SAD-referenced services not in structure.md (use known top-level service keywords)
        top_level_sad = {"s3 proxy", "s3proxy"}
        for keyword in top_level_sad:
            if keyword in sad_lower:
                found_in_structure = any(keyword in name.lower() or keyword in d.lower() for name, d, _ in components)
                if not found_in_structure:
                    lines.append(f"- '{keyword}' referenced in SAD but not in structure.md — may be missing from code")

    # ADR coverage check
    adr_dir = root / "designs" / "ADR"
    lines.append("\n### ADR coverage")
    if not adr_dir.exists():
        lines.append("- designs/ADR/ not found — ADR coverage check skipped")
    else:
        adr_files = [f.name for f in adr_dir.iterdir() if f.suffix == ".md"]
        decisions = {
            "HTTP framework (Go)": ["go", "golang", "gin", "echo", "gorilla", "chi", "entrypoint"],
            "Auth mechanism": ["auth", "mtls", "jwt", "keycloak", "okta"],
            "Cloud deployment": ["ecs", "terraform", "deploy", "infra", "cloud"],
            "Database": ["postgres", "database", "rds", "sql", "db"],
        }
        for decision, keywords in decisions.items():
            matches = [f for f in adr_files if any(k in f.lower() for k in keywords)]
            if matches:
                lines.append(f"- {decision}: COVERED — {', '.join(matches[:3])}")
            else:
                lines.append(f"- {decision}: NOT COVERED — no matching ADR found")
        lines.append(f"- Total ADR files: {len(adr_files)}")

    return "\n".join(lines)


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
    security_facts = _precheck_security(project_root)
    arch_facts = _precheck_architecture(project_root)
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

    def _vtask(name: str, context_tasks: list | None = None, extra_ctx: str = "") -> Task:
        agent_key = _VERIFY_TASK_AGENTS[name]
        task_ctx = f"{ctx}\n\n{extra_ctx}\n\n" if extra_ctx else f"{ctx}\n\n"
        return Task(
            name=name,
            description=f"{task_ctx}{tc[name].description}",
            expected_output=tc[name].expected_output,
            agent=agents[agent_key],
            context=context_tasks or [],
        )

    arch_scan   = _vtask("verify_arch_scan",       extra_ctx=arch_facts)
    sec_scan    = _vtask("verify_security_scan",   extra_ctx=security_facts)
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


_MAX_PRE_READ_BYTES = 3_000   # cap per file to keep context manageable
_MAX_PRE_READ_FILES = 4       # max files to pre-inject per project
_MAX_TERRAFORM_LINES = 60     # lines of terraform grep output to inject


def _pre_read(path: str, root: "Path | None" = None) -> str:
    """Read a file relative to root (or cwd), capped at _MAX_PRE_READ_BYTES."""
    import pathlib
    base = root or pathlib.Path.cwd()
    try:
        full = (base / path).resolve()
        content = full.read_text(encoding="utf-8", errors="replace")
        if len(content) > _MAX_PRE_READ_BYTES:
            content = content[:_MAX_PRE_READ_BYTES] + "\n... (truncated)"
        return content
    except Exception:
        return ""


def _terraform_grep(component_dirs: list[str], root: "Path | None" = None) -> str:
    """Grep ops/ Terraform for any reference to the component directories.

    Returns a compact summary so agents don't burn API calls searching Terraform.
    """
    import subprocess, pathlib, re
    base = root or pathlib.Path.cwd()
    ops_dir = base / "ops"
    if not ops_dir.exists():
        return ""

    # Build patterns from component directory names (handles fhir_proxy → fhir/proxy, fhir-proxy)
    patterns = []
    for d in component_dirs:
        patterns += [d, d.replace("_", "-"), d.replace("_", "/")]
    pattern = "|".join(set(patterns))

    try:
        result = subprocess.run(
            ["grep", "-rn", "--include=*.tf", "-E", pattern, str(ops_dir)],
            capture_output=True, text=True, timeout=10,
        )
        lines = result.stdout.splitlines()
        # Deduplicate and trim noise (long data lines, etc.)
        seen, out = set(), []
        for line in lines:
            key = re.sub(r'^\S+:\d+:', '', line).strip()
            if key and key not in seen and len(key) < 200:
                seen.add(key)
                out.append(line)
        return "\n".join(out[:_MAX_TERRAFORM_LINES])
    except Exception:
        return ""


def _build_threat_context(project: dict, inventory: dict, revision_feedback: str = "") -> str:
    """Build the shared context string injected into threat crew tasks.

    Pre-reads key files and runs a Terraform grep so agents spend tool calls on
    analysis, not rediscovering the same facts over and over.
    """
    import pathlib
    stacks = inventory.get("stacks", [])
    structure = _load_project_structure()
    root = pathlib.Path.cwd()

    ctx_lines = [
        # This banner is FIRST so the agent reads it before any investigation.
        "## !! READ THIS BEFORE TAKING ANY ACTION !!\n\n"
        "This context block already contains pre-scanned file contents and Terraform grep output.\n"
        "**Do NOT call workspace_reader or platform_shell to read or search for anything listed below.**\n"
        "Doing so wastes an iteration and risks hitting max_iter before the OTM is produced.\n"
        "Scroll to the 'Pre-scanned files' and 'Terraform deployment references' sections now.\n"
        "Only read files that are NOT already present in this context.",

        f"## Project scope\n\n"
        f"**Project id**: {project['id']}\n"
        f"**Project name**: {project['name']}\n"
        f"**Description**: {project['description']}\n\n"
        f"**Components in scope**: {', '.join(project['components'])}\n\n"
        f"**Active stacks**: {', '.join(stacks)}"
    ]

    if inventory.get("infra_modules"):
        ctx_lines.append(
            "**Infrastructure modules**: "
            + ", ".join(inventory["infra_modules"])
        )

    # ── Pre-read key files and inject content ────────────────────────────────
    # Filter to files belonging to THIS project's component directories, then
    # pre-read and inject so agents don't burn tool calls re-reading them.
    # Prefer dependency-manifests first; cap at _MAX_PRE_READ_FILES total.
    component_prefixes = tuple(c + "/" for c in project.get("components", []))
    pre_read_sections: list[str] = []
    key_files = inventory.get("key_files", [])
    # Sort: dependency-manifest before entry-point; skip terraform-module files
    # (Terraform info is already covered by the grep section below).
    _type_order = {"dependency-manifest": 0, "entry-point": 1}
    sorted_kfs = sorted(
        [kf for kf in key_files if kf.get("type") in _type_order],
        key=lambda k: _type_order[k.get("type", "entry-point")]
    )
    for kf in sorted_kfs:
        if len(pre_read_sections) >= _MAX_PRE_READ_FILES:
            break
        path = kf.get("path", "")
        ftype = kf.get("type", "")
        # Skip files that belong to other projects (filter by component directory)
        if component_prefixes and not path.startswith(component_prefixes):
            continue
        content = _pre_read(path, root)
        if content:
            pre_read_sections.append(f"### `{path}` ({ftype})\n```\n{content}\n```")
        # skip files that can't be read — not worth an empty stub entry

    if pre_read_sections:
        ctx_lines.append(
            "## Pre-scanned files (do NOT re-read these with workspace_reader)\n\n"
            + "\n\n".join(pre_read_sections)
        )

    # ── Terraform deployment references ──────────────────────────────────────
    # Use grep output stored by /explore if available; fall back to running grep now.
    # Either way the agent gets the raw lines — no fragile parsing needed.
    stored_grep = project.get("terraform_grep")  # set by _enrich_project_terraform
    tf_grep = stored_grep if stored_grep is not None else _terraform_grep(project["components"], root)

    if tf_grep:
        ctx_lines.append(
            "## Terraform deployment references (pre-scanned — do NOT re-grep ops/)\n\n"
            "Every Terraform line mentioning this service's components. "
            "Read these to determine the Terraform key, CPU/memory, ALB path, and env vars.\n\n"
            f"```\n{tf_grep}\n```"
        )
    else:
        ctx_lines.append(
            "## Terraform deployment references\n\n"
            "No explicit Terraform resource found for this service. "
            "Default deployment: **AWS ECS Fargate** (inferred from `ecs-deployment` stack). "
            "Do not search ops/ for this service."
        )

    if structure:
        ctx_lines.append(f"## Project structure\n\n{structure}")

    if revision_feedback:
        ctx_lines.append(
            f"## Manager revision feedback (address ALL items before producing the OTM)\n\n"
            f"{revision_feedback}"
        )

    return "\n\n".join(ctx_lines)


def build_threat_model_crew(project: dict, inventory: dict, revision_feedback: str = "") -> Crew:
    """Hierarchical crew: Security Lead (manager_agent) drives Architect (worker) to produce OTM.

    Security Lead asks architectural questions; Architect reads source files and reports.
    Together they work through the four OWASP TMP phases and produce a complete OTM YAML.
    """
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    ac = load_bundle_agents(_KNOWLEDGE / "agents")
    tools = _make_tools()
    agents = build_agents(tools)

    ctx = _build_threat_context(project, inventory, revision_feedback)

    # Worker: Architect reads the codebase and answers Security Lead's questions
    architect = agents["architect"]
    architect.max_iter = 35  # threat crew needs more iterations: trust zone phase + 4 OWASP phases + OTM production

    worker_task = Task(
        name="threat_build",
        description=f"{ctx}\n\n{tc['threat_build'].description}",
        expected_output=tc["threat_build"].expected_output,
        agent=architect,
        # No guardrail: the manager (Security Lead) decides when the work is done.
        # The revision loop in _run_threat handles missing/incomplete OTM output.
    )

    # Manager agent: Security Lead — drives the conversation through TM phases
    security_lead_def = ac["security_lead"]
    security_lead_manager = Agent(
        role=security_lead_def.role,
        goal=security_lead_def.goal,
        backstory=(
            security_lead_def.backstory
            + "\n\n---\n\n"
            + tc["threat_model"].description
        ),
        llm=get_llm_for_tier("powerful"),
        verbose=True,
    )

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        return Crew(
            agents=[architect],
            tasks=[worker_task],
            manager_agent=security_lead_manager,
            process=Process.hierarchical,
            verbose=True,
        )


def build_threat_patch_crew(project: dict, otm_text: str, revision_feedback: str) -> Crew:
    """Sequential crew: Architect patches specific gaps in an existing OTM YAML.

    Used for revisions — lighter than the full hierarchical re-run. The Architect
    only reads the files needed to fill the specific gaps the manager identified.
    """
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    agents = build_agents(_make_tools())

    ctx = (
        f"## Project\n\n"
        f"**Project id**: {project['id']}\n"
        f"**Project name**: {project['name']}\n\n"
        f"## Manager revision feedback (fix ALL of these)\n\n"
        f"{revision_feedback}\n\n"
        f"## Existing OTM YAML to patch\n\n"
        f"```yaml\n{otm_text}\n```"
    )

    architect = agents["architect"]
    architect.max_iter = 20

    patch_task = Task(
        name="threat_patch",
        description=f"{ctx}\n\n{tc['threat_patch'].description}",
        expected_output=tc["threat_patch"].expected_output,
        agent=architect,
    )

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        return Crew(
            agents=[architect],
            tasks=[patch_task],
            process=Process.sequential,
            verbose=True,
        )


def build_threat_gate_crew(project: dict, otm_text: str, stacks: list[str]) -> Crew:
    """Sequential crew: Manager reviews the OTM and either approves or lists gaps."""
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    agents = build_agents(_make_tools())

    compliance = os.environ.get("CODE_CREW_COMPLIANCE", "")
    gate_ctx = (
        f"**Project**: {project['name']} ({project['id']})\n"
        f"**Active stacks**: {', '.join(stacks)}\n"
        f"**Compliance**: {compliance or 'not specified'}\n\n"
        f"## OTM produced by Security Lead + Architect\n\n"
        f"```yaml\n{otm_text}\n```"
    )

    manager_agent = _build_manager_agent("threat_gate")
    gate_task = Task(
        name="threat_gate",
        description=f"{gate_ctx}\n\n{tc['threat_gate'].description}",
        expected_output=tc["threat_gate"].expected_output,
        agent=manager_agent,
    )

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        return Crew(
            agents=[manager_agent],
            tasks=[gate_task],
            process=Process.sequential,
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
