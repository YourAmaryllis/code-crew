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
    MemoryTool,
    PlatformShellTool,
    PythonREPLTool,
    StackReaderTool,
    WorkspaceReaderTool,
)

_KNOWLEDGE = Path(__file__).parent / "knowledge"


def _load_stacks(stacks: list[str]) -> str:
    """Load and concatenate stack docs for pre-injection into task descriptions.

    Called by crew builders when inventory.stacks is already known so agents
    receive stack conventions without needing to call stack_reader at runtime.
    """
    import re as _re
    _stacks_dir = _KNOWLEDGE / "stacks"
    parts = []
    for name in stacks:
        p = _stacks_dir / f"{name}.md"
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8")
        if txt.startswith("---"):
            body = _re.split(r"^---\s*$", txt, maxsplit=2, flags=_re.MULTILINE)
            txt = body[2].strip() if len(body) >= 3 else txt
        parts.append(f"### Stack: `{name}`\n\n{txt}")
    return "\n\n---\n\n".join(parts)


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
        "stack_reader": StackReaderTool(),
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

    sr = tools["stack_reader"]
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
        "scrum_master":      _agent("scrum_master",      [sr, dc, jv, mm]),
        "architect":         _agent("architect",         [sr, ws, ci, jv, sh, ah]),
        "engineer":          _agent("engineer",          [sr, ws, ci, ap, jv, sh, pr, ah], max_iter=25),
        "qa_lead":           _agent("qa_lead",           [sr, ws, jv, sh, br, pr, ah, cs]),
        "security_lead":      _agent("security_lead",      [sr, ws, sh, pr], max_iter=25),
        "compliance_officer": _agent("compliance_officer", [sr, ws, jv], max_iter=20),
        "product_owner":     _agent("product_owner",     [sr, jv]),
        "devops_lead":       _agent("devops_lead",       [sr, ws, jv, sh, pr, cs]),
        "release_engineer":  _agent("release_engineer",  [sr, ws, jv, sh]),
        "ux_lead":           _agent("ux_lead",           [fr, sr, ws, ah]),
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
    cleanup          = task("cleanup",                "engineer",           [implementation, devops_coord])
    code_review      = task("code_review",            "architect",          [implementation, devops_coord, cleanup])
    sec_review       = task("security_review",         "security_lead",      [implementation, devops_coord, code_review])
    comp_review      = task("compliance_review",       "compliance_officer", [implementation, devops_coord, code_review, sec_review])
    dod_check        = task("dod_check",               "scrum_master",
                            [sprint_planning, arch_review, scaffold_code, scaffold_test,
                             bdd_authoring, bdd_final, implementation, devops_coord, cleanup,
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
        "cleanup":              cleanup,
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


_DESIGN_STRUCTURE_SECTIONS = (
    "Detected stacks",
    "Detected architecture",
    "Architectural components",
    "Project summary",
    "Architect verification notes",
)


def _format_design_context(design_input: dict) -> str:
    acs = "\n".join(f"- {ac}" for ac in design_input.get("acceptance_criteria", []))
    structure = _load_structure_sections(*_DESIGN_STRUCTURE_SECTIONS)
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
    decomp = _load_decomposition_diagram()
    if decomp:
        sections.append(f"## Service decomposition\n\n{decomp}")
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
        + (f"**Architecture pattern**: {arch_style}\n\n{_load_stacks([f'arch-{arch_style}'])}\n" if arch_style else "")
        + f"\n**Acceptance criteria**:\n{acs}"
    )
    if comment_context:
        sections.append(f"## Context from Jira comments\n\n{comment_context}")
    if user_context:
        sections.append(user_context)
    if human_feedback:
        sections.append(human_feedback)
    structure = _load_structure_sections(*STRUCTURE_ENGINEER)
    if structure:
        sections.append(f"## Project structure\n\n{structure}")
    decomp = _load_decomposition_diagram()
    if decomp:
        sections.append(f"## Service decomposition\n\n{decomp}")
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


def _load_decomposition_diagram() -> str:
    """Load the mermaid diagram from .code-crew/decomposition.md if present.

    Returns only the ```mermaid...``` block — not the full file — so it stays
    compact enough to include in every command context without token bloat.
    Handles both the fenced format (current) and the bare graph TD format (legacy).
    """
    import re as _re
    p = Path.cwd() / ".code-crew" / "decomposition.md"
    if not p.exists():
        return ""
    try:
        text = p.read_text(encoding="utf-8")
        m = _re.search(r"(```mermaid\n.*?```)", text, _re.DOTALL)
        if m:
            return m.group(1)
        # Legacy: bare graph TD/LR block (no fence)
        m2 = _re.search(r"(graph (?:TD|LR)\b.*)", text, _re.DOTALL)
        if m2:
            return "```mermaid\n" + m2.group(1).strip() + "\n```"
        return ""
    except OSError:
        return ""


def _load_structure_sections(*headers: str) -> str:
    """Extract named ## sections from structure.md plus the # title line.

    Pass header names without the leading '## ' (e.g. 'Terraform infrastructure').
    Sections not present in the file are silently omitted.
    Pass no headers to get the full file.

    Role presets (use these constants instead of hard-coding header lists):
      STRUCTURE_SECURITY  — stacks, architecture, terraform, components, summary
      STRUCTURE_DEVOPS    — stacks, CI/CD, terraform, commands, components
      STRUCTURE_ENGINEER  — stacks, architecture, migration tool, commands, components
    """
    import re as _sre
    full = _load_project_structure()
    if not full or not headers:
        return full
    parts = _sre.split(r"^(?=## )", full, flags=_sre.MULTILINE)
    result: list[str] = []
    for part in parts:
        stripped = part.strip()
        if not stripped.startswith("## "):
            result.append(part)
            continue
        for h in headers:
            if stripped.startswith(f"## {h}"):
                result.append(part)
                break
    return "\n\n".join(p.strip() for p in result if p.strip())


STRUCTURE_SECURITY = (
    "Detected stacks",
    "Detected architecture",
    "Terraform infrastructure",
    "Architectural components",
    "Project summary",
    "Architect verification notes",
)

STRUCTURE_DEVOPS = (
    "Detected stacks",
    "CI/CD tooling",
    "Terraform infrastructure",
    "Project commands",
    "Architectural components",
)

STRUCTURE_ENGINEER = (
    "Detected stacks",
    "Detected architecture",
    "Detected migration tool",
    "Project commands",
    "Architectural components",
    "Project summary",
    "Architect verification notes",
)


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
    structure = _load_structure_sections(*STRUCTURE_DEVOPS)
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
    decomp = _load_decomposition_diagram()
    if decomp:
        sections.append(f"## Service decomposition\n\n{decomp}")
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

    structure = _load_structure_sections(*STRUCTURE_SECURITY)
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


def _run_explore_subtask(task_name: str, description: str, expected_output: str, agents: dict) -> str:
    """Run one focused explore subtask. Returns the raw output string."""
    t = Task(
        name=task_name,
        description=description,
        expected_output=expected_output,
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
        result = crew.kickoff(inputs={})
    return str(result)


def _build_filtered_tree(root: "Path", max_depth: int = 6) -> str:
    """Build an indented directory tree filtered to signal files only.

    Shows all directories (skipping noise) and key manifest / entrypoint files.
    This gives the LLM a structural view without flooding it with source filenames.
    """
    import pathlib

    SKIP_DIRS = {
        ".git", "vendor", "node_modules", "__pycache__", ".terraform",
        ".code-crew", "dist", "build", ".venv", "venv", ".mypy_cache",
        ".next", "coverage", ".idea", ".vscode", "playwright-report",
        "output", "test-results", ".turbo", ".cache",
    }
    SKIP_PREFIXES = (".", "_")

    # Files worth showing — manifests, entrypoints, key config
    SIGNAL_NAMES = {
        "README.md", "README.rst", "readme.md", "README",
        "go.mod", "go.sum", "package.json", "package-lock.json",
        "Cargo.toml", "pom.xml", "build.gradle", "settings.gradle",
        "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
        "Makefile", "makefile", "GNUmakefile",
        "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        ".gitmodules", "main.go", "main.py", "__main__.py",
        "index.ts", "index.js", "server.go", "app.py", "app.ts",
        "atlas.hcl", "alembic.ini",
    }
    SIGNAL_EXTENSIONS = {".tf", ".hcl"}  # terraform/config worth noting

    root = pathlib.Path(root)
    if not root.is_dir():
        return f"{root.name} (not a directory — skipped)"
    lines: list[str] = [f"{root.name}/"]

    def _walk(path: pathlib.Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        except PermissionError:
            return

        dirs = [
            e for e in entries
            if e.is_dir()
            and e.name not in SKIP_DIRS
            and not e.name.startswith(SKIP_PREFIXES)
        ]
        files = [
            e for e in entries
            if e.is_file()
            and (e.name in SIGNAL_NAMES or e.suffix in SIGNAL_EXTENSIONS)
            and not e.name.startswith(".")
        ]

        all_items = dirs + files
        for i, entry in enumerate(all_items):
            is_last = i == len(all_items) - 1
            connector = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")
            label = f"{entry.name}/" if entry.is_dir() else entry.name
            lines.append(f"{prefix}{connector}{label}")
            if entry.is_dir():
                _walk(entry, child_prefix, depth + 1)

    _walk(root, "", 0)
    return "\n".join(lines)


def _crew_kickoff_with_timeout(crew: "Crew", timeout_seconds: int = 300) -> str:
    """Run crew.kickoff() with a hard wall-clock timeout via SIGALRM (Unix).

    NVIDIA Build free tier silently hangs instead of returning 504 when the
    server-side deadline is exceeded. ThreadPoolExecutor.shutdown(wait=True)
    blocks even after future.result() times out, so we use SIGALRM which
    actually interrupts the running HTTP call. Falls back to no timeout on
    Windows (no SIGALRM).
    """
    import signal

    if not hasattr(signal, "SIGALRM"):
        return str(crew.kickoff(inputs={}))

    class _AlarmTimeout(BaseException):
        pass

    def _handler(signum: int, frame: object) -> None:
        raise _AlarmTimeout()

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout_seconds)
    try:
        result = crew.kickoff(inputs={})
        signal.alarm(0)
        return str(result)
    except _AlarmTimeout:
        raise TimeoutError(
            f"LLM call timed out after {timeout_seconds}s — NVIDIA server may be overloaded"
        )
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def _llm_call_with_tools(task_name: str, ctx: str, tc: dict, agents: dict,
                          timeout_seconds: int = 120) -> str:
    """Run one LLM task with workspace_reader + code_index tools."""
    tools = _make_tools()
    # Rebuild agent with full tool list (agents dict may have been built with empty tools)
    from code_crew.crew import build_agents
    agents_with_tools = build_agents(tools)
    t = Task(
        name=task_name,
        description=f"{ctx}\n\n{tc[task_name].description}",
        expected_output=tc[task_name].expected_output,
        agent=agents_with_tools["architect"],
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        crew = Crew(
            agents=[agents_with_tools["architect"]],
            tasks=[t],
            process=Process.sequential,
            verbose=True,
        )
        return _crew_kickoff_with_timeout(crew, timeout_seconds=timeout_seconds)


def build_breakdown_task(root: "Path", extra_context: str = "") -> str:
    """Phase 2: send filtered tree to LLM → AREA classifications.

    Bypasses CrewAI and calls the LLM directly so the socket-level timeout is
    actually enforced. Uses the fast (small) model — classification is pattern
    matching, so 8b is sufficient and has lower queue times on NVIDIA free tier.
    Depth=2 is enough to classify top-level areas without noise.
    """
    from shared.llm_factory import direct_llm_completion

    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    tree = _build_filtered_tree(root, max_depth=2)
    ctx = f"## Repository: {root.name}\n\n```\n{tree}\n```\n\n{extra_context}"
    prompt = f"{ctx}\n\n{tc['explore_breakdown'].description}"
    return direct_llm_completion(prompt, tier="fast", timeout=90, max_retries=3)


def _pre_read_unit(root: "Path", unit_path: str, max_file_chars: int = 800) -> str:
    """Pre-fetch key content from a unit directory for context injection.

    Reads: directory listing (depth 2), README, dependency manifests, and
    entry-point files. Keeps each file truncated to max_file_chars to stay
    within token budget.
    """
    import pathlib

    SIGNAL_NAMES = {
        "README.md", "README.rst", "readme.md", "README",
        "go.mod", "package.json", "Cargo.toml", "pom.xml",
        "pyproject.toml", "setup.py", "requirements.txt",
        "Makefile", "Dockerfile", "docker-compose.yml",
    }
    ENTRY_NAMES = {
        "main.go", "main.py", "__main__.py", "server.go",
        "app.py", "app.ts", "index.ts", "index.js",
    }

    unit_abs = pathlib.Path(root) / unit_path
    parts: list[str] = []

    # Depth-2 directory tree
    parts.append(_build_filtered_tree(unit_abs, max_depth=2))

    def _try_read(p: pathlib.Path) -> str:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            if len(text) > max_file_chars:
                text = text[:max_file_chars] + "\n… (truncated)"
            return text
        except OSError:
            return ""

    # Key files: manifests first, then entry points
    for name in list(SIGNAL_NAMES) + list(ENTRY_NAMES):
        candidate = unit_abs / name
        if candidate.is_file():
            content = _try_read(candidate)
            if content:
                parts.append(f"\n### {name}\n```\n{content}\n```")

    # cmd/ sub-entries (Go-style executables)
    cmd_dir = unit_abs / "cmd"
    if cmd_dir.is_dir():
        for sub in sorted(cmd_dir.iterdir()):
            if sub.is_dir():
                for entry in ("main.go", "main.py"):
                    ep = sub / entry
                    if ep.is_file():
                        content = _try_read(ep)
                        if content:
                            parts.append(f"\n### cmd/{sub.name}/{entry}\n```\n{content}\n```")
                        break

    return "\n".join(parts)


def build_summarize_unit_task(root: "Path", unit_path: str, unit_type: str,
                               unit_description: str, sub_executables: list[str],
                               infra_modules: list[str]) -> str:
    """Phase 3: deep-dive one unit → UNIT_SUMMARY block.

    Pre-reads key files programmatically then calls the LLM directly (bypassing
    CrewAI) so the socket-level timeout is enforced. Avoids the tool-use loop
    which requires multiple round-trips and is more likely to hang on NVIDIA.
    """
    from shared.llm_factory import direct_llm_completion

    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")

    matching_execs = [e for e in sub_executables if e.startswith(unit_path + "/")]
    matching_infra = [m for m in infra_modules
                      if unit_path.replace("_", "-") in m or m in unit_path]

    ctx = f"## Unit: {unit_path}\n"
    ctx += f"**Classified as**: {unit_type} — {unit_description}\n"
    if matching_execs:
        ctx += f"**Detected sub-executables**: {', '.join(matching_execs)}\n"
    if matching_infra:
        ctx += f"**Matching infra modules**: {', '.join(matching_infra)}\n"
    ctx += "\n### Pre-read content\n" + _pre_read_unit(root, unit_path)

    prompt = f"{ctx}\n\n{tc['explore_summarize_unit'].description}"
    return direct_llm_completion(prompt, tier="fast", timeout=90, max_retries=2)


def build_summarize_docs_task(root: "Path", docs_path: str,
                               docs_description: str) -> str:
    """Phase 3: summarize a docs directory → DOC_SUMMARY blocks.

    Pre-reads document titles/first paragraphs then calls the LLM directly.
    """
    import pathlib
    from shared.llm_factory import direct_llm_completion

    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    docs_abs = pathlib.Path(root) / docs_path

    # Collect doc files (up to 20, first 400 chars each)
    doc_snippets: list[str] = []
    try:
        for p in sorted(docs_abs.rglob("*.md"))[:20]:
            try:
                snippet = p.read_text(encoding="utf-8", errors="replace")[:400]
                rel = p.relative_to(docs_abs)
                doc_snippets.append(f"**{rel}**\n{snippet}\n---")
            except OSError:
                pass
    except OSError:
        pass

    ctx = (f"## Documentation directory: {docs_path}\n"
           f"**Description**: {docs_description}\n\n"
           + ("\n".join(doc_snippets) if doc_snippets else "(no documents found)"))

    prompt = f"{ctx}\n\n{tc['explore_summarize_docs'].description}"
    return direct_llm_completion(prompt, tier="fast", timeout=90, max_retries=2)


_DEPLOYABLE_TYPES = frozenset({"deployable-service", "worker", "lambda", "frontend"})


def classify_units_from_structure(structure_md: str) -> dict:
    """Phase 4 (Python): parse UNIT_SUMMARY blocks and classify deterministically.

    Returns dict:
      real_services: list[str]           — paths with deployable TYPE or non-none ENTRY_POINTS
      not_services: dict[str, str]       — path → reason (library/cli/test-harness/…)
      decomposed: dict[str, list[str]]   — parent path → sub-service names
    """
    result: dict = {"real_services": [], "not_services": {}, "decomposed": {}}

    in_block = False
    current_path: str | None = None
    current: dict = {}

    def _clean(raw: str) -> str:
        """Strip markdown heading markers and bold markers so the model's formatting doesn't break matching."""
        return raw.strip().lstrip("# ").strip().replace("**", "").strip()

    for line in structure_md.splitlines():
        normed = _clean(line)
        if normed.startswith("UNIT_SUMMARY:") and not normed.startswith("UNIT_SUMMARY COMPLETE"):
            in_block = True
            current_path = normed[len("UNIT_SUMMARY:"):].strip().rstrip("/")
            current = {"type": "", "entry_points": "none", "decompose": False, "sub_units": []}
        elif normed == "UNIT_SUMMARY COMPLETE" and in_block:
            if current_path:
                ep_val = current["entry_points"].lower().strip()
                is_deployable = (
                    current["type"] in _DEPLOYABLE_TYPES
                    or (ep_val and ep_val != "none")
                )
                if is_deployable:
                    result["real_services"].append(current_path)
                    if current["decompose"] and current["sub_units"]:
                        result["decomposed"][current_path] = current["sub_units"]
                else:
                    result["not_services"][current_path] = current["type"] or "library"
            in_block = False
            current_path = None
        elif in_block:
            s = _clean(line)
            if s.startswith("TYPE:"):
                _val = s[5:].strip().split()
                if _val:
                    current["type"] = _val[0].lower().rstrip(",|")
            elif s.startswith("ENTRY_POINTS:"):
                current["entry_points"] = s[13:].strip()
            elif s.upper().startswith("DECOMPOSE: YES"):
                current["decompose"] = True
            elif s.startswith("SUB_UNITS:") and current["decompose"]:
                subs = [x.strip() for x in s[10:].split(",")
                        if x.strip() and not x.strip().startswith("<")]
                if subs:
                    current["sub_units"] = subs

    # Commit any unclosed block (EOF or filter flushed without COMPLETE marker)
    if in_block and current_path:
        ep_val = current["entry_points"].lower().strip()
        is_deployable = (
            current["type"] in _DEPLOYABLE_TYPES
            or (ep_val and ep_val != "none")
        )
        if is_deployable:
            result["real_services"].append(current_path)
            if current["decompose"] and current["sub_units"]:
                result["decomposed"][current_path] = current["sub_units"]
        else:
            result["not_services"][current_path] = current["type"] or "library"

    return result


def build_diagram_from_services(
    real_services: "list[str]",
    not_services: "dict[str, str]",
    decomposed: "dict[str, list[str]]",
    external_services: "list[dict]",
) -> str:
    """Phase 4 (Python): deterministic Mermaid graph TD from classified service lists.

    Parent-child edges are derived from path hierarchy (no LLM hallucinations).
    External services appear as nodes; sub-services from decomposed appear inline.
    """
    if not real_services:
        return ""

    def _node_id(path: str) -> str:
        return path.replace("/", "-").replace("_", "-").replace(".", "-").replace(" ", "-")

    svc_set = set(real_services)
    lines = ["graph TD"]

    # Declare all internal service nodes
    for svc in real_services:
        nid = _node_id(svc)
        lines.append(f'    {nid}["{svc}\\n(deployable)"]')

    # Declare explicit decomposed sub-service nodes (if not already in real_services)
    for parent, subs in decomposed.items():
        for sub in subs:
            full = f"{parent}/{sub}"
            if full not in svc_set:
                nid = _node_id(full)
                lines.append(f'    {nid}["{sub}\\n(sub-service)"]')

    # External service nodes
    ext_names = []
    for e in external_services:
        name = e.get("name", str(e)) if isinstance(e, dict) else str(e)
        ext_names.append(name)
        nid = _node_id(name)
        lines.append(f'    {nid}["{name}\\n(external)"]:::external')

    # Structural parent-child edges from path hierarchy
    for svc in real_services:
        parent = svc.rsplit("/", 1)[0] if "/" in svc else None
        if parent and parent in svc_set:
            lines.append(f"    {_node_id(parent)} --> {_node_id(svc)}")

    # Explicit sub-service edges from decomposed dict
    for parent, subs in decomposed.items():
        pid = _node_id(parent)
        for sub in subs:
            full = f"{parent}/{sub}"
            cid = _node_id(full)
            edge = f"    {pid} --> {cid}"
            if edge not in lines:
                lines.append(edge)

    if ext_names:
        lines.append("    classDef external fill:#f5f5f5,stroke:#999,stroke-dasharray:4 4")

    return "\n".join(lines)


def build_synthesize_decomposition_from_structure(structure_md: str) -> str:
    """Phase 4: decomposition from structure.md → REAL_SERVICE/DECOMPOSE/PROJECT + diagram.

    Uses direct LLM call (bypassing CrewAI) with the standard model so the
    socket-level timeout is enforced. structure.md already has all unit summaries,
    so tool access is rarely needed for classification.

    Kept for backward compatibility; new callers should use classify_units_from_structure
    + build_diagram_from_services instead.
    """
    from shared.llm_factory import direct_llm_completion

    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    ctx = f"## structure.md\n\n{structure_md}\n"
    prompt = f"{ctx}\n\n{tc['explore_synthesize_decomposition'].description}"
    return direct_llm_completion(prompt, tier="fast", timeout=90, max_retries=3)


def _pre_read_infra_dir(root: "Path", terraform_info: dict) -> str:
    """Return a flat file listing of the infra directory — no parsing, just names."""
    import pathlib
    infra_root_rel = (terraform_info or {}).get("root", "")
    if not infra_root_rel:
        return ""
    infra_path = pathlib.Path(root) / infra_root_rel
    if not infra_path.is_dir():
        return ""
    lines: list[str] = [f"## Infrastructure directory: {infra_root_rel}/"]
    try:
        for entry in sorted(infra_path.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                children = sorted(c.name for c in entry.iterdir()
                                   if not c.name.startswith("."))[:20]
                lines.append(f"  {entry.name}/")
                for c in children:
                    lines.append(f"    {c}")
            else:
                lines.append(f"  {entry.name}")
    except Exception:
        pass
    return "\n".join(lines)


def _pre_read_sad(designs_dir: "Path | None") -> str:
    """Return first ~1500 chars of each SAD file in designs/SAD/."""
    import pathlib
    if not designs_dir:
        return ""
    sad_dir = pathlib.Path(designs_dir) / "SAD"
    if not sad_dir.is_dir():
        return ""
    chunks: list[str] = []
    for f in sorted(sad_dir.glob("*.md"))[:4]:
        try:
            content = f.read_text(encoding="utf-8", errors="replace")[:1500]
            chunks.append(f"### {f.name}\n\n{content}")
        except Exception:
            pass
    return "\n\n".join(chunks)


def build_synthesize_decomposition_task(
    candidate_dirs: list[str],
    sub_executables: list[str],
    infra_modules: list[str],
    gitmodules: str,
    infra_dir_listing: str,
    sad_excerpts: str,
    service_subdirs: dict[str, list[str]],
) -> str:
    """Decomposition synthesis: candidates → REAL_SERVICE/NOT_SERVICE/DECOMPOSE + diagram."""
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    agents = build_agents(_make_tools())

    by_svc: dict[str, list[str]] = {}
    for exe in sub_executables:
        parent = exe.split("/")[0]
        by_svc.setdefault(parent, []).append(exe)

    ctx = "## Candidate service directories\n\n"
    for d in candidate_dirs:
        subdirs = service_subdirs.get(d, [])
        execs = by_svc.get(d, [])
        ctx += f"### {d}/\n"
        if subdirs:
            ctx += f"- Subdirs: {', '.join(subdirs[:20])}\n"
        if execs:
            ctx += f"- Sub-executables: {', '.join(execs)}\n"
        else:
            ctx += "- Sub-executables: none\n"
        matching = [m for m in infra_modules if d.replace("_", "-") in m or m in d]
        if matching:
            ctx += f"- Matching infra modules: {', '.join(matching)}\n"
        ctx += "\n"

    ctx += "## All sub-executables\n" + "\n".join(f"- {e}" for e in sub_executables) + "\n\n"
    ctx += "## All infrastructure modules\n" + "\n".join(f"- {m}" for m in infra_modules[:40]) + "\n\n"

    if gitmodules:
        ctx += f"## .gitmodules\n\n```\n{gitmodules}\n```\n\n"
    if infra_dir_listing:
        ctx += infra_dir_listing + "\n\n"
    if sad_excerpts:
        ctx += "## System Architecture Document (SAD) excerpts\n\n" + sad_excerpts + "\n\n"

    return _llm_call("explore_synthesize_decomposition", ctx, tc, agents)


def _parse_decomposition_output(raw: str) -> dict:
    """Parse REAL_SERVICE/NOT_SERVICE/DECOMPOSE lines and DECOMPOSITION diagram.

    The 8b model often echoes the task template (including format examples in code
    fences) before producing real output, and wraps real output in code fences too.
    Strategy: strip all backtick fence markers and scan every remaining line for the
    actual marker prefixes. For the diagram, find the first `graph TD/LR` block.
    """
    result: dict = {
        "real_services": [],
        "not_services": {},
        "decomposed": {},
        "diagram": "",
    }

    # Strip backtick fence lines and DECOMPOSITION_BEGIN/END markers (just noise).
    # Collect the diagram separately: first graph TD/LR block in the output.
    _in_graph = False
    _graph_lines: list[str] = []
    _seen_graph_end = False

    lines = raw.splitlines()
    clean_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        # Skip fence markers and explicit diagram markers
        if stripped.startswith("```") or stripped in ("DECOMPOSITION_BEGIN", "DECOMPOSITION_END"):
            if _in_graph and not _seen_graph_end:
                # A ``` line closes the graph block
                _seen_graph_end = True
                _in_graph = False
            continue
        # Detect start of mermaid graph block
        if stripped.startswith("graph ") and not result["diagram"] and not _in_graph:
            _in_graph = True
            _graph_lines = [line]
            continue
        if _in_graph:
            if stripped == "" and _graph_lines:
                # Blank line ends the graph block
                _seen_graph_end = True
                _in_graph = False
                result["diagram"] = "\n".join(_graph_lines).strip()
            else:
                _graph_lines.append(line)
            continue
        clean_lines.append(line)

    # If graph block ran to end of input without a closing marker, save it
    if _in_graph and _graph_lines and not result["diagram"]:
        result["diagram"] = "\n".join(_graph_lines).strip()
    elif _seen_graph_end and _graph_lines and not result["diagram"]:
        result["diagram"] = "\n".join(_graph_lines).strip()

    # Now parse the marker lines (fences already stripped)
    for line in clean_lines:
        stripped = line.strip()
        if stripped.startswith("REAL_SERVICE:"):
            rest = stripped.split(":", 1)[1].strip()
            svc = rest.split("|")[0].strip().split("→")[0].strip().rstrip("/")
            # Reject angle-bracket template placeholders
            if svc and not svc.startswith("<") and svc not in result["real_services"]:
                result["real_services"].append(svc)
        elif stripped.startswith("NOT_SERVICE:"):
            rest = stripped.split(":", 1)[1].strip()
            parts = rest.split("|", 1)
            svc = parts[0].strip().split("→")[0].strip().rstrip("/")
            reason = parts[1].strip() if len(parts) > 1 else ""
            if svc and not svc.startswith("<"):
                result["not_services"][svc] = reason
        elif stripped.startswith("DECOMPOSE:"):
            rest = stripped.split(":", 1)[1].strip()
            parts = rest.split("→", 1)
            if len(parts) == 2:
                parent = parts[0].strip().rstrip("/")
                sub_part = parts[1].split("|")[0].strip()
                subs = [s.strip() for s in sub_part.split(",")
                        if s.strip() and not s.strip().startswith("<")]
                if parent and not parent.startswith("<") and subs:
                    result["decomposed"][parent] = subs
    return result


def _pre_read_service(root: "Path", svc: str, sub_executables: list[str]) -> dict:
    """Read key files for one service dir. Returns dict ready to inject into a summarize task."""
    import pathlib
    svc_path = pathlib.Path(root) / svc

    readme = ""
    for name in ("README.md", "README.rst", "readme.md"):
        p = svc_path / name
        if p.exists():
            try:
                readme = p.read_text(encoding="utf-8", errors="replace")[:600]
            except Exception:
                pass
            break

    subdirs = []
    try:
        subdirs = sorted(
            d.name for d in svc_path.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )[:25]
    except Exception:
        pass

    manifest = ""
    manifest_names = ("go.mod", "package.json", "requirements.txt",
                      "pyproject.toml", "Cargo.toml", "pom.xml")
    search_paths = [svc_path] + [svc_path / sub for sub in subdirs[:5]]
    for sp in search_paths:
        for name in manifest_names:
            p = sp / name
            if p.exists():
                try:
                    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[:12]
                    rel = str(p.relative_to(root))
                    manifest = f"{rel}:\n" + "\n".join(lines)
                except Exception:
                    pass
                break
        if manifest:
            break

    entry_snippets = []
    svc_execs = [e for e in sub_executables if e.startswith(f"{svc}/")]
    for exec_path in svc_execs[:4]:
        for ep in ("main.go", "main.py", "index.ts", "__main__.py", "server.go"):
            p = pathlib.Path(root) / exec_path / ep
            if p.exists():
                try:
                    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[:15]
                    entry_snippets.append(f"{exec_path}/{ep}:\n" + "\n".join(lines))
                except Exception:
                    pass
                break

    return {
        "name": svc,
        "readme": readme,
        "subdirs": subdirs,
        "manifest": manifest,
        "entry_snippets": entry_snippets,
        "sub_executables": svc_execs,
    }


def _pre_read_domain(root: "Path", domain_path: str) -> dict:
    """Read key files for one domain dir. Returns dict ready to inject into a summarize task."""
    import pathlib
    dp = pathlib.Path(root) / domain_path

    files: list[str] = []
    key_content = ""
    try:
        source_exts = {".go", ".py", ".ts", ".tsx", ".java", ".rs", ".js"}
        all_files = list(dp.iterdir())
        files = sorted(f.name for f in all_files if f.is_file())[:30]
        source_files = [f for f in all_files if f.is_file() and f.suffix in source_exts]
        if source_files:
            key_file = max(source_files, key=lambda f: f.stat().st_size)
            lines = key_file.read_text(encoding="utf-8", errors="replace").splitlines()[:20]
            key_content = f"{key_file.name}:\n" + "\n".join(lines)
    except Exception:
        pass

    return {
        "name": dp.name,
        "path": domain_path,
        "parent_service": domain_path.split("/")[0] if "/" in domain_path else "",
        "files": files,
        "key_content": key_content,
    }


def _llm_call(task_name: str, ctx: str, tc: dict, agents: dict,
              timeout_seconds: int = 300, max_retries: int = 2) -> str:
    """Run one no-tools LLM task and return its raw output.

    Retries up to max_retries times on TimeoutError or transient failure, since
    NVIDIA Build free tier can 504 even on small contexts.
    """
    import time

    last_exc: BaseException | None = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait = 30 * attempt
            print(f"  [retry {attempt}/{max_retries}] waiting {wait}s before retry…")
            time.sleep(wait)
        try:
            t = Task(
                name=task_name,
                description=f"{ctx}\n\n{tc[task_name].description}",
                expected_output=tc[task_name].expected_output,
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
                return _crew_kickoff_with_timeout(crew, timeout_seconds=timeout_seconds)
        except BaseException as exc:
            last_exc = exc
            print(f"  LLM call attempt {attempt + 1} failed: {exc}")
    raise RuntimeError(f"LLM call '{task_name}' failed after {max_retries + 1} attempts") from last_exc


def build_summarize_service_task(service_info: dict, infra_modules: list[str]) -> str:
    """Summarize one service directory. Returns raw output string."""
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    agents = build_agents(_make_tools())

    ctx = f"## Service: {service_info['name']}\n\n"
    if service_info.get("readme"):
        ctx += f"### README (first 600 chars)\n\n{service_info['readme']}\n\n"
    if service_info.get("subdirs"):
        ctx += f"### Subdirectories\n" + "\n".join(f"- {d}" for d in service_info["subdirs"]) + "\n\n"
    if service_info.get("manifest"):
        ctx += f"### Dependency manifest\n\n```\n{service_info['manifest']}\n```\n\n"
    if service_info.get("entry_snippets"):
        ctx += "### Entry point snippets\n\n"
        for snippet in service_info["entry_snippets"]:
            ctx += f"```\n{snippet}\n```\n\n"
    if service_info.get("sub_executables"):
        ctx += "### Sub-executables detected\n" + "\n".join(f"- {e}" for e in service_info["sub_executables"]) + "\n\n"
    if infra_modules:
        ctx += "### Infrastructure modules (for context)\n" + "\n".join(f"- {m}" for m in infra_modules[:20]) + "\n\n"

    return _llm_call("explore_summarize_service", ctx, tc, agents)


def build_summarize_domain_task(domain_info: dict, infra_modules: list[str]) -> str:
    """Summarize one domain directory. Returns raw output string."""
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    agents = build_agents(_make_tools())

    ctx = f"## Domain: {domain_info['name']}"
    if domain_info.get("parent_service"):
        ctx += f" (inside {domain_info['parent_service']})"
    ctx += f"\n**Path**: `{domain_info['path']}`\n\n"
    if domain_info.get("files"):
        ctx += "### Files in this directory\n" + "\n".join(f"- {f}" for f in domain_info["files"]) + "\n\n"
    if domain_info.get("key_content"):
        ctx += f"### Key source file (largest)\n\n```\n{domain_info['key_content']}\n```\n\n"
    if infra_modules:
        # Highlight if domain name matches any module
        domain_name = domain_info["name"].replace("_", "-")
        matching = [m for m in infra_modules if domain_name in m or m in domain_name]
        if matching:
            ctx += f"### Matching infrastructure modules\n" + "\n".join(f"- {m}" for m in matching) + "\n\n"
        ctx += "### All infrastructure modules\n" + "\n".join(f"- {m}" for m in infra_modules[:20]) + "\n\n"

    return _llm_call("explore_summarize_domain", ctx, tc, agents)


def build_synthesize_scope_task(summaries: dict, inventory: dict) -> str:
    """Scope synthesis: summaries → PROJECT blocks. Returns raw output string."""
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    agents = build_agents(_make_tools())

    ctx = _build_summaries_context(summaries, inventory)
    return _llm_call("explore_synthesize_scope", ctx, tc, agents)


def build_synthesize_architecture_task(summaries: dict, inventory: dict) -> str:
    """Architecture synthesis: summaries → ARCHITECTURE_STYLE, COMPONENT lines, code_structure."""
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    agents = build_agents(_make_tools())

    ctx = _build_summaries_context(summaries, inventory)
    ctx += f"\n**Python-detected architecture hint**: {inventory.get('arch_style', 'undetected')}\n"
    return _llm_call("explore_synthesize_architecture", ctx, tc, agents)


def build_synthesize_compliance_task(summaries: dict, inventory: dict) -> str:
    """Compliance synthesis: summaries → compliance_standards DISCOVERY block."""
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    agents = build_agents(_make_tools())

    ctx = _build_summaries_context(summaries, inventory)
    detected = inventory.get("compliance_standards", [])
    if detected:
        ctx += f"\n**Python-detected compliance standards**: {', '.join(detected)}\n"
    else:
        ctx += "\n**Python-detected compliance standards**: none\n"
    return _llm_call("explore_synthesize_compliance", ctx, tc, agents)


def _build_summaries_context(summaries: dict, inventory: dict) -> str:
    """Build the shared context block injected into all synthesis tasks."""
    ctx = f"## Project: {inventory.get('root_name', '.')}\n\n"

    service_sums = {k: v for k, v in summaries.items() if not v.get("_is_domain")}
    domain_sums = {k: v for k, v in summaries.items() if v.get("_is_domain")}

    if service_sums:
        ctx += "## Service summaries\n\n"
        for svc, s in service_sums.items():
            ctx += f"### {svc}\n"
            ctx += f"- **Purpose**: {s.get('PURPOSE', '')}\n"
            ctx += f"- **Type**: {s.get('TYPE', '')}\n"
            ctx += f"- **Sensitivity**: {s.get('SENSITIVITY', '')}\n"
            if s.get("ENTRY_POINTS") and s["ENTRY_POINTS"] != "none":
                ctx += f"- **Entry points**: {s['ENTRY_POINTS']}\n"
            if s.get("subdirs"):
                ctx += f"- **Subdirectories**: {', '.join(s['subdirs'][:15])}\n"
            ctx += "\n"

    if domain_sums:
        ctx += "## Domain summaries\n\n"
        for path, s in domain_sums.items():
            ctx += f"### {s.get('DOMAIN_SUMMARY', path)}\n"
            ctx += f"- **Purpose**: {s.get('PURPOSE', '')}\n"
            ctx += f"- **Sensitivity**: {s.get('SENSITIVITY', '')}\n"
            ctx += f"- **Separate OTM**: {s.get('SEPARATE_OTM', 'no')}\n"
            if s.get("REASON"):
                ctx += f"- **Reason**: {s['REASON']}\n"
            ctx += "\n"

    if inventory.get("infra_modules"):
        ctx += "## Infrastructure modules\n" + "\n".join(f"- {m}" for m in inventory["infra_modules"]) + "\n\n"
    if inventory.get("sub_executables"):
        ctx += "## Sub-executables\n" + "\n".join(f"- {e}" for e in inventory["sub_executables"]) + "\n\n"
    if inventory.get("gitmodules"):
        ctx += f"## .gitmodules\n\n```\n{inventory['gitmodules']}\n```\n\n"

    return ctx


def build_explore_single_task(explore_input: dict, extra_context: str = "") -> str:
    """Run the LLM phase of /explore as 3 focused subtasks. Returns concatenated output."""
    tools = _make_tools()
    agents = build_agents(tools)
    td = _KNOWLEDGE / "tasks"
    tc = load_bundle_tasks(td)

    stacks = explore_input.get("stacks", [])
    commands = explore_input.get("commands", {})
    ci_methods = explore_input.get("ci_methods", [])
    ci_workflows = explore_input.get("ci_workflows", {})
    terraform = explore_input.get("terraform", {})
    feature_dirs = explore_input.get("feature_dirs", [])
    test_dirs = explore_input.get("test_dirs", [])
    comp_stds = explore_input.get("compliance_standards", [])
    domain_dirs = explore_input.get("domain_dirs", {})

    header = f"## Project: {explore_input.get('root_name', '.')}\n\n"
    header += f"**Service dirs**: {', '.join(explore_input.get('svc_dirs', []))}\n\n"

    # ── Subtask 1: no-tools synthesis — architecture style, component descriptions ──
    # Keep context minimal: no file lists, no modules, no commands. Agent must not call tools.
    v = header
    v += f"**Phase 1 architecture**: {explore_input.get('arch_style', 'undetected')}\n"
    v += f"**Phase 1 migration tool**: {explore_input.get('migration_tool', 'undetected')}\n"
    v += f"**Phase 1 test framework**: {explore_input.get('test_framework', 'not detected')}\n"
    v += f"**Phase 1 API doc standard**: {explore_input.get('api_doc', 'not detected')}"
    if explore_input.get("api_doc_path"):
        v += f" (at `{explore_input['api_doc_path']}`)"
    v += "\n\n"
    if stacks:
        v += "### Detected stacks\n" + "\n".join(f"- {s}" for s in stacks) + "\n\n"
    if ci_methods:
        v += "### Detected CI/CD methods\n" + "\n".join(f"- {m}" for m in ci_methods) + "\n\n"
    if terraform.get("root"):
        v += f"**Terraform root**: `{terraform['root']}`\n\n"
    # Top-level commands only (not the full list which can be very long)
    _key_cmds = {k: v_ for k, v_ in commands.items() if k in ("test", "build", "lint")}
    if _key_cmds:
        v += "### Key commands\n"
        v += "\n".join(f"- `{k}`: `{v_}`" for k, v_ in _key_cmds.items()) + "\n\n"

    result1 = _run_explore_subtask(
        "explore_verify",
        f"{v}\n\n{tc['explore_verify'].description}",
        tc["explore_verify"].expected_output,
        agents,
    )

    # ── Subtask 2: code structure, architectural components, entry points ──
    s = header
    if stacks:
        s += "### Verified stacks\n" + "\n".join(f"- {st}" for st in stacks) + "\n\n"
    if domain_dirs:
        s += "### Detected domain directories (heuristic — verify with SAD and code)\n"
        for svc, doms in domain_dirs.items():
            s += f"**{svc}**: {', '.join(doms)}\n"
        s += "\n"
    if extra_context:
        s += extra_context

    result2 = _run_explore_subtask(
        "explore_structure",
        f"{s}\n\n{tc['explore_structure'].description}",
        tc["explore_structure"].expected_output,
        agents,
    )

    # ── Subtask 3: test suites, CI/CD workflows, compliance ──
    t_ = header
    if feature_dirs:
        t_ += f"**BDD feature dirs**: {', '.join(feature_dirs)}\n"
    if test_dirs:
        t_ += f"**Detected test dirs**: {', '.join(test_dirs)}\n"
    if comp_stds:
        t_ += f"**Phase 1 compliance standards detected**: {', '.join(comp_stds)} — verify by reading designs/ and docs/\n"
    else:
        t_ += "**Phase 1 compliance standards**: none detected — check designs/ and docs/ for HIPAA/SOC2/GDPR/CCPA/PCI-DSS/FIPS mentions\n"
    t_ += "\n"
    if ci_methods:
        t_ += "### Detected CI/CD methods\n"
        for m in ci_methods:
            detail = ci_workflows.get(m, "")
            t_ += f"- {m}" + (f": {detail}" if detail else "") + "\n"
        t_ += "\n"

    result3 = _run_explore_subtask(
        "explore_tests",
        f"{t_}\n\n{tc['explore_tests'].description}",
        tc["explore_tests"].expected_output,
        agents,
    )

    return result1 + "\n" + result2 + "\n" + result3


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


def _read_service_readmes(inventory: dict) -> str:
    """Pre-read README files for each service dir. Returns formatted markdown block."""
    import pathlib
    root_str = inventory.get("root", "")
    if not root_str:
        return ""
    root = pathlib.Path(root_str)
    lines: list[str] = []
    for svc in inventory.get("svc_dirs", []):
        for readme_name in ("README.md", "README.rst", "README.txt", "readme.md"):
            readme = root / svc / readme_name
            if readme.exists():
                try:
                    content = readme.read_text(encoding="utf-8", errors="replace")
                    # Cap at 600 chars — enough for the first paragraph
                    if len(content) > 600:
                        content = content[:600] + "\n... (truncated)"
                    lines.append(f"### {svc}/README\n\n{content}")
                except Exception:
                    pass
                break
    return "\n\n".join(lines)


def build_otm_scope_task(inventory: dict) -> Crew:
    """Return a single-task Crew that decides how to partition the project into OTM files."""
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    agents = build_agents(_make_tools())

    lines = ["## Project inventory\n"]
    lines.append(f"**Root**: {inventory.get('root', '.')}")
    if inventory.get("stacks"):
        lines.append(f"**Detected stacks**: {', '.join(inventory['stacks'])}")

    if inventory.get("svc_dirs"):
        lines.append("### Source services (top-level directories)\n" +
                     "\n".join(f"- {d}" for d in inventory["svc_dirs"]))

    if inventory.get("sub_executables"):
        lines.append(
            "### Sub-executables (separately deployable binaries within services)\n"
            "Detected by stack-specific scan (Go cmd/, Python __main__, Node workspaces, etc.):\n" +
            "\n".join(f"- {e}" for e in inventory["sub_executables"])
        )

    if inventory.get("domain_dirs"):
        _dd_lines = [
            "### Detected domain directories\n"
            "Heuristic scan of internal/src/pages dirs — directories with ≥5 source files.\n"
            "Use as candidates; not all will warrant a separate OTM."
        ]
        for svc, domains in inventory["domain_dirs"].items():
            _dd_lines.append(f"\n**{svc}**:")
            _dd_lines.extend(f"  - {d}" for d in domains)
        lines.append("\n".join(_dd_lines))

    if inventory.get("infra_modules"):
        lines.append(
            "### Infrastructure modules\n"
            "A domain directory that matches an infra module name has its own deployment unit:\n" +
            "\n".join(f"- {m}" for m in inventory["infra_modules"])
        )

    if inventory.get("external_services"):
        _ext_lines: list[str] = []
        for _es in inventory["external_services"]:
            if isinstance(_es, dict):
                _ext_lines.append(f"- {_es.get('name', _es)} ({_es.get('category', '')})")
            else:
                _ext_lines.append(f"- {_es}")
        lines.append("### External services detected in source\n" + "\n".join(_ext_lines))

    # Pre-read service READMEs so the agent doesn't need tool calls for this
    _readmes = _read_service_readmes(inventory)
    if _readmes:
        lines.append("## Service READMEs (pre-read — do not re-read these files)\n\n" + _readmes)

    # Pre-read .gitmodules
    if inventory.get("gitmodules"):
        lines.append("## .gitmodules (pre-read — do not re-read this file)\n\n```\n"
                     + inventory["gitmodules"] + "\n```")

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


def _terraform_grep(
    component_dirs: list[str],
    root: "Path | None" = None,
    infra_dir: str = "",
) -> str:
    """Grep the infrastructure directory for Terraform references to component dirs.

    Uses infra_dir if supplied (value from inventory.json terraform.root).
    Falls back to scanning common directory names.
    Returns a compact summary so agents don't burn API calls searching Terraform.
    """
    import subprocess, pathlib, re
    base = root or pathlib.Path.cwd()
    search_dir: "pathlib.Path | None" = None
    if infra_dir:
        candidate = base / infra_dir
        if candidate.exists():
            search_dir = candidate
    if search_dir is None:
        for name in ("infra", "terraform", "infrastructure", "ops"):
            candidate = base / name
            if candidate.exists() and any(candidate.rglob("*.tf")):
                search_dir = candidate
                break
    if search_dir is None:
        return ""

    # Build patterns from component directory names (handles fhir_proxy → fhir/proxy, fhir-proxy)
    patterns = []
    for d in component_dirs:
        patterns += [d, d.replace("_", "-"), d.replace("_", "/")]
    pattern = "|".join(set(patterns))

    try:
        result = subprocess.run(
            ["grep", "-rn", "--include=*.tf", "-E", pattern, str(search_dir)],
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
    structure = _load_structure_sections(*STRUCTURE_SECURITY)
    root = pathlib.Path.cwd()
    tf_info = inventory.get("terraform", {})

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
    infra_root = tf_info.get("root", "")
    tf_grep = stored_grep if stored_grep is not None else _terraform_grep(
        project["components"], root, infra_dir=infra_root
    )

    if tf_grep:
        ctx_lines.append(
            "## Terraform deployment references (pre-scanned)\n\n"
            "Every Terraform line mentioning this service's components. "
            "Read these to determine the Terraform key, CPU/memory, ALB path, and env vars. "
            "Do NOT re-search the infrastructure directory — this output is already complete.\n\n"
            f"```\n{tf_grep}\n```"
        )
    else:
        ctx_lines.append(
            "## Terraform deployment references\n\n"
            "No explicit Terraform resource found for this service. "
            "Default deployment: **AWS ECS Fargate** (inferred from `ecs-deployment` stack). "
            "Do not search the infrastructure directory — it was already scanned and found nothing."
        )

    if structure:
        ctx_lines.append(f"## Project structure\n\n{structure}")

    decomp = _load_decomposition_diagram()
    if decomp:
        ctx_lines.append(
            "## Service decomposition (pre-computed — do NOT re-read decomposition.md)\n\n"
            + decomp
        )

    stack_docs = _load_stacks(stacks)
    if stack_docs:
        ctx_lines.append(
            "## Technology stack conventions (pre-injected — do NOT call stack_reader)\n\n"
            + stack_docs
        )

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

    No tools — all context (OTM + feedback) is pre-injected by Python.
    """
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    ac = load_bundle_agents(_KNOWLEDGE / "agents")

    ctx = (
        f"## Project\n\n"
        f"**Project id**: {project['id']}\n"
        f"**Project name**: {project['name']}\n\n"
        f"## Manager revision feedback (fix ALL of these)\n\n"
        f"{revision_feedback}\n\n"
        f"## Existing OTM YAML to patch\n\n"
        f"```yaml\n{otm_text}\n```"
    )

    architect_def = ac["architect"]
    architect = Agent(
        role=architect_def.role,
        goal=architect_def.goal,
        backstory=architect_def.backstory,
        llm=get_llm_for_tier("standard"),
        tools=[],
        max_iter=5,
        verbose=True,
    )

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


def _parse_yaml_section(text: str, key: str) -> list:
    """Extract a top-level YAML list section from LLM output. Returns [] on any failure."""
    import yaml as _yaml
    import re as _re
    # Strip markdown fences
    text = _re.sub(r"```ya?ml\s*\n?", "", text)
    text = _re.sub(r"```\s*$", "", text, flags=_re.MULTILINE)
    # Strip known completion markers that look like non-YAML prose
    for _marker in ("DISCOVERY COMPLETE", "THREATS COMPLETE", "MITIGATIONS COMPLETE", "OTM BUILD COMPLETE", "COMPONENT COMPLETE"):
        text = text.replace(_marker, "")
    # Find `key:` at start of a line
    pattern = _re.compile(r"^" + _re.escape(key) + r"\s*:", _re.MULTILINE)
    m = pattern.search(text)
    if not m:
        return []
    start = m.start()
    # Find next top-level key (non-indented line matching `word:`)
    remaining = text[start:]
    top_key_re = _re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*:", _re.MULTILINE)
    end = len(remaining)
    for mk in top_key_re.finditer(remaining):
        if mk.start() > 0:  # skip the first match (that's our key)
            end = mk.start()
            break
    snippet = remaining[:end].strip()
    try:
        parsed = _yaml.safe_load(snippet)
        if isinstance(parsed, dict) and key in parsed:
            val = parsed[key]
            return val if isinstance(val, list) else []
        return []
    except Exception:
        return []


def _infer_assets(components: list[dict]) -> list[dict]:
    """Build unique OTM assets from component phi_categories and a base availability asset."""
    seen: set[str] = set()
    assets: list[dict] = []
    for comp in components:
        attrs = comp.get("attributes", {}) if isinstance(comp, dict) else {}
        for cat in (attrs.get("phi_categories") or []):
            if not cat or cat in seen:
                continue
            seen.add(cat)
            assets.append({
                "name": cat,
                "id": cat.replace(" ", "-").lower(),
                "risk": {"confidentiality": "HIGH", "integrity": "HIGH", "availability": "MEDIUM"},
                "description": f"{cat} data",
            })
    if "system-availability" not in seen:
        assets.append({
            "name": "System Availability",
            "id": "system-availability",
            "risk": {"confidentiality": "LOW", "integrity": "MEDIUM", "availability": "HIGH"},
            "description": "Service uptime and availability",
        })
    return assets


def _infer_dataflows(components: list[dict], zones: list[dict]) -> list[dict]:
    """Infer OTM dataflows from component connects_to fields."""
    comp_map = {c["id"]: c for c in components if isinstance(c, dict) and "id" in c}
    zone_rating = {z["id"]: z.get("rating", 75) for z in zones if isinstance(z, dict) and "id" in z}

    seen_pairs: set[tuple] = set()
    dataflows: list[dict] = []

    def _comp_phi_asset_ids(comp: dict) -> list[str]:
        attrs = comp.get("attributes", {}) or {}
        return [c.replace(" ", "-").lower() for c in (attrs.get("phi_categories") or []) if c]

    for comp in components:
        if not isinstance(comp, dict):
            continue
        src_id = comp.get("id", "")
        connects_to = comp.get("connects_to") or []
        if isinstance(connects_to, str):
            connects_to = [connects_to]

        for dst_id in connects_to:
            if not dst_id or (src_id, dst_id) in seen_pairs:
                continue
            seen_pairs.add((src_id, dst_id))

            dst = comp_map.get(dst_id)
            if not dst:
                continue

            dst_type = dst.get("type", "service")
            protocol_map = {
                "database": "PostgreSQL", "queue": "SQS",
                "external-service": "HTTPS", "actor": "HTTPS",
            }
            protocol = protocol_map.get(dst_type, "HTTPS")

            src_zone_id = (comp.get("parent") or {}).get("trustZone", "")
            dst_zone_id = (dst.get("parent") or {}).get("trustZone", "")
            src_rating = zone_rating.get(src_zone_id, 75)

            if dst_type == "database":
                auth = "IAM Role"
            elif src_rating < 50:
                auth = "JWT"
            elif src_zone_id == dst_zone_id or (src_rating >= 75 and zone_rating.get(dst_zone_id, 75) >= 75):
                auth = "IAM Role"
            else:
                auth = "JWT"

            df_id = f"df-{src_id}-to-{dst_id}"
            if len(df_id) > 60:
                df_id = f"df-{src_id[:20]}-to-{dst_id[:20]}"

            src_assets = _comp_phi_asset_ids(comp)
            dst_assets = _comp_phi_asset_ids(dst)
            all_assets = list(dict.fromkeys(src_assets + dst_assets))

            dataflows.append({
                "name": f"{comp.get('name', src_id)} → {dst.get('name', dst_id)}",
                "id": df_id,
                "source": src_id,
                "destination": dst_id,
                "protocol": protocol,
                "assets": all_assets,
                "authentication": auth,
            })

    return dataflows


def assemble_otm_yaml(
    project: dict,
    zones: list,
    components: list,
    threats: list,
    mitigations: list,
    stacks: list,
    date: str,
) -> str:
    """Assemble a complete OTM v0.2.0 YAML from parsed pieces.

    Strips Python-internal routing fields (connects_to, receives_from) from components,
    renumbers threats T-001..N and mitigations M-001..N, and updates all cross-references.
    """
    import yaml as _yaml

    # Renumber threats and build old→new ID map
    threat_id_map: dict[str, str] = {}
    renumbered_threats = []
    for i, t in enumerate(threats, 1):
        if not isinstance(t, dict):
            continue
        new_id = f"T-{i:03d}"
        old_id = t.get("id", new_id)
        threat_id_map[old_id] = new_id
        renumbered_threats.append({**t, "id": new_id})

    # Renumber mitigations and update mitigatedThreats references
    renumbered_mitigations = []
    for i, m in enumerate(mitigations, 1):
        if not isinstance(m, dict):
            continue
        new_id = f"M-{i:03d}"
        old_refs = m.get("mitigatedThreats") or []
        new_refs = [threat_id_map.get(r, r) for r in old_refs]
        renumbered_mitigations.append({**m, "id": new_id, "mitigatedThreats": new_refs})

    # Clean components — strip Python-internal routing fields
    clean_components = []
    for comp in components:
        if not isinstance(comp, dict):
            continue
        c = {k: v for k, v in comp.items() if k not in ("connects_to", "receives_from")}
        clean_components.append(c)

    assets = _infer_assets(clean_components)
    dataflows = _infer_dataflows(components, zones)  # use original with connects_to

    otm = {
        "otmVersion": "0.2.0",
        "project": {
            "name": project.get("name", project.get("id", "")),
            "id": project.get("id", ""),
            "description": project.get("description", ""),
            "owner": "Security Lead",
            "attributes": {
                "stacks": stacks,
                "threat_model_date": date,
            },
        },
        "representations": [
            {"name": "Architecture Diagram", "id": "arch-diagram", "type": "diagram"}
        ],
        "trustZones": zones,
        "assets": assets,
        "components": clean_components,
        "dataflows": dataflows,
        "threats": renumbered_threats,
        "mitigations": renumbered_mitigations,
    }

    return _yaml.dump(otm, sort_keys=False, allow_unicode=True, default_flow_style=False)


def build_threat_discover_crew(project: dict, inventory: dict) -> "Crew":
    """Sequential crew: Architect analyzes pre-scanned context and outputs zones + components YAML.

    No tools — _build_threat_context already pre-reads key source and infra files.
    Giving the architect tools causes it to loop on knowledge_reader instead of working
    from the injected context.
    """
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    ac = load_bundle_agents(_KNOWLEDGE / "agents")

    ctx = _build_threat_context(project, inventory)

    architect_def = ac["architect"]
    architect = Agent(
        role=architect_def.role,
        goal=architect_def.goal,
        backstory=architect_def.backstory,
        llm=get_llm_for_tier("standard"),
        tools=[],  # no tools — all context provided via _build_threat_context
        max_iter=5,
        verbose=True,
    )

    discover_task = Task(
        name="threat_discover",
        description=f"{ctx}\n\n{tc['threat_discover'].description}",
        expected_output=tc["threat_discover"].expected_output,
        agent=architect,
    )

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        return Crew(
            agents=[architect],
            tasks=[discover_task],
            process=Process.sequential,
            verbose=True,
        )


def build_threat_component_threats_crew(
    project: dict,
    component: dict,
    context_text: str,
    threat_id_start: int = 1,
) -> "Crew":
    """Sequential crew: Architect outputs threats YAML for one component. No file reads."""
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    ac = load_bundle_agents(_KNOWLEDGE / "agents")

    import yaml as _yaml
    comp_yaml = _yaml.dump({"component": component}, sort_keys=False, allow_unicode=True, default_flow_style=False)
    comp_name = component.get("name", component.get("id", "unknown"))

    task_description = (
        f"{context_text}\n\n"
        f"## Component to analyse\n\n"
        f"Name: **{comp_name}**\n\n"
        f"```yaml\n{comp_yaml}```\n\n"
        f"## Threat ID start\n\n"
        f"Start threat IDs at T-{threat_id_start:03d}. "
        f"Your first threat is T-{threat_id_start:03d}, second is T-{threat_id_start+1:03d}, etc.\n\n"
        + tc["threat_component_threats"].description
    )

    architect_def = ac["architect"]
    architect = Agent(
        role=architect_def.role,
        goal=architect_def.goal,
        backstory=architect_def.backstory,
        llm=get_llm_for_tier("standard"),
        tools=[],
        max_iter=5,
        verbose=True,
    )

    threat_task = Task(
        name=f"threat_component_{component.get('id', 'unknown')}",
        description=task_description,
        expected_output=tc["threat_component_threats"].expected_output,
        agent=architect,
    )

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        return Crew(
            agents=[architect],
            tasks=[threat_task],
            process=Process.sequential,
            verbose=True,
        )


def build_threat_component_crew(
    project: dict,
    component: dict,
    context_text: str,
    threat_id_start: int = 1,
) -> "Crew":
    """Sequential crew: Architect outputs threats + mitigations for one component in one pass.

    Replaces the separate build_threat_component_threats_crew + build_threat_mitigations_crew
    calls. Intended for parallel execution via kickoff_async().
    """
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    ac = load_bundle_agents(_KNOWLEDGE / "agents")

    import yaml as _yaml
    comp_yaml = _yaml.dump({"component": component}, sort_keys=False, allow_unicode=True, default_flow_style=False)
    comp_name = component.get("name", component.get("id", "unknown"))

    task_description = (
        f"{context_text}\n\n"
        f"## Component to analyse\n\n"
        f"Name: **{comp_name}**\n\n"
        f"```yaml\n{comp_yaml}```\n\n"
        f"## Threat ID start\n\n"
        f"Start threat IDs at T-{threat_id_start:03d}. "
        f"Your first threat is T-{threat_id_start:03d}, second is T-{threat_id_start+1:03d}, etc.\n\n"
        + tc["threat_component"].description
    )

    architect_def = ac["architect"]
    architect = Agent(
        role=architect_def.role,
        goal=architect_def.goal,
        backstory=architect_def.backstory,
        llm=get_llm_for_tier("standard"),
        tools=[],
        max_iter=5,
        verbose=True,
    )

    task = Task(
        name=f"threat_component_{component.get('id', 'unknown')}",
        description=task_description,
        expected_output=tc["threat_component"].expected_output,
        agent=architect,
    )

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        return Crew(
            agents=[architect],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )


def build_threat_mitigations_crew(
    project: dict,
    threats_context: str,
    otm_context: str,
) -> "Crew":
    """Sequential crew: Architect outputs mitigations YAML for all threats. No file reads."""
    tc = load_bundle_tasks(_KNOWLEDGE / "tasks")
    ac = load_bundle_agents(_KNOWLEDGE / "agents")

    task_description = (
        f"**Project**: {project.get('name', project.get('id', ''))}\n\n"
        + otm_context
        + "\n\n"
        + threats_context
        + "\n\n"
        + tc["threat_mitigations"].description
    )

    architect_def = ac["architect"]
    architect = Agent(
        role=architect_def.role,
        goal=architect_def.goal,
        backstory=architect_def.backstory,
        llm=get_llm_for_tier("standard"),
        tools=[],
        max_iter=5,
        verbose=True,
    )

    mit_task = Task(
        name="threat_mitigations",
        description=task_description,
        expected_output=tc["threat_mitigations"].expected_output,
        agent=architect,
    )

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*cannot be serialized.*checkpointing.*")
        return Crew(
            agents=[architect],
            tasks=[mit_task],
            process=Process.sequential,
            verbose=True,
        )


_UX_STRUCTURE_SECTIONS = (
    "Detected stacks",
    "Detected architecture",
    "Architectural components",
    "Project summary",
)


def _format_ux_context(ux_input: dict) -> str:
    acs = "\n".join(f"- {ac}" for ac in ux_input.get("acceptance_criteria", []))
    structure = _load_structure_sections(*_UX_STRUCTURE_SECTIONS)
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
    decomp = _load_decomposition_diagram()
    if decomp:
        sections.append(f"## Service decomposition\n\n{decomp}")
    return "\n\n".join(sections)
