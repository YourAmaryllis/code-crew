"""
Interactive REPL for code-crew.

Slash commands:
  /jira <KEY> [--retries N]     — run a single ticket
  /sprint <name> [--retries N]  — plan + run a sprint (parallel where safe)
  /init                         — scaffold a new project in cwd
  /status                       — show active runs
  /details <KEY>                — toggle detail output for a ticket
  /help <message>               — inject guidance into a stuck flow
  /retry                        — force retry the stuck flow
  /abort [KEY]                  — abort a run
  /history                      — show past runs this session
  /exit / /quit                 — exit

Free text (no leading /) → chat agent with workspace access.

Config: ~/code-crew/config then local .env
"""

from __future__ import annotations

import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from rich.console import Console

from shared.home import CONFIG_FILE, ensure_home

_PROMPT_STYLE = Style.from_dict({
    "prompt":            "ansigreen bold",
    "prompt.stuck":      "ansiyellow bold",
    "prompt.stuck-key":  "ansiyellow",
})


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _bootstrap() -> None:
    ensure_home()
    load_dotenv(CONFIG_FILE)
    local_env = Path.cwd() / ".env"
    if local_env.exists():
        load_dotenv(local_env)


# ---------------------------------------------------------------------------
# REPL state
# ---------------------------------------------------------------------------

class ReplState:
    def __init__(self) -> None:
        # ticket_key → (TicketFlow, Future)
        self.active: dict[str, tuple] = {}
        self.history: list[str] = []
        self.lock = threading.Lock()

    def add(self, key: str, flow, future: Future) -> None:
        with self.lock:
            self.active[key] = (flow, future)
            self.history.append(key)

    def remove(self, key: str) -> None:
        with self.lock:
            self.active.pop(key, None)

    def get_stuck(self) -> list[str]:
        """Return keys of flows currently waiting for human input."""
        with self.lock:
            return [
                k for k, (flow, _) in self.active.items()
                if flow.state.status == "needs_help"
            ]

    def all_done(self) -> bool:
        with self.lock:
            return all(f.done() for _, f in self.active.values())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _bootstrap()

    # force_terminal=True: Rich outputs ANSI codes even when stdout is
    # redirected by patch_stdout() (which replaces sys.stdout with a
    # non-terminal wrapper, causing Rich to strip all colour by default).
    console = Console(force_terminal=True, highlight=False)
    state = ReplState()
    executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="flow")

    from code_crew.startup import run_checks
    from code_crew.ui import SprintUI

    ui = SprintUI(console=console)

    session = PromptSession(
        history=InMemoryHistory(),
        auto_suggest=AutoSuggestFromHistory(),
        style=_PROMPT_STYLE,
        mouse_support=False,
    )

    # patch_stdout redirects all print()/Console output so it appears above
    # the prompt_toolkit input bar rather than overwriting it.
    with patch_stdout():
        # --- Startup checks ---
        summary = run_checks()
        _print_startup_banner(console, summary)
        if not summary.git_ok:
            console.print(
                "\n[yellow]No git repo detected. Run [bold]/init[/bold] to scaffold "
                "a project, or cd into an existing repo.[/yellow]\n"
            )

        try:
            while True:
                stuck = state.get_stuck()
                if stuck:
                    prompt_msg = HTML(
                        f'<ansiyellow><b>({stuck[0]} needs help)</b></ansiyellow>'
                        f' <ansigreen><b>&gt;</b></ansigreen> '
                    )
                else:
                    prompt_msg = HTML('<ansigreen><b>&gt;</b></ansigreen> ')

                try:
                    line = session.prompt(prompt_msg)
                except KeyboardInterrupt:
                    continue          # Ctrl-C clears the line, stays in loop
                except (EOFError, SystemExit):
                    break             # Ctrl-D or /exit

                line = line.strip()
                if not line:
                    continue

                if line.startswith("/"):
                    _handle_slash(line, state, ui, executor, console)
                else:
                    _handle_chat(line, state, console)

        executor.shutdown(wait=False, cancel_futures=True)
        console.print("[dim]Bye.[/dim]")


# ---------------------------------------------------------------------------
# Slash command dispatcher
# ---------------------------------------------------------------------------

def _handle_slash(line: str, state: ReplState, ui: SprintUI, executor: ThreadPoolExecutor, console: Console) -> None:
    parts = line.split()
    cmd = parts[0].lower()

    if cmd in ("/exit", "/quit"):
        raise SystemExit(0)

    elif cmd == "/jira":
        if len(parts) < 2:
            console.print("[red]Usage: /jira <KEY> [--retries N][/red]")
            return
        key = parts[1].upper()
        retries = _parse_retries(parts[2:])
        _start_ticket(key, retries, state, ui, executor, console)

    elif cmd == "/sprint":
        if len(parts) < 2:
            console.print("[red]Usage: /sprint <name> [--retries N][/red]")
            return
        sprint_name = parts[1]
        retries = _parse_retries(parts[2:])
        _start_sprint(sprint_name, retries, state, ui, executor, console)

    elif cmd == "/init":
        _run_init(console)

    elif cmd == "/status":
        _show_status(state, console)

    elif cmd == "/details":
        key = parts[1].upper() if len(parts) > 1 else ""
        if not key:
            console.print("[red]Usage: /details <KEY>[/red]")
        else:
            ui.toggle_details(key)

    elif cmd == "/help":
        if len(parts) < 2:
            console.print("[red]Usage: /help <your guidance message>[/red]")
            return
        feedback = " ".join(parts[1:])
        _inject_help(feedback, state, console)

    elif cmd == "/retry":
        _inject_help("Please try again with the same approach.", state, console)

    elif cmd == "/abort":
        key = parts[1].upper() if len(parts) > 1 else ""
        _abort(key, state, console)

    elif cmd == "/history":
        if state.history:
            console.print("  " + ", ".join(state.history))
        else:
            console.print("[dim]No runs this session.[/dim]")

    else:
        console.print(f"[red]Unknown command: {cmd}[/red]  Type [bold]/help[/bold] ... or just ask a question.")


# ---------------------------------------------------------------------------
# Ticket / sprint runners
# ---------------------------------------------------------------------------

def _start_ticket(
    key: str,
    max_retries: int,
    state: ReplState,
    ui: SprintUI,
    executor: ThreadPoolExecutor,
    console: Console,
) -> None:
    from code_crew.flow import TicketFlow, TicketState
    from shared.issue_tracker import IssueTrackerClient, TrackerError, MissingFieldError
    from shared.user_memory import UserMemory

    console.print(f"[dim]Fetching {key}...[/dim]")
    try:
        tracker = IssueTrackerClient()
        ticket = tracker.get_ticket(key)
    except MissingFieldError as exc:
        console.print(f"[red]{exc}[/red]")
        return
    except TrackerError as exc:
        console.print(f"[red]Tracker error: {exc}[/red]")
        return

    memory = UserMemory()
    terms = [key] + ticket.acceptance_criteria + ticket.sprint_goal.split()
    user_context = memory.format_for_context(jira_key=key, terms=terms)

    flow_state = TicketState(
        jira_key=key,
        max_retries=max_retries,
        code_path=str(Path.cwd()),
    )
    # Inject ticket fields so _build_sprint_input has them
    flow_state.__dict__.update({
        "story": ticket.story,
        "acceptance_criteria": ticket.acceptance_criteria,
        "sprint_goal": ticket.sprint_goal,
        "figma_url": ticket.figma_url,
        "html_design_ref": ticket.html_design_ref,
        "add_refs": ticket.add_refs,
        "comment_context": ticket.comment_context,
        "user_context": user_context,
    })

    flow = TicketFlow(flow_state, on_status=ui.update)

    def run_and_cleanup():
        try:
            flow.run()
        finally:
            state.remove(key)

    future = executor.submit(run_and_cleanup)
    state.add(key, flow, future)
    console.print(f"[green]Started {key}[/green] (max retries: {max_retries})")


def _start_sprint(
    sprint_name: str,
    max_retries: int,
    state: ReplState,
    ui: SprintUI,
    executor: ThreadPoolExecutor,
    console: Console,
) -> None:
    from shared.issue_tracker import IssueTrackerClient, TrackerError
    from shared.sprint_planner import fetch_sprint_tickets, plan_execution_order
    from code_crew.worktree import WorktreeManager, WorktreeError

    console.print(f"[dim]Fetching sprint '{sprint_name}'...[/dim]")
    try:
        tracker = IssueTrackerClient()
        keys = tracker.list_sprint_tickets(sprint_name)
    except TrackerError as exc:
        console.print(f"[red]{exc}[/red]")
        return

    if not keys:
        console.print("[yellow]No tickets found in sprint.[/yellow]")
        return

    console.print(f"[dim]Fetching {len(keys)} tickets...[/dim]")
    tickets, skipped = fetch_sprint_tickets(keys)

    if skipped:
        for s in skipped:
            console.print(f"[yellow]  Skipped {s['key']}: {s['reason'][:80]}[/yellow]")

    if not tickets:
        console.print("[red]No actionable tickets found.[/red]")
        return

    waves = plan_execution_order(tickets)

    # Show plan and ask for confirmation
    console.print(f"\n[bold]Execution plan — {len(waves)} wave(s):[/bold]")
    for i, wave in enumerate(waves, 1):
        parallel = " (parallel)" if len(wave) > 1 else ""
        keys_str = ", ".join(t.key for t in wave)
        console.print(f"  Wave {i}{parallel}: {keys_str}")

    console.print("\nProceed? [Y/n] ", end="")
    answer = input().strip().lower()
    if answer and answer not in ("y", "yes"):
        console.print("[dim]Aborted.[/dim]")
        return

    wm = WorktreeManager(Path.cwd())

    def run_wave(wave_tickets) -> None:
        """Run tickets in a wave — parallel if >1, sequential if 1."""
        branch_prefix = "feature"
        wave_futures: list[Future] = []

        for ticket in wave_tickets:
            branch = f"{branch_prefix}/{ticket.key.lower()}-{_slugify(ticket.summary)}"
            code_path = str(Path.cwd())

            if len(wave_tickets) > 1:
                try:
                    wt = wm.create(ticket.key, branch)
                    code_path = str(wt.path)
                    console.print(f"[dim]  Worktree: {wt.path}[/dim]")
                except WorktreeError as exc:
                    console.print(f"[red]  Worktree failed for {ticket.key}: {exc}[/red]")
                    continue

            _start_ticket_from_object(ticket, max_retries, code_path, state, ui, executor, console)

        # Wait for all tickets in this wave before moving to next
        with state.lock:
            wave_keys = [t.key for t in wave_tickets]
            wave_futures = [f for k, (_, f) in state.active.items() if k in wave_keys]

        for f in wave_futures:
            f.result()  # blocks

        # Clean up worktrees for parallel tickets
        if len(wave_tickets) > 1:
            for ticket in wave_tickets:
                try:
                    wm.remove(ticket.key)
                except WorktreeError:
                    pass

    def run_all_waves():
        for wave in waves:
            run_wave(wave)

        # Pause before hard-dependency waves (those branching from main after a merge)
        console.print("\n[green]All waves complete.[/green]")

    executor.submit(run_all_waves)


def _start_ticket_from_object(ticket, max_retries, code_path, state, ui, executor, console):
    """Internal helper: start a flow for an already-fetched ticket object."""
    from code_crew.flow import TicketFlow, TicketState
    from shared.user_memory import UserMemory

    memory = UserMemory()
    terms = [ticket.key] + ticket.acceptance_criteria + ticket.sprint_goal.split()
    user_context = memory.format_for_context(jira_key=ticket.key, terms=terms)

    flow_state = TicketState(
        jira_key=ticket.key,
        max_retries=max_retries,
        code_path=code_path,
    )
    flow_state.__dict__.update({
        "story": ticket.story,
        "acceptance_criteria": ticket.acceptance_criteria,
        "sprint_goal": ticket.sprint_goal,
        "figma_url": getattr(ticket, "figma_url", ""),
        "html_design_ref": getattr(ticket, "html_design_ref", ""),
        "add_refs": getattr(ticket, "add_refs", []),
        "comment_context": getattr(ticket, "comment_context", ""),
        "user_context": user_context,
    })

    flow = TicketFlow(flow_state, on_status=ui.update)

    def run_and_cleanup():
        try:
            flow.run()
        finally:
            state.remove(ticket.key)

    future = executor.submit(run_and_cleanup)
    state.add(ticket.key, flow, future)


# ---------------------------------------------------------------------------
# /init scaffold
# ---------------------------------------------------------------------------

def _run_init(console: Console) -> None:
    import subprocess

    root = Path.cwd()
    console.print(f"[bold]Scaffolding project in {root}[/bold]")

    # git init
    if not (root / ".git").exists():
        subprocess.run(["git", "init"], cwd=str(root))
        console.print("  [green]✓[/green] git init")
    else:
        console.print("  [dim]git repo already exists[/dim]")

    # .code-crew.yaml
    config_file = root / ".code-crew.yaml"
    if not config_file.exists():
        console.print("Project name: ", end="")
        name = input().strip() or root.name
        console.print("Issue tracker [jira/linear]: ", end="")
        tracker = input().strip() or "jira"
        console.print("Project key (e.g. PROJ): ", end="")
        project_key = input().strip().upper() or "PROJ"

        config_file.write_text(
            f"project: {name}\n"
            f"issue_tracker: {tracker}\n"
            f"project_key: {project_key}\n",
            encoding="utf-8",
        )
        console.print(f"  [green]✓[/green] .code-crew.yaml written")
    else:
        console.print("  [dim].code-crew.yaml already exists[/dim]")

    # .gitignore
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".env\n.code-crew/\n__pycache__/\n*.pyc\n", encoding="utf-8")
        console.print("  [green]✓[/green] .gitignore written")

    console.print("\n[bold green]Done.[/bold green] Run [bold]/jira KEY[/bold] to start.")


# ---------------------------------------------------------------------------
# Help injection
# ---------------------------------------------------------------------------

def _inject_help(feedback: str, state: ReplState, console: Console) -> None:
    stuck = state.get_stuck()
    if not stuck:
        console.print("[yellow]No flow is currently waiting for help.[/yellow]")
        return
    key = stuck[0]
    flow, _ = state.active[key]
    flow.inject_feedback(feedback)
    console.print(f"[green]Feedback sent to {key}. Resuming...[/green]")


# ---------------------------------------------------------------------------
# Other commands
# ---------------------------------------------------------------------------

def _show_status(state: ReplState, console: Console) -> None:
    with state.lock:
        if not state.active:
            console.print("[dim]No active runs.[/dim]")
            return
        for key, (flow, future) in state.active.items():
            s = flow.state
            console.print(
                f"  [cyan]{key}[/cyan]  {s.status}  task={s.current_task or '—'}"
                f"  retries(cr={s.code_review_retries} sec={s.sec_review_retries} dod={s.dod_retries})"
            )


def _abort(key: str, state: ReplState, console: Console) -> None:
    with state.lock:
        if key and key not in state.active:
            console.print(f"[red]{key} not found in active runs.[/red]")
            return
        targets = [key] if key else list(state.active.keys())

    for k in targets:
        flow, future = state.active.get(k, (None, None))
        if future:
            future.cancel()
        state.remove(k)
        console.print(f"[yellow]Aborted {k}.[/yellow]")


# ---------------------------------------------------------------------------
# Chat passthrough
# ---------------------------------------------------------------------------

def _handle_chat(line: str, state: ReplState, console: Console) -> None:
    from code_crew.chat_agent import ask

    # Build sprint context from active flows
    sprint_ctx = _sprint_context_str(state)
    console.print("[dim]Thinking...[/dim]")
    try:
        answer = ask(line, sprint_context=sprint_ctx)
        console.print(answer)
    except Exception as exc:
        console.print(f"[red]Chat error: {exc}[/red]")


def _sprint_context_str(state: ReplState) -> str:
    with state.lock:
        if not state.active:
            return ""
        lines = []
        for key, (flow, _) in state.active.items():
            s = flow.state
            lines.append(
                f"{key}: status={s.status} task={s.current_task} "
                f"feedback={s.review_feedback[:200] if s.review_feedback else 'none'}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_retries(args: list[str]) -> int:
    env_default = int(os.environ.get("MAX_RETRIES", "3"))
    try:
        idx = args.index("--retries")
        return int(args[idx + 1])
    except (ValueError, IndexError):
        return env_default


def _slugify(text: str) -> str:
    import re
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:40]


def _print_startup_banner(console: Console, summary) -> None:
    from rich.table import Table

    console.print()
    console.print("[bold]code-crew[/bold]", end="  ")
    if summary.detected_stacks:
        console.print(f"[dim]stacks: {', '.join(summary.detected_stacks)}[/dim]")
    else:
        console.print()

    table = Table.grid(padding=(0, 2))
    table.add_column(width=6)
    table.add_column()
    table.add_column()

    for check in summary.checks:
        icon = "[green]✓[/green]" if check.ok else "[red]✗[/red]"
        detail = check.detail if check.ok else f"[dim]{check.fix}[/dim]"
        table.add_row(icon, check.name, detail)

    console.print(table)
    if summary.warnings or summary.errors:
        console.print(
            f"\n[dim]{summary.warnings} warning(s), {summary.errors} error(s).[/dim]"
        )
    console.print()
