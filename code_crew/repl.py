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

Config: ~/.code-crew/config then local .env
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

from shared.home import (
    CONFIG_FILE, CONFIG_YAML, PROFILES_DIR,
    ensure_home, list_profiles, profile_path, legacy_profile_path,
)
from shared.pt_console import PTConsole as _PTConsole

_PROMPT_STYLE = Style.from_dict({
    "prompt":            "ansigreen bold",
    "prompt.stuck":      "ansiyellow bold",
    "prompt.stuck-key":  "ansiyellow",
})


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _bootstrap(profile: str | None = None) -> None:
    from shared.config import load_yaml_config

    ensure_home()

    # 1. Global config — yaml wins; fall back to legacy dotenv
    if CONFIG_YAML.exists():
        load_yaml_config(CONFIG_YAML, override=False)
    elif CONFIG_FILE.exists():
        load_dotenv(CONFIG_FILE)

    # 2. Profile
    name = profile or os.environ.get("CODE_CREW_PROFILE") or _read_project_profile()
    if name:
        ppath = profile_path(name)                     # preferred: .yaml
        legacy = legacy_profile_path(name)             # fallback:  .env
        if ppath.exists():
            load_yaml_config(ppath, override=True)
            os.environ["CODE_CREW_PROFILE"] = name
        elif legacy.exists():
            load_dotenv(legacy, override=True)
            os.environ["CODE_CREW_PROFILE"] = name
            sys.stderr.write(
                f"code-crew: profile '{name}' using legacy .env format — "
                f"migrate to {ppath}\n"
            )
        else:
            sys.stderr.write(
                f"code-crew: profile '{name}' not found "
                f"(expected {ppath})\n"
            )

    # 3. Project yaml env: section (overrides profile)
    _apply_project_yaml_env()

    # 4. Local .env (legacy / secrets, highest priority)
    local_env = Path.cwd() / ".env"
    if local_env.exists():
        load_dotenv(local_env, override=True)


def _apply_project_yaml_env() -> None:
    """Apply env: section from .code-crew.yaml (project overrides profile)."""
    from shared.config import load_yaml_config
    cfg = Path.cwd() / ".code-crew.yaml"
    if cfg.exists():
        try:
            load_yaml_config(cfg, override=True)
        except Exception:
            pass


def _read_project_profile() -> str | None:
    """Read `profile:` key from .code-crew.yaml in cwd, if present."""
    return _read_project_yaml().get("profile") or None


def _read_project_yaml() -> dict:
    """Load .code-crew.yaml from cwd as a dict (empty dict if absent or invalid)."""
    import yaml
    cfg = Path.cwd() / ".code-crew.yaml"
    if not cfg.exists():
        return {}
    try:
        return yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _write_project_yaml(data: dict) -> None:
    """Write data to .code-crew.yaml in cwd, preserving unrelated keys."""
    import yaml
    cfg = Path.cwd() / ".code-crew.yaml"
    existing = _read_project_yaml()
    existing.update(data)
    cfg.write_text(yaml.dump(existing, default_flow_style=False), encoding="utf-8")


def _switch_profile(name: str) -> bool:
    """
    Switch to a different profile in the running process.
    Clears keys set by the current profile first, then loads the new one.
    Returns True if the profile was found and loaded.
    """
    from dotenv import dotenv_values
    from shared.config import load_yaml_config, yaml_env_keys

    # Clear keys set by the current profile
    current = os.environ.get("CODE_CREW_PROFILE", "")
    if current:
        curr_yaml = profile_path(current)
        curr_env  = legacy_profile_path(current)
        if curr_yaml.exists():
            for key in yaml_env_keys(curr_yaml):
                os.environ.pop(key, None)
        elif curr_env.exists():
            for key in dotenv_values(curr_env):
                os.environ.pop(key, None)

    ppath  = profile_path(name)
    legacy = legacy_profile_path(name)
    if ppath.exists():
        load_yaml_config(ppath, override=True)
    elif legacy.exists():
        load_dotenv(legacy, override=True)
    else:
        return False

    os.environ["CODE_CREW_PROFILE"] = name
    return True


# ---------------------------------------------------------------------------
# CrewAI verbosity control
# ---------------------------------------------------------------------------

# Tools the human doesn't need to see — pure background context loading.
_SUPPRESS_TOOLS = frozenset({
    "jira_view", "jira_sprint_list",   # ticket details already known
    "knowledge_reader", "sop_reader",  # internal doc lookups
    "memory_recall",                   # memory hydration
})


def _tool_label(tool_name: str, args) -> str | None:
    """Return a compact one-liner for a tool call, or None to suppress."""
    if tool_name in _SUPPRESS_TOOLS:
        return None

    if isinstance(args, str):
        try:
            import json
            args = json.loads(args)
        except Exception:
            args = {}

    if tool_name == "workspace_reader":
        op   = args.get("operation", "read_file") if isinstance(args, dict) else "read"
        path = args.get("path", "")               if isinstance(args, dict) else ""
        pat  = args.get("pattern", "")            if isinstance(args, dict) else ""
        if op == "read_file":
            return f"  [dim]reading {path}[/dim]"
        if op == "search":
            return f"  [dim]searching '{pat[:40]}' in {path or 'workspace'}[/dim]"
        if op == "list_dir":
            return f"  [dim]listing {path or '/'}[/dim]"
        return f"  [dim]{op} {path}[/dim]"

    if tool_name == "platform_shell":
        cmd = (args.get("command", "") if isinstance(args, dict) else str(args))
        cmd = cmd.strip().split("\n")[0][:70]
        return f"  [dim]$ {cmd}[/dim]"

    if tool_name == "bdd_runner":
        return "  [dim]running BDD tests[/dim]"

    if tool_name == "dod_checker":
        return "  [dim]checking definition of done[/dim]"

    # Generic fallback — show the name, drop noisy args
    label = tool_name.replace("_", " ")
    return f"  [dim]→ {label}[/dim]"


def _quieten_crewai_verbosity() -> None:
    """
    Replace CrewAI's verbose panels with compact one-liners on the console.

    We replace the singleton EventListener's formatter with a minimal subclass
    that only shows what a human needs to track progress:
      - which task is running (bold header)
      - which files are being read/written (dim one-liners)
      - when tests or DoD checks run
      - errors (always kept)

    Everything else (LLM calls, reasoning, tool output, observations) goes to
    Langfuse via OTLP.
    """
    try:
        from crewai.events.event_listener import EventListener
    except ImportError:
        return

    class _QuietFormatter:
        """
        Minimal console formatter — one-liners only, no Rich panels.

        Does NOT inherit from ConsoleFormatter so that __getattr__ reliably
        catches every handle_* method that isn't explicitly overridden here.
        (Inheritance would cause Python to find the parent's panel-printing
        implementations before reaching __getattr__.)
        """

        def __init__(self, console) -> None:
            self.verbose = False
            self.console = console

        # ── Tool calls — show one-liner on start, nothing on finish ─────

        # event_listener: handle_tool_usage_started(tool_name, tool_args, run_attempts)
        def handle_tool_usage_started(
            self, tool_name: str, tool_args="", run_attempts=None
        ) -> None:
            label = _tool_label(tool_name, tool_args)
            if label:
                self.console.print(label)

        def handle_tool_usage_finished(
            self, tool_name: str, output: str = "", run_attempts=None
        ) -> None:
            pass  # full output → Langfuse

        def handle_tool_usage_error(
            self, tool_name: str, error, run_attempts=None
        ) -> None:
            self.console.print(f"  [red]✗ {tool_name}: {str(error)[:120]}[/red]")

        # ── Task lifecycle ────────────────────────────────────────────────

        # event_listener: handle_task_started(source.id, task_name)
        def handle_task_started(self, task_id: str, task_name=None) -> None:
            raw = (task_name or task_id or "").strip()
            name = raw.split("\n")[0].replace("_", " ").strip()[:60]
            if name:
                self.console.print(f"\n[bold dim]{name}[/bold dim]")

        # event_listener: handle_task_status(source.id, agent_role, status, task_name)
        def handle_task_status(
            self, task_id: str, agent_role: str, status: str = "completed",
            task_name=None,
        ) -> None:
            raw = (task_name or task_id or "").strip()
            name = raw.split("\n")[0].replace("_", " ").strip()[:60]
            if status == "completed":
                self.console.print(f"  [dim green]✓ {name}[/dim green]")
            elif status in ("failed", "error"):
                self.console.print(f"  [red]✗ {name}[/red]")

        # ── Crew lifecycle ────────────────────────────────────────────────

        # event_listener: handle_crew_started(crew_name, source.id)
        def handle_crew_started(self, crew_name: str, source_id) -> None:
            pass  # ticket key already shown by the REPL

        # event_listener: handle_crew_status(crew_name, source.id, status, output?)
        def handle_crew_status(
            self, crew_name: str, source_id, status: str = "completed",
            output=None,
        ) -> None:
            if status == "completed":
                self.console.print("\n[bold green]Done.[/bold green]")
            elif status in ("failed", "error"):
                self.console.print("\n[bold red]Failed.[/bold red]")

        # ── Catch-all: suppress every other handle_* call ────────────────
        def __getattr__(self, name: str):
            if name.startswith("handle_"):
                return lambda *a, **kw: None
            raise AttributeError(name)

    # Replace the singleton formatter so all registered event closures use ours.
    try:
        listener = EventListener()
        original_console = listener.formatter.console
        listener.formatter = _QuietFormatter(original_console)
        # TraceCollectionListener shares the same formatter ref; update it too.
        from crewai.events.listeners.tracing.trace_listener import TraceCollectionListener
        tc = TraceCollectionListener()
        if tc.formatter is not None:
            tc.formatter = listener.formatter
    except Exception:
        pass  # non-fatal; user will just see more output than expected

    # Suppress crewai_core.PRINTER.print() calls — these print tool results,
    # agent reasoning, and task descriptions directly, bypassing the formatter.
    # set_suppress_console_output() is a ContextVar and doesn't propagate to
    # ThreadPoolExecutor workers, so we patch the method directly instead.
    # Our _QuietFormatter calls self.console.print() which is unaffected.
    try:
        from crewai_core.printer import Printer
        Printer.print = staticmethod(lambda *a, **kw: None)  # type: ignore[method-assign]
    except ImportError:
        pass


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

_BARE_EXIT = frozenset(("exit", "quit", "bye", ":q", "q"))


def main() -> None:
    import argparse
    import shutil

    parser = argparse.ArgumentParser(prog="code-crew", add_help=False)
    parser.add_argument(
        "--profile", "-p",
        default=None,
        metavar="NAME",
        help="Config profile to activate (~/.code-crew/profiles/<NAME>.env).",
    )
    args, _ = parser.parse_known_args()

    _bootstrap(profile=args.profile)

    # setup_langfuse() MUST run before any crewai import.
    # crewai/events/event_listener.py creates the EventListener singleton at
    # module level, which calls Telemetry.set_tracer() and installs CrewAI's own
    # OTLP provider.  Our provider must be in place first so CrewAI skips its own.
    from shared.telemetry import setup_langfuse
    langfuse_ok = setup_langfuse()

    from code_crew.startup import run_checks
    from code_crew.ui import SprintUI

    # --- Startup checks (before patch_stdout so Rich writes to the real terminal) ---
    summary = run_checks()

    # Clear screen and print banner directly to the real terminal.
    # This avoids patch_stdout's sys.stdout proxy which mangles ANSI escape codes.
    _clear_screen()
    banner_console = Console(force_terminal=True, highlight=False)
    _print_startup_banner(banner_console, summary, langfuse_ok=langfuse_ok)
    if not summary.git_ok:
        banner_console.print(
            "\n[yellow]No git repo detected. Run [bold]/init[/bold] to scaffold "
            "a project, or cd into an existing repo.[/yellow]"
        )

    # Push the prompt toward the bottom of the terminal.
    rows = shutil.get_terminal_size().lines
    padding = max(0, rows - 18)   # 18 ≈ banner height + some breathing room
    if padding:
        sys.stdout.write("\n" * padding)
        sys.stdout.flush()

    # Reduce CrewAI's default verbosity: replace full tool-output panels with
    # compact one-liners and silence the result dump (raw file contents, etc.)
    _quieten_crewai_verbosity()

    # raw=True tells StdoutProxy to call write_raw() instead of write().
    # write() replaces \x1b with ?, corrupting all ANSI colour codes.
    # write_raw() passes bytes through unchanged, so Rich panels from any code
    # (including CrewAI's ConsoleFormatter) render with correct colours.
    console = _PTConsole(force_terminal=True, highlight=False)
    state = ReplState()
    executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="flow")
    ui = SprintUI(console=console)

    session = PromptSession(
        history=InMemoryHistory(),
        auto_suggest=AutoSuggestFromHistory(),
        style=_PROMPT_STYLE,
        mouse_support=False,
    )

    with patch_stdout(raw=True):
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
                    continue
                except (EOFError, SystemExit):
                    break

                line = line.strip()
                if not line:
                    continue

                if line.lower() in _BARE_EXIT:
                    break
                elif line.startswith("/"):
                    _handle_slash(line, state, ui, executor, console)
                else:
                    _handle_chat(line, state, console)

        finally:
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

    elif cmd == "/stack":
        _handle_stack(parts[1:], console)

    elif cmd == "/profiles":
        _show_profiles(console)

    elif cmd == "/profile":
        if len(parts) < 2:
            current = os.environ.get("CODE_CREW_PROFILE", "")
            if current:
                console.print(f"Active profile: [bold cyan]{current}[/bold cyan]")
            else:
                console.print("[dim]No profile active (using global config).[/dim]")
            _show_profiles(console)
        else:
            name = parts[1]
            if _switch_profile(name):
                console.print(f"[green]Switched to profile [bold]{name}[/bold][/green]")
            else:
                console.print(
                    f"[red]Profile '{name}' not found.[/red]  "
                    f"Create [dim]{PROFILES_DIR / (name + '.env')}[/dim] to add it."
                )

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
    except Exception as exc:
        from shared.aws_auth import is_aws_auth_error, sso_login
        if not is_aws_auth_error(exc):
            raise
        if not _run_sso_login(console):
            return
        # Retry once after successful login
        try:
            tracker = IssueTrackerClient()
            ticket = tracker.get_ticket(key)
        except Exception as retry_exc:
            console.print(f"[red]Still failing after login: {retry_exc}[/red]")
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

    flow = TicketFlow(flow_state, on_status=ui.update, on_task_complete=ui.show_summary)

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

    flow = TicketFlow(flow_state, on_status=ui.update, on_task_complete=ui.show_summary)

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

_KNOWN_STACKS = (
    "go-backend",
    "typescript-react",
    "python",
    "terraform-aws",
)


def _handle_stack(args: list[str], console: Console) -> None:
    """
    /stack                       — show active stacks and source
    /stack <name> [name ...]     — set stacks (replaces all)
    /stack add <name> [name ...] — add to existing stacks
    /stack rm  <name> [name ...] — remove from existing stacks
    """
    from code_crew.startup import detect_stacks, _stacks_from_yaml

    root = Path.cwd()
    yaml_stacks = _stacks_from_yaml(root)
    active = detect_stacks(root)
    profile_name = os.environ.get("CODE_CREW_PROFILE", "")
    if os.environ.get("CODE_CREW_STACKS", "").strip():
        source = "[dim](CODE_CREW_STACKS env var)[/dim]"
    elif yaml_stacks is not None:
        source = "[dim](.code-crew.yaml)[/dim]"
    elif os.environ.get("_CODE_CREW_STACKS_PROFILE", "").strip():
        label = f"profile: {profile_name}" if profile_name else "profile"
        source = f"[dim]({label})[/dim]"
    else:
        source = "[dim](auto-detected)[/dim]"

    if not args:
        # Show current stacks
        if active:
            console.print(f"Active stacks {source}: [cyan]{', '.join(active)}[/cyan]")
        else:
            console.print(f"No stacks detected {source}.")
        console.print(f"[dim]Known stacks: {', '.join(_KNOWN_STACKS)}[/dim]")
        console.print("[dim]Usage: /stack <name>...  |  /stack add <name>...  |  /stack rm <name>...[/dim]")
        return

    sub = args[0].lower()

    if sub == "add":
        names = args[1:]
        if not names:
            console.print("[red]Usage: /stack add <name> [name ...][/red]")
            return
        current = list(yaml_stacks or active)
        for n in names:
            if n not in current:
                current.append(n)
        _write_project_yaml({"stacks": current})
        console.print(f"[green]Stacks set to:[/green] [cyan]{', '.join(current)}[/cyan]  [dim](.code-crew.yaml updated)[/dim]")

    elif sub in ("rm", "remove"):
        names = args[1:]
        if not names:
            console.print("[red]Usage: /stack rm <name> [name ...][/red]")
            return
        current = list(yaml_stacks or active)
        removed = [n for n in names if n in current]
        current = [s for s in current if s not in names]
        _write_project_yaml({"stacks": current})
        if removed:
            console.print(f"[green]Removed:[/green] {', '.join(removed)}  →  [cyan]{', '.join(current) or '(none)'}[/cyan]  [dim](.code-crew.yaml updated)[/dim]")
        else:
            console.print(f"[yellow]Nothing to remove — {', '.join(names)} not in active stacks.[/yellow]")

    else:
        # /stack <name> [name ...] — set all
        names = args  # sub is actually the first stack name
        _write_project_yaml({"stacks": names})
        console.print(f"[green]Stacks set to:[/green] [cyan]{', '.join(names)}[/cyan]  [dim](.code-crew.yaml updated)[/dim]")


def _run_sso_login(console: Console) -> bool:
    """
    Detect the active AWS profile, print a hint, run `aws sso login`, return success.
    Runs interactively so the browser flow works (subprocess inherits the terminal).
    """
    from shared.aws_auth import sso_login
    aws_profile = os.environ.get("AWS_PROFILE", "")
    profile_hint = f" --profile {aws_profile}" if aws_profile else ""
    console.print(
        f"[yellow]AWS credentials expired.[/yellow]  "
        f"Running [bold]aws sso login{profile_hint}[/bold]..."
    )
    ok = sso_login(profile=aws_profile or None)
    if ok:
        console.print("[green]Authenticated.[/green]")
    else:
        console.print(
            f"[red]SSO login failed or was cancelled.[/red]\n"
            f"[dim]Run manually: aws sso login{profile_hint}[/dim]"
        )
    return ok


def _show_profiles(console: Console) -> None:
    profiles = list_profiles()
    current = os.environ.get("CODE_CREW_PROFILE", "")
    if not profiles:
        console.print(
            f"[dim]No profiles found. Add [bold]{PROFILES_DIR}/<name>.env[/bold] to create one.[/dim]"
        )
        return
    console.print(f"[dim]Profiles ({PROFILES_DIR}):[/dim]")
    for p in profiles:
        marker = "  [bold cyan]●[/bold cyan] " if p == current else "    "
        console.print(f"{marker}[cyan]{p}[/cyan]")


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


def _clear_screen() -> None:
    sys.stdout.write('\033[2J\033[H')
    sys.stdout.flush()


def _print_startup_banner(console: Console, summary, langfuse_ok: bool = False) -> None:
    from rich.table import Table

    active_profile = os.environ.get("CODE_CREW_PROFILE", "")
    profile_str = f"  [dim cyan]profile: {active_profile}[/dim cyan]" if active_profile else ""
    trace_str   = "  [dim green]langfuse ✓[/dim green]" if langfuse_ok else "  [dim]no tracing[/dim]"

    console.print()
    console.print(f"[bold]code-crew[/bold]{profile_str}{trace_str}", end="  ")
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
