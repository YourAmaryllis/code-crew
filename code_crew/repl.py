"""
Interactive REPL for code-crew.

Slash commands:
  /design <KEY>                 — requirement → ADD/ADR design docs (runs before /issue)
  /ux <KEY>                     — Figma → component spec → implementation → UX review loop
  /issue <KEY> [--retries N]    — run a single ticket (Jira, Linear, or GitHub Issues)
  /sprint <name> [--retries N]  — plan + run a sprint (parallel where safe)
  /init                         — scaffold a new project in cwd
  /status                       — show active runs
  /details <KEY>                — toggle detail output for a ticket
  /help <message>               — inject guidance into a stuck flow
  /retry                        — force retry the stuck flow
  /abort [KEY]                  — abort a run
  /audit                        — full codebase audit: arch + security + compliance → report + optional issue creation
  /drift                        — assess and resolve infrastructure drift (Terraform, CI/CD, monitoring, config)
  /explore [path]               — scan platform dir tree, identify OTM projects, save as agent context
  /index [path]                 — build or rebuild the semantic code search index (auto-run by /explore)
  /threat [project-id]          — generate or refresh OTM threat models (all projects, or one by id)
  /mcp list|connect|disconnect|status  — manage MCP server connections
  /skills                       — list available/active skills
  /skill install <url|user/repo> — install skill(s) from GitHub repo or raw URL
  /skill <name>                 — activate a skill
  /skill off [name]             — deactivate one or all skills
  /ask <agent> <question>       — ask a specific agent directly (architect, security, engineer, qa, …)
  /session                      — show current session (name, path, recent exchanges)
  /session new [name]           — start a new session (default name: <project>-<date>)
  /session use <name>           — resume an existing session
  /session list                 — list all sessions for this project
  /loop                         — poll suspended CI run; resume flow on success
  /resume                       — same as /loop (manual trigger)
  /resume abort                 — clear suspended flow state
  /fix                          — install all missing tools
  /history                      — show past runs this session
  /context [KEY]                — show agent Q&A log; export to .code-crew/decisions/
  /exit / /quit                 — exit

Free text (no leading /) → chat agent with workspace access.

Config: ~/.code-crew/config.yaml (see .config.example.yaml)
"""

from __future__ import annotations

import os
import re
import sys
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path

# CrewAI 1.14.7 / Bedrock: format_answer() falls back to AgentFinish when the
# LLM response can't be parsed, causing a Pydantic serialization mismatch warning.
# The warning is harmless (we handle the incomplete output in flow._execute).
warnings.filterwarnings(
    "ignore",
    message="Pydantic serializer warnings",
    category=UserWarning,
    module="pydantic",
)

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from rich.console import Console

from shared.home import (
    CONFIG_YAML, PROFILES_DIR,
    ensure_home, list_profiles, profile_path,
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

    # 1. Global config
    if CONFIG_YAML.exists():
        load_yaml_config(CONFIG_YAML, override=False)

    # 2. Profile
    name = profile or os.environ.get("CODE_CREW_PROFILE") or _read_project_profile()
    if name:
        ppath = profile_path(name)
        if ppath.exists():
            load_yaml_config(ppath, override=True)
            os.environ["CODE_CREW_PROFILE"] = name
        else:
            sys.stderr.write(
                f"code-crew: profile '{name}' not found (expected {ppath})\n"
            )

    # 3. Project yaml (overrides profile)
    _apply_project_yaml_env()


def _apply_project_yaml_env() -> None:
    """Apply env: section from .code-crew/config.yaml (project overrides profile)."""
    from shared.config import load_yaml_config
    cfg = Path.cwd() / ".code-crew" / "config.yaml"
    if cfg.exists():
        try:
            load_yaml_config(cfg, override=True)
        except Exception:
            pass


def _read_project_profile() -> str | None:
    """Read `profile:` key from .code-crew/config.yaml in cwd, if present."""
    return _read_project_yaml().get("profile") or None


def _read_project_yaml() -> dict:
    """Load .code-crew/config.yaml from cwd as a dict (empty dict if absent or invalid)."""
    import yaml
    cfg = Path.cwd() / ".code-crew" / "config.yaml"
    if not cfg.exists():
        return {}
    try:
        return yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _write_project_yaml(data: dict) -> None:
    """Write data to .code-crew/config.yaml in cwd, preserving unrelated keys."""
    import yaml
    cfg_dir = Path.cwd() / ".code-crew"
    cfg_dir.mkdir(exist_ok=True)
    cfg = cfg_dir / "config.yaml"
    existing = _read_project_yaml()
    existing.update(data)
    cfg.write_text(yaml.dump(existing, default_flow_style=False), encoding="utf-8")


def _switch_profile(name: str) -> bool:
    """Switch to a different profile, clearing keys from the current one first."""
    from shared.config import load_yaml_config, yaml_env_keys

    current = os.environ.get("CODE_CREW_PROFILE", "")
    if current:
        curr_yaml = profile_path(current)
        if curr_yaml.exists():
            for key in yaml_env_keys(curr_yaml):
                os.environ.pop(key, None)

    ppath = profile_path(name)
    if not ppath.exists():
        return False

    load_yaml_config(ppath, override=True)
    os.environ["CODE_CREW_PROFILE"] = name
    return True


# ---------------------------------------------------------------------------
# CrewAI verbosity control
# ---------------------------------------------------------------------------

# Tools the human doesn't need to see — pure background context loading.
_SUPPRESS_TOOLS = frozenset({
    "jira_view", "jira_sprint_list",      # ticket details already known
    "knowledge_reader", "sop_reader",     # internal doc lookups
    "memory_recall",                      # memory hydration
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
    elif not isinstance(args, dict):
        # Pydantic model or other object — coerce to dict
        try:
            args = args.model_dump()
        except Exception:
            try:
                args = dict(args)
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
        if op == "find_files":
            glob = args.get("glob", "**/*") if isinstance(args, dict) else "**/*"
            loc = path or "."
            return f"  [dim]find_files {glob} in {loc}[/dim]"
        return f"  [dim]{op} {path}[/dim]"

    if tool_name == "platform_shell":
        cmd = (args.get("command", "") if isinstance(args, dict) else str(args))
        cmd = cmd.strip().split("\n")[0][:70]
        return f"  [dim]$ {cmd}[/dim]"

    if tool_name == "bdd_runner":
        return "  [dim]running BDD tests[/dim]"

    if tool_name == "dod_checker":
        return "  [dim]checking definition of done[/dim]"

    if tool_name in ("delegate_work_to_coworker", "Delegate work to coworker"):
        coworker = (args.get("coworker", "") if isinstance(args, dict) else "").strip()
        task = (args.get("task", "") if isinstance(args, dict) else "").strip()
        task_short = task[:70] + ("…" if len(task) > 70 else "")
        target = f" → [bold]{coworker}[/bold]" if coworker else ""
        return f"  [dim]manager{target}: {task_short}[/dim]"

    if tool_name in ("ask_question_to_coworker", "Ask question to coworker"):
        coworker = (args.get("coworker", "") if isinstance(args, dict) else "").strip()
        question = (args.get("question", "") if isinstance(args, dict) else "").strip()
        q_short = question[:70] + ("…" if len(question) > 70 else "")
        target = f" → [bold]{coworker}[/bold]" if coworker else ""
        return f"  [dim]manager{target}? {q_short}[/dim]"

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
            from datetime import datetime as _dt
            label = _tool_label(tool_name, tool_args)
            if label:
                ts = _dt.now().strftime("%H:%M:%S")
                # Inject timestamp inside the leading [dim] tag so it renders at the same dim level
                self.console.print(label.replace("[dim]", f"[dim]{ts}  ", 1))
            from shared.log import SessionLogger as _SL
            _SL.get().log_tool_call(tool_name, tool_args)

        def handle_tool_usage_finished(
            self, tool_name: str, output: str = "", run_attempts=None
        ) -> None:
            from shared.log import SessionLogger as _SL
            _SL.get().log_tool_result(tool_name, output or "")

        def handle_tool_usage_error(
            self, tool_name: str, error, run_attempts=None
        ) -> None:
            self.console.print(f"  [red]✗ {tool_name}: {str(error)[:120]}[/red]")

        # ── Task lifecycle ────────────────────────────────────────────────

        # event_listener: handle_task_started(source.id, task_name)
        def handle_task_started(self, task_id: str, task_name=None) -> None:
            pass  # already shown by the ► AGENT KEY TASK status line

        # event_listener: handle_task_status(source.id, agent_role, status, task_name)
        def handle_task_status(
            self, task_id: str, agent_role: str, status: str = "completed",
            task_name=None,
        ) -> None:
            from datetime import datetime as _dt
            ts = _dt.now().strftime("%H:%M:%S")
            raw = (task_name or task_id or "").strip()
            name = raw.split("\n")[0].replace("_", " ").strip()[:60]
            if status == "completed":
                self.console.print(f"  [dim]{ts}[/dim]  [dim green]✓ {name}[/dim green]")
            elif status in ("failed", "error"):
                self.console.print(f"  [dim]{ts}[/dim]  [red]✗ {name}[/red]")

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
        quiet = _QuietFormatter(original_console)
        listener.formatter = quiet
        # TraceCollectionListener shares the same formatter ref; update it too.
        from crewai.events.listeners.tracing.trace_listener import TraceCollectionListener
        tc = TraceCollectionListener()
        if tc.formatter is not None:
            tc.formatter = quiet
    except Exception:
        pass  # non-fatal; user will just see more output than expected

    # Register our own TaskFailedEvent handler to surface the error message.
    # CrewAI's built-in handler calls formatter.handle_task_status("failed")
    # but doesn't pass event.error, so the reason is otherwise invisible.
    crewai_event_bus = None
    try:
        from crewai.events import TaskFailedEvent
        from crewai.events.event_bus import crewai_event_bus

        @crewai_event_bus.on(TaskFailedEvent)
        def _on_task_failed(source, event: TaskFailedEvent) -> None:
            if event.error:
                quiet.console.print(f"  [red dim]{str(event.error)[:200]}[/red dim]")
    except Exception:
        pass

    # Wire crewai event bus → Langfuse OTel spans (no-op if Langfuse not configured).
    try:
        if crewai_event_bus is not None:
            from shared.telemetry import wire_crewai_events
            wire_crewai_events(crewai_event_bus)
    except Exception:
        pass

    # Silence crewai.flow.runtime ERROR logs — they surface internal exceptions
    # (including our format_answer patch TypeError) directly to the console.
    import logging
    logging.getLogger("crewai.flow.runtime").setLevel(logging.CRITICAL)

    # Patch format_answer so a list of tool calls raises instead of silently
    # becoming AgentFinish. CrewAI's bare except in format_answer converts any
    # parse failure into a final answer — when the LLM returns tool calls and
    # available_functions is None, the list reaches format_answer, parse() throws,
    # and the except wraps the list as AgentFinish(output=<list>), which then
    # causes TaskOutput(raw=<list>) to fail Pydantic. Raising here instead lets
    # the agent loop's exception handler deal with it (or our retry fires).
    try:
        import crewai.utilities.agent_utils as _agent_utils

        _orig_format_answer = _agent_utils.format_answer

        def _patched_format_answer(answer):
            if isinstance(answer, list):
                # Debug: show which tool calls the LLM tried to use as a final answer
                try:
                    parts = []
                    for item in answer[:3]:
                        if hasattr(item, "function"):
                            fn = item.function
                            args = (fn.arguments or "")[:80]
                            parts.append(f"{fn.name}({args})")
                        elif isinstance(item, dict) and "function" in item:
                            fn = item["function"]
                            args = str(fn.get("arguments", ""))[:80]
                            parts.append(f"{fn.get('name', '?')}({args})")
                    if parts:
                        quiet.console.print(
                            f"  [dim yellow]agent returned tool call(s) as final answer: "
                            f"{', '.join(parts)}[/dim yellow]"
                        )
                except Exception:
                    pass
                raise TypeError(
                    "format_answer received a list (tool calls) instead of str — "
                    "LLM hit max_iterations mid tool-call"
                )
            return _orig_format_answer(answer)

        _agent_utils.format_answer = _patched_format_answer
    except Exception:
        pass

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
        from shared.session import Session
        self.session: Session = Session.load_or_create(Session.default_name())

    def add(self, key: str, flow, future: Future) -> None:
        with self.lock:
            self.active[key] = (flow, future)
            self.history.append(key)

    def remove(self, key: str) -> None:
        with self.lock:
            self.active.pop(key, None)

    def get_stuck(self) -> list[str]:
        """Return keys of flows currently waiting for /help input."""
        with self.lock:
            return [
                k for k, (flow, _) in self.active.items()
                if flow.state.status == "needs_help"
            ]

    def get_pending_question(self):
        """Return the first PendingQuestion across active flows, or None."""
        with self.lock:
            for flow, _ in self.active.values():
                q = flow.relay.pending()
                if q is not None:
                    return q
        return None

    def answer_pending(self, text: str) -> None:
        """Send text as the answer to the first pending agent question."""
        with self.lock:
            for flow, _ in self.active.values():
                if flow.relay.pending() is not None:
                    flow.relay.answer(text)
                    return

    def context_log(self) -> list[dict]:
        """Accumulated Q&A from all flows (including finished ones)."""
        with self.lock:
            entries = []
            for flow, _ in self.active.values():
                entries.extend(flow.relay.log)
        return entries

    def all_done(self) -> bool:
        with self.lock:
            return all(f.done() for _, f in self.active.values())

    def session_tokens(self) -> str:
        """Return formatted cumulative token count across all active flows, or ''."""
        from code_crew.flow import _fmt_k
        with self.lock:
            total = sum(flow.state.session_tokens for flow, _ in self.active.values())
        return _fmt_k(total) if total else ""


# ---------------------------------------------------------------------------
# Input helper — works in both CLI startup and REPL slash-command context
# ---------------------------------------------------------------------------

def _read_line(console: "Console", prompt_text: str = "") -> str:
    """Print prompt_text via PTConsole (bypasses patch_stdout proxy) then read a line.

    Uses sys.__stdin__ so it works whether or not patch_stdout is active and
    regardless of whether an active PromptSession is running.
    """
    if prompt_text:
        console.print(prompt_text, end="")
    try:
        raw_stdin = getattr(sys, "__stdin__", sys.stdin) or sys.stdin
        line = raw_stdin.readline()
        return line.rstrip("\n")
    except (EOFError, KeyboardInterrupt):
        return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

_BARE_EXIT = frozenset(("exit", "quit", "bye", ":q", "q"))


def _looks_like_exit(text: str) -> bool:
    """Return True if the input is a 1-2 char typo of 'exit' or 'quit'."""
    t = re.sub(r"[^a-z]", "", text.lower())
    if not t or t in _BARE_EXIT:
        return False
    for target in ("exit", "quit"):
        if abs(len(t) - len(target)) <= 1:
            n = max(len(t), len(target))
            diffs = sum(a != b for a, b in zip(t.ljust(n), target.ljust(n)))
            if diffs <= 2:
                return True
    return False


def main() -> None:
    import argparse
    import shutil

    parser = argparse.ArgumentParser(prog="code-crew", add_help=False)
    parser.add_argument(
        "--profile", "-p",
        default=None,
        metavar="NAME",
        help="Config profile to activate (~/.code-crew/profiles/<NAME>.yaml).",
    )
    args, remaining = parser.parse_known_args()

    # Build startup slash command from positional argv, e.g.:
    #   code-crew issue LOOPLAT-92  →  /issue LOOPLAT-92
    #   code-crew explore           →  /explore
    #   code-crew init              →  /init
    #   code-crew audit             →  /audit
    # Any all-lowercase word is forwarded to _handle_slash, which validates it.
    # New commands are picked up automatically — no list to maintain here.
    startup_slash: str = ""
    if remaining and re.match(r'^[a-z]+$', remaining[0]):
        tail = " ".join(remaining[1:])
        startup_slash = f"/{remaining[0]} {tail}".strip()

    _bootstrap(profile=args.profile)

    from shared.log import SessionLogger as _SessionLogger
    _sl = _SessionLogger.get()
    _sl.setup()

    # setup_langfuse() MUST run before any crewai import.
    # crewai/events/event_listener.py creates the EventListener singleton at
    # module level, which calls Telemetry.set_tracer() and installs CrewAI's own
    # OTLP provider.  Our provider must be in place first so CrewAI skips its own.
    from shared.telemetry import setup_langfuse
    langfuse_ok, langfuse_error = setup_langfuse()

    from code_crew.startup import run_checks
    from code_crew.ui import SprintUI

    # --- Startup checks (before patch_stdout so Rich writes to the real terminal) ---
    summary = run_checks()

    # Clear screen and print banner directly to the real terminal.
    # This avoids patch_stdout's sys.stdout proxy which mangles ANSI escape codes.
    _clear_screen()
    banner_console = Console(force_terminal=True, highlight=False)
    _print_startup_banner(banner_console, summary)
    if _sl.enabled:
        banner_console.print(f"[dim]  logging → {_sl.log_path}[/dim]")
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

    # Key bindings: Enter submits, Alt+Enter (Esc then Enter) inserts a newline.
    # Shift+Enter isn't a distinct escape sequence in most terminals, so Alt+Enter
    # is the standard workaround for "newline without submit."
    _repl_kb = KeyBindings()

    @_repl_kb.add("enter")
    def _submit(event):
        event.current_buffer.validate_and_handle()

    @_repl_kb.add("escape", "enter")
    def _newline(event):
        event.current_buffer.insert_text("\n")

    session = PromptSession(
        history=InMemoryHistory(),
        auto_suggest=AutoSuggestFromHistory(),
        style=_PROMPT_STYLE,
        mouse_support=False,
        multiline=True,
        key_bindings=_repl_kb,
        # Continuation line (lines 2+ in multi-line input): align under first char of "> "
        prompt_continuation=lambda width, _line, _wrap: " " * width,
    )

    # Dispatch the startup command BEFORE patch_stdout so that input() calls
    # (e.g. in /init or /audit human gates) reach the real terminal, not the
    # prompt_toolkit stdout proxy (which has no active prompt to flush into yet).
    # PTConsole routes output through print_formatted_text regardless, so
    # background-thread output is safe once the REPL loop starts below.
    if startup_slash:
        try:
            _handle_slash(startup_slash, state, ui, executor, console)
        except Exception as _e:
            console.print(f"[red]{_e}[/red]")

    # Timer thread: invalidate the active prompt every second so the elapsed-time
    # counter in _build_prompt updates even when no other output is printing.
    def _invalidate_loop() -> None:
        while True:
            time.sleep(1)
            app = getattr(session, "app", None)
            if app is not None:
                try:
                    app.invalidate()
                except Exception:
                    pass

    threading.Thread(target=_invalidate_loop, daemon=True, name="status-ticker").start()

    with patch_stdout(raw=True):
        _last_interrupt = 0.0
        try:
            while True:
                # Show consultation panel once when the gate fires (must happen
                # before session.prompt() blocks so the panel appears immediately).
                pending_q = state.get_pending_question()
                stuck = state.get_stuck()
                if stuck and not pending_q:
                    _key = stuck[0]
                    _entry = state.active.get(_key)
                    if _entry:
                        _flow, _ = _entry
                        if (
                            _flow.state.needs_help_gate == "chief_architect_consultation"
                            and _key not in _shown_consultation
                        ):
                            _show_consultation_panel(_key, _flow, console)
                            _shown_consultation.add(_key)

                try:
                    line = session.prompt(
                        lambda: _build_prompt(state),
                        bottom_toolbar=lambda: _bottom_toolbar(state),
                    )
                except KeyboardInterrupt:
                    now = time.monotonic()
                    if now - _last_interrupt < 2.0:
                        break  # second Ctrl-C within 2s → exit
                    _last_interrupt = now
                    console.print("[dim]  (Ctrl-C again or /exit to quit)[/dim]")
                    continue
                except (EOFError, SystemExit):
                    break

                line = line.strip()
                if not line:
                    continue

                from shared.log import SessionLogger as _SL
                _SL.get().log_user_input(line)

                # Re-read state after prompt returns (may have changed while waiting)
                pending_q = state.get_pending_question()
                stuck = state.get_stuck()

                try:
                    if pending_q:
                        state.answer_pending(line)
                    elif _is_in_consultation(stuck, state) and not line.startswith("/"):
                        _inject_help(line, state, console)
                    elif line.lower() in _BARE_EXIT:
                        break
                    elif _looks_like_exit(line):
                        console.print("[dim]Did you mean [bold]/exit[/bold]?[/dim]")
                    elif line.startswith("/"):
                        _handle_slash(line, state, ui, executor, console)
                    else:
                        _handle_chat(line, state, console)
                except KeyboardInterrupt:
                    console.print("\n[dim]Interrupted.[/dim]")

        finally:
            executor.shutdown(wait=False, cancel_futures=True)
            from shared.telemetry import flush as _lf_flush
            _lf_flush()
            from shared.log import SessionLogger as _SL2
            _SL2.get().close()
            console.print("[dim]Bye.[/dim]")
            # os._exit bypasses atexit handlers (including concurrent.futures'
            # _python_exit which blocks forever joining live flow threads).
            # Telemetry is already flushed synchronously above.
            os._exit(0)


# ---------------------------------------------------------------------------
# Slash command dispatcher
# ---------------------------------------------------------------------------

def _handle_slash(line: str, state: ReplState, ui: SprintUI, executor: ThreadPoolExecutor, console: Console) -> None:
    parts = line.split()
    cmd = parts[0].lower()

    if cmd in ("/exit", "/quit"):
        raise SystemExit(0)

    elif cmd == "/design":
        if len(parts) < 2:
            console.print("[red]Usage: /design <KEY>[/red]")
            return
        key = parts[1].upper()
        _start_design(key, state, executor, console)

    elif cmd == "/ux":
        if len(parts) < 2:
            console.print("[red]Usage: /ux <KEY>[/red]")
            return
        key = parts[1].upper()
        _start_ux(key, state, executor, console)

    elif cmd == "/issue":
        if len(parts) < 2:
            console.print("[red]Usage: /issue <KEY> [--retries N][/red]")
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

    elif cmd == "/mcp":
        _handle_mcp(parts[1:], console)

    elif cmd in ("/skill", "/skills"):
        _handle_skill(parts[1:], console)

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

    elif cmd in ("/loop", "/resume"):
        if cmd == "/resume" and len(parts) > 1 and parts[1].lower() == "abort":
            _clear_flow_state()
            console.print("[yellow]Suspended flow cleared.[/yellow]")
        else:
            _handle_loop_tick(state, ui, executor, console)

    elif cmd == "/fix":
        _run_fix(console)

    elif cmd == "/audit":
        _start_verify(console)

    elif cmd == "/drift":
        _start_drift(console)

    elif cmd == "/index":
        target = parts[1] if len(parts) > 1 else ""
        _run_index(target, console)

    elif cmd == "/domain":
        _handle_domain(parts[1:], console)

    elif cmd == "/explore":
        target = parts[1] if len(parts) > 1 else ""
        _run_explore(target, console)

    elif cmd == "/threat":
        target = parts[1] if len(parts) > 1 else ""
        _run_threat(target, console)

    elif cmd == "/history":
        if state.history:
            console.print("  " + ", ".join(state.history))
        else:
            console.print("[dim]No runs this session.[/dim]")

    elif cmd == "/context":
        key = parts[1].upper() if len(parts) > 1 else ""
        _show_context(key, state, console)

    elif cmd == "/stack":
        _handle_stack(parts[1:], console)

    elif cmd == "/session":
        _handle_session(parts[1:], state, console)

    elif cmd == "/ask":
        if len(parts) < 3:
            from code_crew.chat_agent import AGENT_ALIASES
            known = ", ".join(sorted(set(AGENT_ALIASES.values())))
            console.print(f"[red]Usage: /ask <agent> <question>[/red]")
            console.print(f"[dim]Agents: {known}[/dim]")
            return
        agent_name = parts[1].lower()
        question = " ".join(parts[2:])
        _ask_agent(agent_name, question, state, console)

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
                    f"Create [dim]{PROFILES_DIR / (name + '.yaml')}[/dim] to add it."
                )

    else:
        console.print(f"[red]Unknown command: {cmd}[/red]  Type [bold]/help[/bold] ... or just ask a question.")


# ---------------------------------------------------------------------------
# MCP command
# ---------------------------------------------------------------------------

def _handle_mcp(args: list[str], console: Console) -> None:
    """Handle /mcp subcommands: list | connect <name> | disconnect <name> | status."""
    from shared.mcp_registry import MCPRegistry

    sub = args[0].lower() if args else "status"
    registry = MCPRegistry.get()

    if sub == "list":
        try:
            config = registry.load_config().get("servers", {})
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/red]")
            console.print(f"[dim]Create {registry.config_path()} to configure MCP servers.[/dim]")
            return
        if not config:
            console.print(f"[dim]No MCP servers configured. Add them to {registry.config_path()}[/dim]")
            return
        connected = set(registry.connected_names())
        for name, cfg in config.items():
            status = "[green]●[/green] connected" if name in connected else "[dim]○ disconnected[/dim]"
            cmd = cfg.get("command", "")
            agents = ", ".join(cfg.get("agents", [])) or "all agents"
            console.print(f"  {status}  [bold]{name}[/bold]  ({cmd})  → {agents}")

    elif sub == "connect":
        if len(args) < 2:
            console.print("[red]Usage: /mcp connect <name>[/red]")
            return
        name = args[1]
        console.print(f"[dim]Connecting to {name}...[/dim]")
        try:
            tools = registry.connect(name)
            console.print(f"[green]Connected: {name}[/green] — {len(tools)} tool(s)")
            for t in tools:
                console.print(f"  [dim]· {t.name}[/dim]")
        except (KeyError, RuntimeError) as exc:
            console.print(f"[red]{exc}[/red]")

    elif sub == "disconnect":
        if len(args) < 2:
            console.print("[red]Usage: /mcp disconnect <name>[/red]")
            return
        name = args[1]
        registry.disconnect(name)
        console.print(f"[dim]Disconnected: {name}[/dim]")

    elif sub == "status":
        connected = registry.connected_names()
        if not connected:
            console.print("[dim]No MCP servers connected. Use /mcp connect <name>[/dim]")
            return
        for name in connected:
            try:
                tools = registry.connect(name)  # no-op if already connected, returns tools
                console.print(f"  [green]●[/green] [bold]{name}[/bold] — {len(tools)} tool(s)")
            except Exception:
                console.print(f"  [red]●[/red] [bold]{name}[/bold] — error")

    else:
        console.print("[yellow]Usage: /mcp list | /mcp connect <name> | /mcp disconnect <name> | /mcp status[/yellow]")


def _install_skill(source: str, console: Console) -> None:
    """Fetch and install skill(s) from a GitHub repo or raw URL into ~/.code-crew/skills/."""
    import json
    import re
    import urllib.request

    dest = Path.home() / ".code-crew" / "skills"
    dest.mkdir(parents=True, exist_ok=True)

    def _fetch(url: str) -> str:
        with urllib.request.urlopen(url, timeout=10) as r:  # noqa: S310
            return r.read().decode()

    def _save(name: str, content: str) -> None:
        out = dest / f"{name}.md"
        out.write_text(content, encoding="utf-8")
        console.print(f"  [green]✓[/green] installed [bold]{name}[/bold] → {out}")

    # Direct raw .md URL
    if source.startswith("http") and source.endswith(".md"):
        name = Path(source).stem
        _save(name, _fetch(source))
        return

    # Normalise to owner/repo
    gh_match = re.match(r"(?:https?://github\.com/)?([^/]+/[^/]+?)(?:\.git)?/?$", source)
    if not gh_match:
        console.print(f"[red]Cannot parse:[/red] {source}. Use github.com/user/repo or user/repo.")
        return

    owner_repo = gh_match.group(1)
    api_base = f"https://api.github.com/repos/{owner_repo}/contents"

    def _api(path: str = "") -> list[dict]:
        url = f"{api_base}/{path}".rstrip("/")
        try:
            return json.loads(_fetch(url))
        except Exception:
            return []

    # Try skills/<name>/SKILL.md pattern (caveman-style repo)
    entries = _api("skills")
    if isinstance(entries, list) and entries:
        installed = 0
        for entry in entries:
            if entry.get("type") != "dir":
                continue
            skill_name = entry["name"]
            skill_url = f"https://raw.githubusercontent.com/{owner_repo}/main/skills/{skill_name}/SKILL.md"
            try:
                _save(skill_name, _fetch(skill_url))
                installed += 1
            except Exception:
                pass  # skill subdir exists but no SKILL.md — skip
        if installed:
            console.print(f"\n[dim]Run [bold]/skills[/bold] to see installed skills.[/dim]")
            return

    # Fallback: grab all root-level .md files (single-skill repos)
    root_entries = _api()
    if isinstance(root_entries, list):
        for entry in root_entries:
            if entry.get("type") == "file" and entry["name"].upper() in ("SKILL.md", "CLAUDE.md"):
                name = owner_repo.split("/")[1]
                _save(name, _fetch(entry["download_url"]))
                console.print(f"\n[dim]Run [bold]/skills[/bold] to see installed skills.[/dim]")
                return

    console.print(f"[red]No skills found[/red] in {owner_repo}. Expected skills/<name>/SKILL.md or a root SKILL.md.")


def _handle_skill(args: list[str], console: Console) -> None:
    """Handle /skill and /skills commands.

    /skills            — list available and active skills (all sources)
    /skill <name>      — activate a skill
    /skill off         — deactivate all skills
    /skill off <name>  — deactivate one skill
    """
    from code_crew.crew import _skill_search_dirs

    # Collect all available skills across search dirs, noting source
    # Later dirs are shadowed by earlier ones (project > user > bundled)
    seen: dict[str, str] = {}  # name → source label
    source_labels = ["project", "user", "bundled"]
    for label, d in zip(source_labels, _skill_search_dirs()):
        if d.exists():
            for p in sorted(d.glob("*.md")):
                if p.stem not in seen:
                    seen[p.stem] = label

    current_raw = os.environ.get("CODE_CREW_SKILLS", "").strip()
    active = {s for s in (current_raw.split(",") if current_raw else []) if s}

    if not args or args[0] == "list":
        if not seen:
            console.print("[dim]No skills found. Add .md files to .code-crew/skills/, ~/.code-crew/skills/, or knowledge/skills/[/dim]")
            return
        for name in sorted(seen):
            marker = "[green]●[/green]" if name in active else "[dim]○[/dim]"
            console.print(f"  {marker} {name}  [dim]({seen[name]})[/dim]")
        if active:
            console.print(f"\n[dim]Active: {', '.join(sorted(active))}[/dim]")
        return

    if args[0] == "install":
        if len(args) < 2:
            console.print("[red]Usage: /skill install <github-url|user/repo|raw-url>[/red]")
            return
        _install_skill(args[1], console)
        return

    if args[0] == "off":
        if len(args) > 1:
            name = args[1].lower()
            active.discard(name)
            os.environ["CODE_CREW_SKILLS"] = ",".join(sorted(active))
            console.print(f"[yellow]Skill deactivated:[/yellow] {name}")
        else:
            os.environ["CODE_CREW_SKILLS"] = ""
            console.print("[yellow]All skills deactivated.[/yellow]")
        return

    name = args[0].lower()
    if name not in seen:
        console.print(f"[red]Unknown skill:[/red] {name}. Run [bold]/skills[/bold] to see available.")
        return
    active.add(name)
    os.environ["CODE_CREW_SKILLS"] = ",".join(sorted(active))
    console.print(f"[green]Skill activated:[/green] {name}  [dim]({seen[name]})[/dim]")


# ---------------------------------------------------------------------------
# Design / ticket / sprint runners
# ---------------------------------------------------------------------------

def _start_design(
    key: str,
    state: ReplState,
    executor: ThreadPoolExecutor,
    console: Console,
) -> None:
    """Run the design flow: ticket → agents draft → Chief Architect loop → commit/push/PR → ticket comment."""
    from code_crew.flow import DesignFlow, DesignReviewExhausted
    from shared.issue_tracker import IssueTrackerClient, TrackerError, MissingFieldError

    console.print(f"[dim]Fetching {key}...[/dim]")
    try:
        tracker = IssueTrackerClient()
        ticket = tracker.get_ticket(key)
    except MissingFieldError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        console.print("[dim]Continuing — design flow will read the full ticket anyway.[/dim]")
        ticket = None
    except TrackerError as exc:
        console.print(f"[red]Tracker error: {exc}[/red]")
        return

    design_input: dict = {
        "issue_key": key,
        "issue_summary": ticket.summary if ticket else key,
        "requirement": ticket.story if ticket else "",
        "acceptance_criteria": ticket.acceptance_criteria if ticket else [],
        "raw_ticket": ticket.raw if ticket else "",
    }

    def on_task_complete(issue_key: str, task_name: str, summary: str) -> None:
        console.print(f"[dim]  ✓ {task_name}: {summary[:120]}[/dim]")

    flow = DesignFlow(design_input, on_task_complete=on_task_complete)

    def run() -> None:
        try:
            flow.run()
            console.print(f"\n[bold green]Design complete for {key}[/bold green]")
            finalize_out = flow.task_outputs.get("design_finalize", "")
            if finalize_out:
                console.print(finalize_out[:2000])
        except DesignReviewExhausted as exc:
            console.print(f"\n[yellow]{exc}[/yellow]")
        except Exception as exc:
            console.print(f"\n[red]Design flow error: {exc}[/red]")
        finally:
            state.remove(f"DESIGN:{key}")

    future = executor.submit(run)
    state.add(f"DESIGN:{key}", flow, future)
    console.print(
        f"[green]Design flow started for {key}[/green] — "
        "agents will present the design for your review as Chief Architect"
    )


def _start_ux(
    key: str,
    state: ReplState,
    executor: ThreadPoolExecutor,
    console: Console,
) -> None:
    """Run the UX flow: Figma spec extraction → component implementation → UX review loop."""
    from code_crew.flow import UxFlow, DesignReviewExhausted
    from shared.issue_tracker import IssueTrackerClient, TrackerError, MissingFieldError

    console.print(f"[dim]Fetching {key}...[/dim]")
    try:
        tracker = IssueTrackerClient()
        ticket = tracker.get_ticket(key)
    except MissingFieldError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        ticket = None
    except TrackerError as exc:
        console.print(f"[red]Tracker error: {exc}[/red]")
        return

    # Detect active stack from project structure
    structure_path = Path.cwd() / ".code-crew" / "structure.md"
    stack = "unknown"
    if structure_path.exists():
        text = structure_path.read_text(encoding="utf-8")
        for s in ("typescript-react", "go-backend", "python"):
            if s in text:
                stack = s
                break

    ux_input: dict = {
        "issue_key": key,
        "issue_summary": ticket.summary if ticket else key,
        "figma_url": ticket.figma_url if ticket else "",
        "acceptance_criteria": ticket.acceptance_criteria if ticket else [],
        "stack": stack,
    }

    def on_task_complete(issue_key: str, task_name: str, summary: str) -> None:
        console.print(f"[dim]  ✓ {task_name}: {summary[:120]}[/dim]")

    flow = UxFlow(ux_input, on_task_complete=on_task_complete)

    def run() -> None:
        try:
            flow.run()
            console.print(f"\n[bold green]UX flow complete for {key}[/bold green]")
            review_out = flow.task_outputs.get("ux_review", "")
            if review_out:
                console.print(review_out[:1000])
        except DesignReviewExhausted as exc:
            console.print(f"\n[yellow]{exc}[/yellow]")
        except Exception as exc:
            console.print(f"\n[red]UX flow error: {exc}[/red]")
        finally:
            state.remove(f"UX:{key}")

    future = executor.submit(run)
    state.add(f"UX:{key}", flow, future)
    figma_note = f"Figma: {ux_input['figma_url']}" if ux_input["figma_url"] else "no Figma URL — UX Lead will ask"
    console.print(f"[green]UX flow started for {key}[/green] — {figma_note}")


def _start_ticket(
    key: str,
    max_retries: int,
    state: ReplState,
    ui: SprintUI,
    executor: ThreadPoolExecutor,
    console: Console,
) -> None:
    from code_crew.flow import TicketFlow, TicketState, _load_checkpoint, _delete_checkpoint
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

    # Check for an existing checkpoint and ask whether to resume
    checkpoint = _load_checkpoint(key)
    if checkpoint:
        n = len(checkpoint)
        console.print(
            f"[yellow]Checkpoint found for {key} "
            f"({n} task(s) complete: {', '.join(checkpoint)}).[/yellow]\n"
            f"Resume? [Y/n] ",
            end="",
        )
        answer = input().strip().lower()
        if answer and answer not in ("y", "yes"):
            _delete_checkpoint(key)
            checkpoint = {}
            console.print("[dim]Starting fresh.[/dim]")

    flow_state = TicketState(
        jira_key=key,
        max_retries=max_retries,
        code_path=str(Path.cwd()),
    )
    if checkpoint:
        flow_state.task_outputs = checkpoint
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

    flow = TicketFlow(
        flow_state,
        on_status=ui.update,
        on_task_complete=_task_complete_callback(ui, state.session, flow_state.task_outputs),
    )

    def run_and_cleanup():
        from code_crew.flow import StagingHandedOff
        from datetime import datetime, timezone
        try:
            flow.run()
        except StagingHandedOff as exc:
            _save_flow_state({
                "jira_key": key,
                "phase": exc.phase,
                "run_handle": exc.run_handle,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "poll_interval": _POLL_INTERVALS.get(exc.phase, 60),
                "attempt": 1,
                "max_attempts": max_retries,
                "context": {
                    "code_path": flow_state.code_path,
                    "max_retries": max_retries,
                },
            })
            console.print(
                f"\n[yellow]  {key}: {exc.phase} kicked off — flow suspended.[/yellow]\n"
                f"[dim]  Use /loop or /resume to poll status and continue.[/dim]"
            )
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

    flow = TicketFlow(
        flow_state,
        on_status=ui.update,
        on_task_complete=_task_complete_callback(ui, state.session, flow_state.task_outputs),
    )

    def run_and_cleanup():
        from code_crew.flow import StagingHandedOff
        from datetime import datetime, timezone
        try:
            flow.run()
        except StagingHandedOff as exc:
            _save_flow_state({
                "jira_key": ticket.key,
                "phase": exc.phase,
                "run_handle": exc.run_handle,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "poll_interval": _POLL_INTERVALS.get(exc.phase, 60),
                "attempt": 1,
                "max_attempts": max_retries,
                "context": {
                    "code_path": code_path,
                    "max_retries": max_retries,
                },
            })
            console.print(
                f"\n[yellow]  {ticket.key}: {exc.phase} kicked off — flow suspended.[/yellow]\n"
                f"[dim]  Use /loop or /resume to poll status and continue.[/dim]"
            )
        finally:
            state.remove(ticket.key)

    future = executor.submit(run_and_cleanup)
    state.add(ticket.key, flow, future)


# ---------------------------------------------------------------------------
# Async CI flow state — /loop and /resume
# ---------------------------------------------------------------------------

_POLL_INTERVALS: dict[str, int] = {
    "promote_staging":    60,
    "staging_verification": 120,
    "smoke_test":         60,
}

_PHASE_SUCCESS_SIGNALS: dict[str, str] = {
    "promote_staging":    "STAGING DEPLOYED",
    "staging_verification": "STAGING VERIFIED",
    "smoke_test":         "SMOKE PASSED",
}


def _save_flow_state(state: dict) -> None:
    import json as _json
    path = Path.cwd() / ".code-crew" / "flow-state.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(_json.dumps(state, indent=2), encoding="utf-8")


def _load_flow_state() -> dict | None:
    import json as _json
    path = Path.cwd() / ".code-crew" / "flow-state.json"
    if not path.exists():
        return None
    try:
        return _json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _clear_flow_state() -> None:
    (Path.cwd() / ".code-crew" / "flow-state.json").unlink(missing_ok=True)


def _poll_ci_run(run_handle: dict) -> dict:
    """Poll any job handle (gh_actions, shell, ecs). Delegates to AsyncJobTool."""
    import json as _json
    from shared.tools.async_job import AsyncJobTool as _AsyncJobTool
    raw = _AsyncJobTool()._run(operation="poll", handle=run_handle)
    try:
        return _json.loads(raw)
    except Exception:
        return {"status": "unknown", "error": raw[:200]}


def _inject_checkpoint_output(jira_key: str, phase: str, output: str) -> None:
    """Write a synthetic task output into the checkpoint so the flow replays it on resume."""
    import json as _json
    from code_crew.flow import _checkpoint_path
    path = _checkpoint_path(jira_key)
    existing: dict = {}
    if path.exists():
        try:
            existing = _json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing[phase] = output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps(existing), encoding="utf-8")


def _handle_loop_tick(
    repl_state: "ReplState",
    ui: "SprintUI",
    executor: "ThreadPoolExecutor",
    console: "Console",
) -> None:
    """Poll the suspended CI run and resume the flow on success."""
    flow_state = _load_flow_state()
    if not flow_state:
        console.print("[dim]No suspended flow.[/dim]")
        return

    phase = flow_state.get("phase", "")
    jira_key = flow_state.get("jira_key", "?")
    run_handle = flow_state.get("run_handle", {})
    attempt = flow_state.get("attempt", 1)
    max_attempts = flow_state.get("max_attempts", 3)

    run_id = run_handle.get("run_id", "?")
    console.print(f"[dim]Polling {phase} (run {run_id}) for {jira_key}…[/dim]")

    result = _poll_ci_run(run_handle)
    status = result.get("status", "unknown")
    url = result.get("url", "")
    url_str = f" — {url}" if url else ""

    if status in ("pending", "running"):
        label = "queued" if status == "pending" else "running"
        console.print(f"[dim]  {phase}: {label}{url_str}[/dim]")
        return

    if status == "success":
        console.print(f"[green]  {phase}: success{url_str}[/green]")
        _resume_from_flow_state(flow_state, result, repl_state, ui, executor, console)
        return

    # Failure
    console.print(f"[red]  {phase}: {status}{url_str}[/red]")
    if attempt >= max_attempts:
        console.print(f"[red]  Max attempts ({max_attempts}) reached — manual intervention required.[/red]")
        console.print(f"[dim]  Run /resume abort to clear state, or fix CI and /resume to retry.[/dim]")
    else:
        flow_state["attempt"] = attempt + 1
        _save_flow_state(flow_state)
        console.print(
            f"[dim]  Attempt {attempt}/{max_attempts} failed — "
            f"state saved. Run /resume again after CI is retriggered.[/dim]"
        )


def _resume_from_flow_state(
    flow_state: dict,
    ci_result: dict,
    repl_state: "ReplState",
    ui: "SprintUI",
    executor: "ThreadPoolExecutor",
    console: "Console",
) -> None:
    """Resume a suspended TicketFlow after a CI run completes successfully."""
    jira_key = flow_state["jira_key"]
    phase = flow_state["phase"]
    run_handle = flow_state["run_handle"]
    context = flow_state.get("context", {})
    run_id = run_handle.get("run_id", "")
    url = ci_result.get("url", "")

    signal = _PHASE_SUCCESS_SIGNALS.get(phase)
    if not signal:
        console.print(f"[red]Unknown phase in flow state: {phase!r}[/red]")
        return

    synthetic = f"{signal} — CI run {run_id} succeeded.{' URL: ' + url if url else ''}"
    _inject_checkpoint_output(jira_key, phase, synthetic)

    if phase == "smoke_test":
        _clear_flow_state()
        console.print(f"[bold green]{jira_key}: flow complete — smoke test passed.[/bold green]")
        return

    _clear_flow_state()
    console.print(f"[dim]Resuming {jira_key} from checkpoint (after {phase})…[/dim]")
    _start_ticket_resumed(jira_key, context, repl_state, ui, executor, console)


def _start_ticket_resumed(
    jira_key: str,
    context: dict,
    repl_state: "ReplState",
    ui: "SprintUI",
    executor: "ThreadPoolExecutor",
    console: "Console",
) -> None:
    """Re-start a TicketFlow from its checkpoint after async CI completion."""
    from code_crew.flow import TicketFlow, TicketState, _load_checkpoint
    from shared.issue_tracker import IssueTrackerClient, TrackerError, MissingFieldError
    from shared.user_memory import UserMemory

    max_retries = context.get("max_retries", 3)
    code_path = context.get("code_path", str(Path.cwd()))

    checkpoint = _load_checkpoint(jira_key)
    if not checkpoint:
        console.print(f"[red]No checkpoint found for {jira_key} — cannot resume.[/red]")
        return

    console.print(f"[dim]Fetching {jira_key}…[/dim]")
    try:
        ticket = IssueTrackerClient().get_ticket(jira_key)
    except (MissingFieldError, TrackerError) as exc:
        console.print(f"[yellow]{exc} — resuming without fresh ticket context[/yellow]")
        ticket = None

    memory = UserMemory()
    terms = [jira_key] + (ticket.acceptance_criteria if ticket else [])
    user_context = memory.format_for_context(jira_key=jira_key, terms=terms)

    flow_state = TicketState(
        jira_key=jira_key,
        max_retries=max_retries,
        code_path=code_path,
    )
    flow_state.task_outputs = checkpoint
    flow_state.__dict__.update({
        "story":               ticket.story if ticket else "",
        "acceptance_criteria": ticket.acceptance_criteria if ticket else [],
        "sprint_goal":         ticket.sprint_goal if ticket else "",
        "figma_url":           getattr(ticket, "figma_url", "") if ticket else "",
        "html_design_ref":     getattr(ticket, "html_design_ref", "") if ticket else "",
        "add_refs":            getattr(ticket, "add_refs", []) if ticket else [],
        "comment_context":     getattr(ticket, "comment_context", "") if ticket else "",
        "user_context":        user_context,
    })

    flow = TicketFlow(
        flow_state,
        on_status=ui.update,
        on_task_complete=_task_complete_callback(ui, repl_state.session, flow_state.task_outputs),
    )

    def run_and_cleanup():
        from code_crew.flow import StagingHandedOff
        from datetime import datetime, timezone
        try:
            flow.run()
        except StagingHandedOff as exc:
            _save_flow_state({
                "jira_key": jira_key,
                "phase": exc.phase,
                "run_handle": exc.run_handle,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "poll_interval": _POLL_INTERVALS.get(exc.phase, 60),
                "attempt": 1,
                "max_attempts": max_retries,
                "context": {
                    "code_path": code_path,
                    "max_retries": max_retries,
                },
            })
            console.print(
                f"\n[yellow]  {jira_key}: {exc.phase} kicked off — flow suspended.[/yellow]\n"
                f"[dim]  Use /loop or /resume to poll status and continue.[/dim]"
            )
        finally:
            repl_state.remove(jira_key)

    future = executor.submit(run_and_cleanup)
    repl_state.add(jira_key, flow, future)
    console.print(f"[green]Resumed {jira_key}[/green] (max retries: {max_retries})")


# ---------------------------------------------------------------------------
# /init scaffold
# ---------------------------------------------------------------------------

def _scan_project(root: Path) -> dict:
    """
    Pure-Python signal scan. Returns discovered config values (dotted keys)
    plus two special keys used only by /explore:
      "_stacks"  — list[str] of detected stack names
      "_svc_dirs" — list[str] of top-level dirs containing source files
    Called by both /init (config keys only) and /explore Phase 1.
    """
    import json as _json

    _SKIP = {".git", "vendor", "node_modules", "__pycache__", ".terraform",
             ".idea", ".vscode", "dist", "build", "coverage", ".next"}

    found: dict = {}

    # --- stacks (file-extension / manifest signals) ---
    stacks: list[str] = []
    if any(root.rglob("go.mod")):
        stacks.append("go-backend")
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            pkg = _json.loads(pkg_json.read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if any(k in deps for k in ("react", "next", "@types/react")):
                stacks.append("typescript-react")
        except Exception:
            pass
    elif any(root.rglob("*.tsx")):
        stacks.append("typescript-react")
    if list(root.glob("requirements*.txt")) or (root / "pyproject.toml").exists():
        stacks.append("python")
    if any(root.rglob("*.java")) or (root / "pom.xml").exists() or any(root.rglob("build.gradle")):
        stacks.append("java")
    if any(root.rglob("*.rb")) or (root / "Gemfile").exists():
        stacks.append("ruby")
    if any(root.rglob("*.rs")) or (root / "Cargo.toml").exists():
        stacks.append("rust")
    if any(root.rglob("*.tf")):
        stacks.append("terraform")
        for f in list(root.rglob("*.tf"))[:10]:
            try:
                if "aws" in f.read_text():
                    stacks.append("terraform-aws")
                    break
            except Exception:
                pass
    if list(root.rglob("*task-definition*.json")) or list(root.rglob("*ecs*.tf")):
        stacks.append("ecs-deployment")
    if any(root.rglob("*.ipynb")):
        stacks.append("ai-ml")
    elif list(root.glob("requirements*.txt")):
        for f in list(root.glob("requirements*.txt"))[:5]:
            try:
                if any(kw in f.read_text().lower() for kw in
                       ("torch", "transformers", "openai", "anthropic", "langchain", "bedrock")):
                    stacks.append("ai-ml")
                    break
            except Exception:
                pass
    _feature_files = [f for f in root.rglob("*.feature") if not any(p in _SKIP for p in f.parts)]
    if _feature_files:
        stacks.append("bdd-testing")
        # Unique parent dirs of feature files (relative to root), up to 5
        _feat_dirs_seen: set[str] = set()
        _feat_dirs: list[str] = []
        for _ff in _feature_files[:20]:
            try:
                _rel = str(_ff.parent.relative_to(root))
                if _rel not in _feat_dirs_seen:
                    _feat_dirs_seen.add(_rel)
                    _feat_dirs.append(_rel)
            except ValueError:
                pass
        found["_feature_dirs"] = _feat_dirs[:5]
    found["_stacks"] = stacks

    # --- service dirs (top-level dirs with source files) ---
    ext_src = ("*.go", "*.py", "*.ts", "*.tsx", "*.java", "*.rb", "*.rs")
    svc_dirs = [
        d.name for d in sorted(root.iterdir())
        if d.is_dir() and d.name not in _SKIP and not d.name.startswith(".")
        and any(any(d.rglob(ext)) for ext in ext_src)
    ][:8]
    found["_svc_dirs"] = svc_dirs

    # --- test dirs (dirs clearly for testing) ---
    _test_dir_names = {"test", "tests", "spec", "specs", "integration", "e2e", "__tests__",
                       "bdd", "features", "testdata"}
    _test_dirs_found: list[str] = []
    for _td in root.rglob("*"):
        if not _td.is_dir() or any(p in _SKIP for p in _td.parts):
            continue
        if _td.name.lower() in _test_dir_names or _td.name.lower().startswith("test"):
            try:
                _test_dirs_found.append(str(_td.relative_to(root)))
            except ValueError:
                pass
    found["_test_dirs"] = _test_dirs_found[:10]

    # --- migration tool ---
    if (root / "alembic.ini").exists():
        found["db.migration_tool"] = "alembic"
    elif (root / "atlas.hcl").exists() or (root / "atlas.sum").exists():
        found["db.migration_tool"] = "atlas"
    else:
        for mf in list(root.rglob("*.sql"))[:20]:
            try:
                if "-- +goose" in mf.read_text(encoding="utf-8", errors="ignore"):
                    found["db.migration_tool"] = "goose"
                    break
            except OSError:
                pass

    # --- migration schema path ---
    for candidate in ("migrations", "alembic/versions", "db/migrations"):
        if (root / candidate).is_dir():
            found["db.schema_path"] = candidate + "/"
            break
    if "db.schema_path" not in found:
        for _mdir in list(root.rglob("migrations"))[:5]:
            if not _mdir.is_dir() or any(p in _SKIP for p in _mdir.parts):
                continue
            try:
                found["db.schema_path"] = str(_mdir.relative_to(root)) + "/"
                break
            except ValueError:
                pass

    # --- compliance standards (scan docs for mentions) ---
    _COMPLIANCE_KEYWORDS = {
        "hipaa":   ["hipaa", "phi ", "protected health information", "hitech"],
        "soc2":    ["soc 2", "soc2", "soc type", "trust service criteria"],
        "gdpr":    ["gdpr", "general data protection", "data subject", "right to erasure"],
        "ccpa":    ["ccpa", "california consumer privacy", "right to know"],
        "pci-dss": ["pci dss", "pci-dss", "payment card industry", "cardholder data"],
        "fips":    ["fips 140", "fips-140"],
    }
    _compliance_standards: list[str] = []
    _doc_search_dirs = [root / "designs", root / "docs", root]
    _doc_files_checked: list[Path] = []
    for _ddir in _doc_search_dirs:
        if not _ddir.is_dir():
            continue
        for _df in list(_ddir.rglob("*.md"))[:30] + list(_ddir.rglob("*.txt"))[:5]:
            if any(p in _SKIP for p in _df.parts):
                continue
            _doc_files_checked.append(_df)
            if len(_doc_files_checked) > 40:
                break
    for _df in _doc_files_checked:
        try:
            _text = _df.read_text(encoding="utf-8", errors="ignore").lower()
            for _std, _keywords in _COMPLIANCE_KEYWORDS.items():
                if _std not in _compliance_standards and any(kw in _text for kw in _keywords):
                    _compliance_standards.append(_std)
        except OSError:
            pass
    if _compliance_standards:
        found["_compliance_standards"] = _compliance_standards

    # --- testing framework ---
    if (root / "pytest.ini").exists() or (root / "setup.cfg").exists():
        found["testing.framework"] = "pytest"
    elif (root / "pyproject.toml").exists():
        try:
            text = (root / "pyproject.toml").read_text(encoding="utf-8")
            if "[tool.pytest" in text:
                found["testing.framework"] = "pytest"
        except OSError:
            pass
    if "testing.framework" not in found:
        if list(root.glob("jest.config.*")) or list(root.glob("jest.config.ts")):
            found["testing.framework"] = "jest"
        elif (root / "go.mod").exists():
            found["testing.framework"] = "go-test"

    # --- BDD ---
    if any(root.rglob("*.feature")):
        found["testing.bdd"] = "true"

    # --- API doc standard ---
    _openapi_names = {"swagger.json", "swagger.yaml", "openapi.json", "openapi.yaml"}
    _api_doc_found = False
    for candidate in ("docs/swagger.json", "docs/swagger.yaml", "docs/openapi.json",
                       "docs/openapi.yaml", "openapi.yaml", "openapi.json"):
        if (root / candidate).exists():
            found["api.doc_standard"] = "openapi"
            found["api.doc_path"] = candidate
            _api_doc_found = True
            break
    if not _api_doc_found:
        for _af in list(root.rglob("swagger.yaml")) + list(root.rglob("swagger.json")) + \
                    list(root.rglob("openapi.yaml")) + list(root.rglob("openapi.json")):
            if any(p in _SKIP for p in _af.parts):
                continue
            try:
                found["api.doc_standard"] = "openapi"
                found["api.doc_path"] = str(_af.relative_to(root))
                break
            except ValueError:
                pass

    # --- CI/CD tooling (collect all; terraform + GHA often coexist) ---
    ci_methods: list[str] = []
    if (root / ".github" / "workflows").is_dir() and list((root / ".github" / "workflows").glob("*.yml")):
        ci_methods.append("github-actions")
    if (root / ".gitlab-ci.yml").exists():
        ci_methods.append("gitlab-ci")
    if (root / "Jenkinsfile").exists():
        ci_methods.append("jenkins")
    if any(f.name in ("docker-compose.yml", "docker-compose.yaml")
           for f in root.iterdir() if f.is_file()):
        ci_methods.append("docker-compose")
    if (root / "cdk.json").exists() or any(root.rglob("cdk.ts")):
        ci_methods.append("aws-cdk")
    if (root / "pulumi.yaml").exists():
        ci_methods.append("pulumi")
    if (root / "fly.toml").exists():
        ci_methods.append("fly-io")
    if (root / "vercel.json").exists() or (root / ".vercel").is_dir():
        ci_methods.append("vercel")
    if any(root.rglob("*.tf")):
        ci_methods.append("terraform")
    if ci_methods:
        found["ci.deployment_methods"] = ci_methods

    # --- build / test / lint commands ---
    # Priority: Makefile targets > package.json scripts > stack heuristics
    _commands: dict[str, str] = {}

    makefile = root / "Makefile"
    if makefile.exists():
        import re as _re
        try:
            mk_text = makefile.read_text(encoding="utf-8", errors="ignore")
            mk_lines = mk_text.splitlines()
            _mk_targets: dict[str, str] = {}
            for _i, _line in enumerate(mk_lines):
                _m = _re.match(r'^([a-z][a-z0-9_\-]*)[\s]*:', _line)
                if _m:
                    _tname = _m.group(1)
                    for _j in range(_i + 1, min(_i + 6, len(mk_lines))):
                        _cmd = mk_lines[_j].lstrip('\t').strip().lstrip('@-').strip()
                        if _cmd and not _cmd.startswith('#'):
                            _mk_targets[_tname] = _cmd
                            break
            for _k, _v in _mk_targets.items():
                if _k in ("test", "tests"):
                    _commands.setdefault("test", f"make {_k}")
                elif _k in ("build", "compile"):
                    _commands.setdefault("build", f"make {_k}")
                elif _k in ("lint", "check", "vet"):
                    _commands.setdefault("lint", f"make {_k}")
                elif _k in ("audit", "vuln", "security"):
                    _commands.setdefault("audit", f"make {_k}")
                elif _k in ("typecheck", "type-check", "tsc"):
                    _commands.setdefault("typecheck", f"make {_k}")
        except Exception:
            pass

    # Check root package.json first, then find the primary frontend package.json.
    # Priority: directories named "frontend", "web", "app", "ui", or inside "portal/".
    _pkg_jsons_to_check: list[tuple[int, str, "Path"]] = []
    if (root / "package.json").exists():
        _pkg_jsons_to_check.append((0, "", root / "package.json"))
    import json as _j2
    _SKIP_PARTS = {"node_modules", ".next", "dist", "build", "coverage", ".turbo"}
    _FRONTEND_PRIO = {"frontend": 10, "web": 8, "app": 8, "ui": 7, "portal": 5}
    for _pj in root.rglob("package.json"):
        if any(skip in _pj.parts for skip in _SKIP_PARTS):
            continue
        if _pj == root / "package.json":
            continue
        try:
            _pd = _j2.loads(_pj.read_text())
            _deps = {**_pd.get("dependencies", {}), **_pd.get("devDependencies", {})}
            if not any(k in _deps for k in ("react", "next", "@types/react", "vite")):
                continue
            _rel = str(_pj.parent.relative_to(root))
            # Score: higher = more likely to be the primary frontend
            _score = sum(
                _FRONTEND_PRIO.get(part, 0) for part in _pj.parts
            )
            _pkg_jsons_to_check.append((_score, _rel, _pj))
        except Exception:
            continue
    # Sort descending by score so primary frontend comes first
    _pkg_jsons_to_check.sort(key=lambda x: -x[0])
    _pkg_jsons_to_check = _pkg_jsons_to_check[:3]

    for _, _pkg_rel, _pkg_path in _pkg_jsons_to_check:
        try:
            _pkg = _j2.loads(_pkg_path.read_text())
            _scripts = _pkg.get("scripts", {})
            _cd = f"cd {_pkg_rel} && " if _pkg_rel else ""
            if "test" in _scripts:
                _commands.setdefault("test_frontend", f"{_cd}npm test")
            if "build" in _scripts:
                _commands.setdefault("build_frontend", f"{_cd}npm run build")
            if any(k in _scripts for k in ("typecheck", "type-check", "tsc")):
                _tc = next(k for k in ("typecheck", "type-check", "tsc") if k in _scripts)
                _commands.setdefault("typecheck", f"{_cd}npm run {_tc}")
            elif "build" in _scripts and "tsc" in _scripts.get("build", ""):
                _commands.setdefault("typecheck", f"{_cd}npx tsc --noEmit")
            if any(k in _scripts for k in ("lint", "eslint")):
                _commands.setdefault("lint_frontend", f"{_cd}npm run lint")
        except Exception:
            pass

    # Stack-level fallbacks when no Makefile / script entry found
    if any(root.rglob("go.mod")):
        _commands.setdefault("test", "go test ./... -count=1 -timeout 120s")
        _commands.setdefault("build", "go build ./...")
        if list(root.rglob(".golangci.yml")) or list(root.rglob(".golangci.yaml")):
            _commands.setdefault("lint", "golangci-lint run ./...")
        _commands.setdefault("audit", "go mod verify")
    if (root / "pyproject.toml").exists() or list(root.glob("requirements*.txt")):
        _commands.setdefault("test", "pytest")
        _commands.setdefault("lint", "ruff check .")
        _commands.setdefault("audit", "pip-audit")
    if _commands:
        found["_commands"] = _commands

    # --- architecture style (low-confidence heuristic; LLM phase overrides) ---
    all_dirs = {p.name for p in root.rglob("*") if p.is_dir() and p.name not in _SKIP}
    if "ports" in all_dirs and ("driving" in all_dirs or "driven" in all_dirs):
        found["architecture.style"] = "hexagonal"
    elif "domain" in all_dirs and "application" in all_dirs and any(
        (root / "domain" / sub).exists() for sub in ("model", "services", "repositories")
    ):
        found["architecture.style"] = "onion"
    elif "usecases" in all_dirs or ("domain" in all_dirs and "adapters" in all_dirs):
        found["architecture.style"] = "clean"
    elif ("handlers" in all_dirs or "controllers" in all_dirs) and "services" in all_dirs and (
        "repository" in all_dirs or "storage" in all_dirs or "repositories" in all_dirs
    ):
        found["architecture.style"] = "layered"

    # --- Terraform structure ---
    # Only scan if Terraform files were found
    if any(root.rglob("*.tf")):
        import re as _tf_re
        _tf: dict = {}

        # Locate the directory whose immediate children are environment names (dev/staging/prod/…)
        # Search up to 4 levels deep so it works regardless of nesting (ops/loopora/, infra/, etc.)
        _ENV_NAMES = {"dev", "staging", "prod", "production", "development", "qa", "uat", "sandbox"}
        _LAYER_NAMES = {"bootstrap", "core-infra", "app-infra", "core", "app", "shared",
                        "networking", "security", "data", "services"}
        _SKIP_TF = {".git", "vendor", "node_modules", "__pycache__", ".terraform",
                    ".idea", ".vscode", "dist", "build", "coverage", ".next", "modules"}
        _tf_root: "Path | None" = None

        def _has_env_children(d: "Path") -> bool:
            try:
                children = [c for c in d.iterdir() if c.is_dir() and c.name in _ENV_NAMES]
                return len(children) >= 2
            except (PermissionError, OSError):
                return False

        def _search_tf_root(base: "Path", depth: int) -> "Path | None":
            if depth == 0:
                return None
            try:
                for entry in sorted(base.iterdir()):
                    if not entry.is_dir() or entry.name in _SKIP_TF:
                        continue
                    if _has_env_children(entry):
                        return entry
                    result = _search_tf_root(entry, depth - 1)
                    if result:
                        return result
            except (PermissionError, OSError):
                pass
            return None

        _tf_root = _search_tf_root(root, 4)

        if _tf_root:
            _rel_tf_root = str(_tf_root.relative_to(root))
            _tf["root"] = _rel_tf_root

            # Collect environments and their layers
            _envs: dict[str, list[str]] = {}
            for _env_dir in sorted(_tf_root.iterdir()):
                if not _env_dir.is_dir() or _env_dir.name not in _ENV_NAMES:
                    continue
                _layers = [
                    d.name for d in sorted(_env_dir.iterdir())
                    if d.is_dir() and d.name in _LAYER_NAMES
                ]
                if _layers:
                    _envs[_env_dir.name] = _layers
            if _envs:
                _tf["environments"] = _envs

            # Infer apply order from layer names (bootstrap first, app-infra last)
            _all_layers = {l for layers in _envs.values() for l in layers}
            _order = [l for l in ["bootstrap", "core-infra", "core", "app-infra", "app", "shared"]
                      if l in _all_layers]
            if _order:
                _tf["apply_order"] = " → ".join(_order)

        # State backend: search within the detected tf root first, then fall back to whole tree
        _btf_search_root = _tf_root if _tf_root else root
        _btf_candidates = list(_btf_search_root.rglob("backend.tf"))[:5]
        if not _btf_candidates:
            _btf_candidates = list(root.rglob("backend.tf"))[:5]
        for _btf in _btf_candidates:
            try:
                _btf_text = _btf.read_text(encoding="utf-8", errors="ignore")
                _bkt = _tf_re.search(r'bucket\s*=\s*"([^"]+)"', _btf_text)
                _reg = _tf_re.search(r'region\s*=\s*"([^"]+)"', _btf_text)
                _key = _tf_re.search(r'key\s*=\s*"([^"]+)"', _btf_text)
                _prof = _tf_re.search(r'profile\s*=\s*"([^"]+)"', _btf_text)
                if _bkt:
                    _tf["state_bucket"] = _bkt.group(1)
                if _reg:
                    _tf["state_region"] = _reg.group(1)
                if _key:
                    # Generalise the key pattern: replace the env/layer segments with {env}/{layer}
                    _key_val = _key.group(1)
                    _key_gen = _tf_re.sub(
                        r'/(dev|staging|prod|production|qa|uat)/',
                        "/{env}/", _key_val
                    )
                    _key_gen = _tf_re.sub(
                        r'/(bootstrap|core-infra|app-infra|core|app)/',
                        "/{layer}/", _key_gen
                    )
                    _tf["state_key_pattern"] = _key_gen
                if _prof:
                    _tf["aws_profile"] = _prof.group(1)
                if _bkt:
                    break
            except OSError:
                continue

        # Modules: find a modules/ directory containing subdirs each with *.tf files
        # No hardcoded path — works for ops/modules/, infra/modules/, terraform/modules/, etc.
        _SKIP_GENERAL = {".git", "vendor", "node_modules", "__pycache__", ".terraform",
                         ".idea", ".vscode", "dist", "build", "coverage", ".next"}
        _mod_dir: "Path | None" = None
        for _md in root.rglob("modules"):
            if not _md.is_dir():
                continue
            if any(part in _SKIP_GENERAL for part in _md.parts):
                continue
            # Must contain at least 2 subdirs that each have at least one .tf file
            _mod_subdirs = [
                d for d in _md.iterdir()
                if d.is_dir() and not d.name.startswith(".") and any(d.glob("*.tf"))
            ]
            if len(_mod_subdirs) >= 2:
                _mod_dir = _md
                break
        if _mod_dir is not None and _mod_dir.is_dir():
            _tf["modules_path"] = str(_mod_dir.relative_to(root))
            _tf["modules"] = sorted(d.name for d in _mod_dir.iterdir() if d.is_dir())

        if _tf:
            found["_terraform"] = _tf

    return found


# Backward-compat alias (callers inside /init still use _detect_project name)
_detect_project = _scan_project


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

    # .code-crew/config.yaml
    cfg_dir = root / ".code-crew"
    cfg_dir.mkdir(exist_ok=True)
    config_file = cfg_dir / "config.yaml"
    if not config_file.exists():
        name = _read_line(console, "Project name: ") or root.name
        tracker = _read_line(console, "Issue tracker [jira/linear/github]: ") or "jira"
        project_key = (_read_line(console, "Project key (e.g. PROJ): ") or "PROJ").upper()

        config_file.write_text(
            f"project: {name}\n"
            f"issue_tracker:\n"
            f"  type: {tracker}\n"
            f"  project_key: {project_key}\n",
            encoding="utf-8",
        )
        console.print("  [green]✓[/green] .code-crew/config.yaml written")
    else:
        console.print("  [dim].code-crew/config.yaml already exists[/dim]")

    # .gitignore
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("__pycache__/\n*.pyc\n.code-crew/structure.md\n", encoding="utf-8")
        console.print("  [green]✓[/green] .gitignore written")

    # --- auto-detect and append discovered config ---
    console.print("\n[bold]Scanning project…[/bold]")
    detected = {k: v for k, v in _scan_project(root).items() if not k.startswith("_")}

    if detected:
        # Group dotted keys into nested YAML sections
        sections: dict[str, dict] = {}
        for dotted, value in detected.items():
            section, _, key = dotted.partition(".")
            sections.setdefault(section, {})[key] = value

        block = "\n# Auto-detected by /init\n"
        for section, keys in sections.items():
            block += f"{section}:\n"
            for k, v in keys.items():
                block += f"  {k}: {v}\n"

        existing = config_file.read_text(encoding="utf-8")
        if "# Auto-detected" not in existing:
            config_file.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")

        _label = {
            "db.migration_tool": "Migration tool",
            "db.schema_path": "Schema path",
            "testing.framework": "Test framework",
            "testing.bdd": "BDD (.feature files)",
            "api.doc_standard": "API doc standard",
            "architecture.style": "Architecture",
        }
        for k, v in detected.items():
            console.print(f"  [green]✓[/green] {_label.get(k, k)}: [bold]{v}[/bold]")
    else:
        console.print("  [dim]No signals detected — edit .code-crew/config.yaml manually.[/dim]")

    # --- designs directory ---
    _init_designs_dir(root, console)

    console.print("\n[bold green]Done.[/bold green] Run [bold]/explore[/bold] then [bold]/design KEY[/bold] to start.")


def _init_designs_dir(root: Path, console: Console) -> None:
    """Prompt for and create a designs directory if one isn't already configured."""
    import yaml as _yaml

    # Already configured via env or exists at default location
    if os.environ.get("DESIGNS_PATH", "").strip():
        console.print(f"  [dim]designs directory: {os.environ['DESIGNS_PATH']}[/dim]")
        return
    if (root / "designs").exists():
        console.print(f"  [dim]designs directory: {root / 'designs'}[/dim]")
        return

    console.print(
        "\n[yellow]No designs directory found.[/yellow] "
        "This is where ADRs, ADDs, SOPs, and threat models live."
    )
    console.print("Designs directory path [designs/]: ", end="")
    try:
        answer = input().strip()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    designs_path = root / (answer or "designs")

    designs_path.mkdir(parents=True, exist_ok=True)
    for subdir in ("ADR", "ADD", "SOP", "TMD", "DMD"):
        (designs_path / subdir).mkdir(exist_ok=True)
    console.print(f"  [green]✓[/green] created {designs_path}")

    # Write to config if non-default path
    rel = str(designs_path.relative_to(root)) if designs_path.is_relative_to(root) else str(designs_path)
    if rel != "designs":
        cfg_file = root / ".code-crew" / "config.yaml"
        existing = _yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {} if cfg_file.exists() else {}
        existing.setdefault("designs", {})["path"] = rel
        cfg_file.write_text(_yaml.dump(existing, default_flow_style=False), encoding="utf-8")
        console.print(f"  [green]✓[/green] designs.path: {rel} written to config")

    os.environ["DESIGNS_PATH"] = str(designs_path)


# ---------------------------------------------------------------------------
# Chief Architect consultation UI
# ---------------------------------------------------------------------------

_shown_consultation: set[str] = set()


def _parse_consultation(output: str) -> dict | None:
    """Extract decision point and options from a CHIEF_ARCHITECT_CONSULTATION_REQUIRED block."""
    import re

    marker = "CHIEF_ARCHITECT_CONSULTATION_REQUIRED"
    idx = output.upper().find(marker)
    if idx == -1:
        return None
    block = output[idx + len(marker):]

    result: dict = {"decision": "", "options": [], "recommendation": ""}

    m = re.search(
        r"##\s*Decision(?:\s*Point)?\s*\n+(.*?)(?=\n##|\Z)",
        block, re.IGNORECASE | re.DOTALL,
    )
    if m:
        result["decision"] = m.group(1).strip()

    for _, name, body in re.findall(
        r"##\s*Option\s*\d+:\s*(.+?)\n(.*?)(?=\n##\s*Option|\n##\s*(?:Architect\s*)?Rec|\Z)",
        block, re.DOTALL | re.IGNORECASE,
    ):
        pros_m = re.search(r"\*\*Pros\*\*:?\s*(.+?)(?=\*\*Cons|\Z)", body, re.DOTALL)
        cons_m = re.search(r"\*\*Cons\*\*:?\s*(.+?)(?=\Z)", body, re.DOTALL)
        result["options"].append({
            "name": name.strip(),
            "pros": pros_m.group(1).strip() if pros_m else "",
            "cons": cons_m.group(1).strip() if cons_m else "",
        })

    rec_m = re.search(
        r"##\s*(?:Architect\s*)?Recommendation\s*\n+(.*?)(?=\Z)",
        block, re.DOTALL | re.IGNORECASE,
    )
    if rec_m:
        result["recommendation"] = rec_m.group(1).strip()

    return result if result["options"] else None


def _show_consultation_panel(key: str, flow, console) -> None:
    """Print the Chief Architect decision panel to the console."""
    arch_out = flow.state.task_outputs.get("architecture_review", "")
    parsed = _parse_consultation(arch_out)

    console.print()
    if not parsed:
        console.print(
            f"[yellow bold]⚡ {key} — Chief Architect input required[/yellow bold]\n"
            "[dim]Read the architecture_review output, then type your guidance "
            "or use /help <text>.[/dim]"
        )
        return

    console.print(f"[yellow bold]⚡ {key} — Chief Architect Input Required[/yellow bold]")
    if parsed["decision"]:
        console.print(f"\n[bold]Decision:[/bold] {parsed['decision']}\n")

    for i, opt in enumerate(parsed["options"], 1):
        console.print(f"  [bold cyan][{i}] {opt['name']}[/bold cyan]")
        if opt["pros"]:
            for line in opt["pros"].splitlines():
                l = line.strip(" -*")
                if l:
                    console.print(f"      [green]+[/green] {l}")
        if opt["cons"]:
            for line in opt["cons"].splitlines():
                l = line.strip(" -*")
                if l:
                    console.print(f"      [red]-[/red] {l}")
        console.print()

    if parsed["recommendation"]:
        rec = parsed["recommendation"].split("\n")[0].strip()
        console.print(f"[dim]Architect recommends: {rec}[/dim]\n")

    n = len(parsed["options"])
    choices = "/".join(str(i) for i in range(1, n + 1))
    console.print(
        f"[dim]Type [bold]{choices}[/bold] to select an option, "
        "or type guidance / questions directly.[/dim]"
    )


def _is_in_consultation(stuck: list[str], state: ReplState) -> bool:
    if not stuck:
        return False
    entry = state.active.get(stuck[0])
    if not entry:
        return False
    flow, _ = entry
    return flow.state.needs_help_gate == "chief_architect_consultation"


# ---------------------------------------------------------------------------
# Help injection
# ---------------------------------------------------------------------------

def _parse_finding_selection(answer: str, count: int) -> set[int] | None:
    """Parse a finding selection string into a set of 1-based indices.

    Returns None to signal cancellation (no action).
    Accepts: empty/'all' → all, 'none'/'n'/'no' → empty set, or comma-sep numbers/ranges.
    """
    import re as _re
    s = answer.strip().lower()
    if not s or s == "all":
        return set(range(1, count + 1))
    if s in ("none", "n", "no"):
        return set()
    selected: set[int] = set()
    for part in _re.split(r"[,\s]+", s):
        part = part.strip()
        if not part:
            continue
        m = _re.match(r"^(\d+)-(\d+)$", part)
        if m:
            selected.update(range(int(m.group(1)), int(m.group(2)) + 1))
        elif _re.match(r"^\d+$", part):
            selected.add(int(part))
    return selected & set(range(1, count + 1))


def _start_drift(console: Console) -> None:
    """Assess and resolve infrastructure drift: Terraform, CI/CD, monitoring, config."""
    from code_crew.flow import DriftFlow

    console.print("\n[bold]Starting infrastructure drift assessment…[/bold]")
    console.print("[dim]Categories: terraform · ci/cd · monitoring · config[/dim]\n")

    drift_input: dict = {
        "project_root": str(Path.cwd()),
        "environments": ["dev", "staging", "prod"],
        "categories": ["terraform", "cicd", "monitoring", "config"],
    }

    def on_task_complete(_key: str, task_name: str, summary: str) -> None:
        console.print(f"[dim]  ✓ {task_name}: {summary[:120]}[/dim]")

    flow = DriftFlow(drift_input, on_task_complete=on_task_complete)
    try:
        flow.run()
        assess_out = flow.task_outputs.get("drift_assess", "")
        if "NO DRIFT DETECTED" in assess_out.upper():
            console.print("\n[bold green]No infrastructure drift detected.[/bold green]")
        else:
            resolve_out = flow.task_outputs.get("drift_resolve", "")
            if "DRIFT RESOLVED" in resolve_out.upper():
                console.print("\n[bold green]Drift resolution complete.[/bold green]")
            else:
                console.print("\n[bold yellow]Drift partially resolved — review output for items requiring manual intervention.[/bold yellow]")
            console.print(resolve_out[:2000])
    except Exception as exc:
        console.print(f"\n[red]Drift flow error: {exc}[/red]")


def _start_verify(console: Console) -> None:
    """Run the full verification audit, show summary, gate on human approval, open issues."""
    import re
    import urllib.request
    import urllib.error
    import json as _json
    from datetime import date

    from code_crew.crew import build_verify_crew, _precheck_security, _precheck_architecture

    console.print("\n[bold]Starting verification audit…[/bold]")
    console.print("[dim]Scans: architecture · security · compliance · domain → chief review → report[/dim]\n")

    # Run Python pre-checks before the LLM crew — these are authoritative for objective facts
    _cwd = str(Path.cwd())
    _sec_facts  = _precheck_security(_cwd)
    _arch_facts = _precheck_architecture(_cwd)

    def _parse_precheck_into_lines(facts: str, tag: str) -> tuple[list[str], list[str], list[str]]:
        """Convert pre-check fact lines into FINDING/PASS/INFO lists."""
        findings: list[str] = []
        passes:   list[str] = []
        infos:    list[str] = []
        for line in facts.splitlines():
            stripped = line.strip()
            if not stripped.startswith("- "):
                continue
            entry = stripped[2:]
            entry_lower = entry.lower()
            if tag == "SEC":
                if "**invalid**" in entry_lower or "no tmd file found" in entry_lower:
                    name = entry.split(":")[0].strip()
                    reason = entry.split("—", 1)[1].strip() if "—" in entry else "invalid"
                    if "designs/TMD/" in entry:
                        findings.append(f"TMD file invalid — {entry.split(':')[0].strip()} [HIGH] ({reason})")
                    else:
                        findings.append(f"No threat model found for component — {name} [MEDIUM]")
                elif "tmd invalid" in entry_lower:
                    name = entry.split(":")[0].strip()
                    reason = entry.split("(", 1)[1].rstrip(")") if "(" in entry else "invalid"
                    findings.append(f"Threat model invalid for component — {name} [HIGH] ({reason})")
                elif ": valid" in entry_lower or "tmd valid" in entry_lower:
                    passes.append(entry.replace(": VALID", "").replace("TMD VALID — ", "TMD valid — "))
                elif "tmd valid" in entry_lower:
                    passes.append(f"TMD valid — {entry.split('TMD VALID')[0].strip()}")
                elif ": `" in entry and ("[high]" in entry_lower or "[low]" in entry_lower):
                    # Hardcoded secret line: "- path:line: `snippet` [HIGH]"
                    severity = "HIGH" if "[high]" in entry_lower else "LOW"
                    path_part = entry.split(":")[0].strip().lstrip("- ")
                    line_part = entry.split(":")[1].strip() if len(entry.split(":")) > 1 else "?"
                    findings.append(f"Hardcoded secret — {path_part}:{line_part} [{severity}]")
                elif "no hardcoded secrets found" in entry_lower:
                    passes.append("No hardcoded secrets found in scanned Go source files")
                else:
                    infos.append(entry)
            elif tag == "ARCH":
                if "exists in code and in sad" in entry_lower:
                    name_dir = entry.split("→")[0].strip() if "→" in entry else entry.split(":")[0].strip()
                    dir_part = entry.split("→")[1].split(":")[0].strip() if "→" in entry else ""
                    passes.append(f"SAD component {name_dir} present at {dir_part} — aligned with SAD")
                elif "exists in code but not in sad" in entry_lower:
                    name = entry.split("→")[0].strip() if "→" in entry else entry.split(":")[0].strip()
                    infos.append(f"Component not in SAD — {name} (newer than SAD)")
                elif "directory missing from code" in entry_lower:
                    name = entry.split("→")[0].strip() if "→" in entry else entry.split(":")[0].strip()
                    dir_part = entry.split("→")[1].split(":")[0].strip() if "→" in entry else ""
                    findings.append(f"Code directory missing — {name} ({dir_part} not found)")
                elif "not a deployable service" in entry_lower:
                    infos.append(f"Non-deployable entry — {entry.split(':')[0].strip()}")
                elif "referenced in sad but not in structure" in entry_lower:
                    keyword = entry.split("'")[1] if "'" in entry else "unknown"
                    findings.append(f"SAD references '{keyword}' not found in code")
                elif "sad drift check skipped" in entry_lower or "not found" in entry_lower:
                    infos.append(entry)
                elif "covered —" in entry_lower:
                    decision = entry.split(":")[0].strip()
                    detail = entry.split("COVERED —")[1].strip() if "COVERED —" in entry else ""
                    passes.append(f"ADR covers {decision} — {detail}")
                elif "not covered" in entry_lower:
                    decision = entry.split(":")[0].strip()
                    findings.append(f"No ADR for {decision}")
                elif "adr coverage check skipped" in entry_lower:
                    infos.append("No ADR directory found — ADR coverage check skipped")
                elif "total adr files" in entry_lower:
                    infos.append(entry)
                else:
                    infos.append(entry)
        return findings, passes, infos

    _sec_findings,  _sec_passes,  _sec_infos  = _parse_precheck_into_lines(_sec_facts,  "SEC")
    _arch_findings, _arch_passes, _arch_infos = _parse_precheck_into_lines(_arch_facts, "ARCH")

    def _kickoff_verify():
        crew = build_verify_crew(project_root=str(Path.cwd()))
        return crew.kickoff()  # returns CrewOutput

    def _is_tool_call_exc(exc) -> bool:
        s = str(exc)
        return (
            ("Input should be a valid string" in s and "ChatCompletion" in s)
            or "format_answer received a list" in s
            or "LLM hit max_iterations mid tool-call" in s
        )

    try:
        crew_output = _kickoff_verify()
    except Exception as exc:
        if _is_tool_call_exc(exc):
            console.print("[yellow]Model returned tool-call as final output — retrying…[/yellow]")
            try:
                crew_output = _kickoff_verify()
            except Exception as exc2:
                console.print(f"\n[bold red]Verify failed:[/bold red] {exc2}")
                return
        else:
            console.print(f"\n[bold red]Verify failed:[/bold red] {exc}")
            return

    # --- map task name → raw output ---
    task_map: dict[str, str] = {}
    for t in getattr(crew_output, "tasks_output", []) or []:
        if getattr(t, "name", None):
            task_map[t.name] = getattr(t, "raw", "") or ""

    chief_out = task_map.get("verify_chief_review", str(crew_output))
    report_out = task_map.get("verify_report", "")

    # --- parse findings from chief review ---
    # Must contain [TAG] to exclude the summary count lines (REQUIRED: N / EXEMPT: N / PASS: N)
    _tag = r"\[(?:ARCH|SEC|COMP|DOMAIN)\]"
    required = re.findall(rf"^REQUIRED:\s+({_tag}.+)$", chief_out, re.MULTILINE)
    exempt   = re.findall(rf"^EXEMPT:\s+({_tag}.+)$",   chief_out, re.MULTILINE)
    passed   = re.findall(rf"^PASS:\s+({_tag}.+)$",     chief_out, re.MULTILINE)

    # --- per-scan finding and pass counts ---
    scan_defs = [
        ("verify_arch_scan",        "Architecture", "ARCH"),
        ("verify_security_scan",    "Security",     "SEC"),
        ("verify_compliance_scan",  "Compliance",   "COMP"),
        ("verify_domain_scan",      "Domain",       "DOMAIN"),
    ]
    scan_counts: dict[str, int] = {}
    scan_passes: dict[str, list[str]] = {}
    scan_infos: dict[str, list[str]] = {}
    _scan_findings_merged: dict[str, list[str]] = {}
    for task_name, _, tag in scan_defs:
        raw = task_map.get(task_name, "")
        _all_findings = list(dict.fromkeys(re.findall(rf"^FINDING \[{tag}\]:?\s+(.+)$", raw, re.MULTILINE)))
        _all_passes   = list(dict.fromkeys(re.findall(rf"^PASS \[{tag}\]:?\s+(.+)$",    raw, re.MULTILINE)))
        _all_infos    = list(dict.fromkeys(re.findall(rf"^INFO \[{tag}\]:?\s+(.+)$",    raw, re.MULTILINE)))

        # Merge Python pre-check results (authoritative for objective checks)
        if tag == "SEC":
            for f in _sec_findings:
                if f not in _all_findings:
                    _all_findings.append(f)
            for p in _sec_passes:
                if p not in _all_passes:
                    _all_passes.append(p)
            for i in _sec_infos:
                if i not in _all_infos:
                    _all_infos.append(i)
        elif tag == "ARCH":
            for f in _arch_findings:
                if f not in _all_findings:
                    _all_findings.append(f)
            for p in _arch_passes:
                if p not in _all_passes:
                    _all_passes.append(p)
            for i in _arch_infos:
                if i not in _all_infos:
                    _all_infos.append(i)

        scan_counts[task_name]   = len(_all_findings)
        scan_passes[task_name]   = _all_passes
        scan_infos[task_name]    = _all_infos
        # Store merged findings list for the report section (not just the count)
        _scan_findings_merged[task_name] = _all_findings

    # --- write report file ---
    from datetime import datetime as _dt
    _now = _dt.now()
    ts = _now.strftime("%Y%m%d-%H%M%S")
    report_path = Path(".code-crew") / f"audit-{ts}.md"
    report_path.parent.mkdir(exist_ok=True)

    today_fmt = _now.strftime("%Y-%m-%d")
    proj = Path.cwd().name
    rows_required = "\n".join(f"- {r}" for r in required) or "_None_"
    rows_exempt   = "\n".join(f"- {e}" for e in exempt)   or "_None_"
    rows_triaged_pass = "\n".join(f"- {p}" for p in passed) or "_None_"

    # Build per-scan detail sections (findings + passes + infos) — deduplicate each list
    def _dedup(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            key = item.strip()
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    _scan_detail_sections = ""
    for task_name, label, tag in scan_defs:
        _findings = _dedup(_scan_findings_merged.get(task_name, []))
        _passes   = _dedup(scan_passes.get(task_name, []))
        _infos    = _dedup(scan_infos.get(task_name, []))
        _scan_detail_sections += f"\n### {label}\n\n"
        if _findings:
            _scan_detail_sections += "**Findings:**\n" + "\n".join(f"- {f}" for f in _findings) + "\n\n"
        else:
            _scan_detail_sections += "**Findings:** _None_\n\n"
        if _passes:
            _scan_detail_sections += "**Passed:**\n" + "\n".join(f"- {p}" for p in _passes) + "\n\n"
        if _infos:
            _scan_detail_sections += "**Info:**\n" + "\n".join(f"- {i}" for i in _infos) + "\n\n"

    # Total pass count = per-scan PASS lines + chief-review PASS (false positive) lines
    total_clean = sum(len(v) for v in scan_passes.values())
    content = (
        f"# Audit Report\n\n"
        f"**Date:** {today_fmt}  \n**Project:** {proj}  \n"
        f"**Scans run:** Architecture · Security · Compliance · Domain\n\n---\n\n"
        f"## Summary\n\n"
        f"| Status | Count |\n|--------|-------|\n"
        f"| REQUIRED (must fix) | {len(required)} |\n"
        f"| EXEMPT (accepted risk) | {len(exempt)} |\n"
        f"| PASS (false positive triaged by architect) | {len(passed)} |\n"
        f"| Clean checks (passed per scan) | {total_clean} |\n\n---\n\n"
        f"## Required Fixes\n\n{rows_required}\n\n---\n\n"
        f"## Exemptions\n\n{rows_exempt}\n\n---\n\n"
        f"## Scan Details\n{_scan_detail_sections}\n---\n\n"
        f"## Appendix — False Positives (Chief Review PASS)\n\n{rows_triaged_pass}\n"
    )
    report_path.write_text(content + "\n", encoding="utf-8")

    # ── Summary display ──────────────────────────────────────────────────
    console.print(f"\n[bold]Verification Summary[/bold]  [dim]{report_path}[/dim]\n")

    for task_name, label, _ in scan_defs:
        n = scan_counts.get(task_name, 0)
        p = len(scan_passes.get(task_name, []))
        icon = "[green]✓[/green]" if n == 0 else "[red]✗[/red]"
        console.print(f"  {icon} {label:<18} {n} finding(s), {p} clean check(s)")

    console.print()
    console.print(f"  [red bold]REQUIRED:[/red bold]  {len(required)}")
    console.print(f"  [yellow]EXEMPT:[/yellow]    {len(exempt)}")
    console.print(f"  [green]PASS (false positive):[/green] {len(passed)}")
    console.print(f"  [green]CLEAN checks:[/green] {total_clean}")

    if required:
        console.print(f"\n[red bold]Required fixes — must resolve before next release:[/red bold]")
        for i, r in enumerate(required, 1):
            console.print(f"  [red]{i}.[/red] {r}")

    # ── Human gate ──────────────────────────────────────────────────────
    console.print()
    if not required:
        answer = _read_line(console, "[bold]Chief Architect: approve report?[/bold] [y/N] ").lower()
        if answer == "y":
            console.print(f"[green]✓ Report approved. {report_path}[/green]")
        else:
            console.print(f"[dim]Report saved to {report_path}. No action taken.[/dim]")
        return

    n = len(required)
    console.print(f"[bold]Chief Architect: which findings to open as issues?[/bold]")
    console.print(f"  [dim]Enter 'all' (default), 'none', or numbers — e.g. '3-17' or '1,3,5-10'[/dim]")
    console.print(f"  [dim]Findings not selected are noted in the report but no ticket is created.[/dim]")
    answer = _read_line(console, "  [bold]>[/bold] ")
    if answer == "":
        console.print(f"\n[dim]Cancelled. Report saved to {report_path}.[/dim]")
        return

    selected = _parse_finding_selection(answer, n)

    to_open_idx = sorted(selected) if selected else []
    to_skip_idx = [i for i in range(1, n + 1) if i not in selected]

    if to_skip_idx:
        console.print(f"\n[dim]Skipping {len(to_skip_idx)} finding(s) — no issues created for:[/dim]")
        for i in to_skip_idx:
            console.print(f"  [dim]{i}. {required[i - 1][:90]}[/dim]")

    if not to_open_idx:
        console.print(f"\n[dim]Report approved. No issues created. {report_path}[/dim]")
        return

    required_to_open = [required[i - 1] for i in to_open_idx]
    console.print(f"\n[green]Opening {len(required_to_open)} issue(s)…[/green]")
    required = required_to_open  # hand off to issue-creation block below

    # ── Create issue tickets ─────────────────────────────────────────────
    jira_url   = os.environ.get("JIRA_URL", "").rstrip("/")
    jira_user  = os.environ.get("JIRA_USER", "")
    jira_token = os.environ.get("JIRA_TOKEN", "")
    project_key = os.environ.get("PROJECT_KEY", "PROJ")

    if not all([jira_url, jira_user, jira_token]):
        console.print("[yellow]Jira not configured — issues to create:[/yellow]\n")
        for i, r in enumerate(required, 1):
            tag = re.match(r"\[(ARCH|SEC|COMP|DOMAIN)\]", r)
            label = tag.group(1).lower() if tag else "verify"
            console.print(f"  {i}. [bold][verify] {r[:100]}[/bold]")
            console.print(f"     Labels: verify, {label}-audit\n")
        return

    import base64
    creds = base64.b64encode(f"{jira_user}:{jira_token}".encode()).decode()
    created: list[str] = []

    for finding in required:
        summary = re.sub(r"^\[(ARCH|SEC|COMP|DOMAIN)\]\s*", "", finding)[:200]
        tag_match = re.match(r"\[(\w+)\]", finding)
        label = tag_match.group(1).lower() + "-audit" if tag_match else "verify"
        payload = _json.dumps({
            "fields": {
                "project": {"key": project_key},
                "summary": f"[verify] {summary}",
                "description": {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph", "content": [
                        {"type": "text", "text": finding}
                    ]}]
                },
                "issuetype": {"name": "Bug"},
                "labels": ["verify", label],
            }
        }).encode()
        req = urllib.request.Request(
            f"{jira_url}/rest/api/3/issue",
            data=payload,
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                data = _json.loads(resp.read())
                key = data.get("key", "?")
                created.append(key)
                console.print(f"  [green]✓[/green] Created [bold]{key}[/bold]: {summary[:60]}")
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")[:200]
            console.print(f"  [red]✗[/red] Failed to create issue: {e.code} {body}")

    if created:
        console.print(f"\n[green]{len(created)} issue(s) created:[/green] {', '.join(created)}")


def _handle_domain(args: list[str], console: Console) -> None:
    """Handle /domain subcommands: design <KEY>, extract [path], (no args → status)."""
    if not args:
        console.print(
            "[bold]Domain modeling commands:[/bold]\n"
            "  /domain design <KEY>     — run event storming for a Jira issue\n"
            "  /domain extract [path]   — reverse-engineer domain model from code\n"
        )
        return

    sub = args[0].lower()
    if sub == "design":
        if len(args) < 2:
            console.print("[red]Usage: /domain design <KEY>[/red]")
            return
        _start_domain_design(args[1].upper(), console)
    elif sub == "extract":
        path = args[1] if len(args) > 1 else ""
        _start_domain_extract(path, console)
    else:
        console.print(f"[red]Unknown /domain subcommand: {sub}[/red]")


def _start_domain_design(issue_key: str, console: Console) -> None:
    """Run a full domain modeling session (all 3 phases) for a Jira issue."""
    from code_crew.flow import DomainFlow
    from shared.jira_client import get_issue

    console.print(f"\n[bold]Domain modeling session — {issue_key}[/bold]")
    console.print("[dim]Phase 1: flow discovery · Phase 2: per-flow event storming · Phase 3: synthesis[/dim]\n")

    try:
        issue = get_issue(issue_key)
    except Exception as exc:
        console.print(f"[yellow]Could not fetch {issue_key}: {exc}. Proceeding with key only.[/yellow]")
        issue = {"key": issue_key, "summary": "", "description": ""}

    domain_input = {
        "issue_key": issue_key,
        "system_name": issue.get("summary", issue_key),
        "requirement": issue.get("description", ""),
    }

    def _on_task(key: str, task: str, summary: str) -> None:
        console.print(f"  [green]✓[/green] [bold]{task}[/bold]: {summary[:100]}")

    flow = DomainFlow(domain_input, on_task_complete=_on_task)
    try:
        flow.run()
        console.print("\n[green bold]Domain modeling complete.[/green bold]")
        console.print("[dim]Outputs saved to designs/DMD/[/dim]")
    except Exception as exc:
        console.print(f"\n[red]Domain flow failed: {exc}[/red]")


def _start_domain_extract(path: str, console: Console) -> None:
    """Extract a domain model from existing code."""
    from code_crew.crew import build_domain_extract_crew

    target = str(Path(path).expanduser()) if path else str(Path.cwd())
    console.print(f"\n[bold]Domain extract — {target}[/bold]")
    console.print("[dim]Scanning code for aggregates, events, value objects…[/dim]\n")

    def _kickoff() -> str:
        return str(build_domain_extract_crew(target_path=target).kickoff())

    def _is_tool_call_exc(exc) -> bool:
        s = str(exc)
        return (
            ("Input should be a valid string" in s and "ChatCompletion" in s)
            or "format_answer received a list" in s
            or "LLM hit max_iterations mid tool-call" in s
        )

    try:
        output = _kickoff()
    except Exception as exc:
        if _is_tool_call_exc(exc):
            console.print("[yellow]Model returned tool-call as final output — retrying…[/yellow]")
            try:
                output = _kickoff()
            except Exception as exc2:
                console.print(f"\n[bold red]Domain extract failed:[/bold red] {exc2}")
                return
        else:
            console.print(f"\n[bold red]Domain extract failed:[/bold red] {exc}")
            return

    import re
    match = re.search(r"DOMAIN EXTRACT COMPLETE", output, re.IGNORECASE)
    if match:
        console.print("\n[green bold]Domain extract complete.[/green bold]")
        console.print("[dim]Outputs saved to designs/DMD/[/dim]")
    else:
        console.print("\n[yellow]Extract may be incomplete — check agent output above.[/yellow]")


def _run_index(target: str, console: Console) -> None:
    """Build or rebuild the semantic code search index for a project directory."""
    from pathlib import Path as _Path
    from shared.tools.code_index import build_index

    root = _Path(target).resolve() if target else _Path.cwd()
    if not root.exists():
        console.print(f"[red]Path not found: {target}[/red]")
        return

    model = os.environ.get("CODE_INDEX_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    console.print(f"\n[dim]Building code index for [bold]{root.name}[/bold] (model: {model})…[/dim]")
    console.print("[dim]First run downloads the embedding model (~45MB). Subsequent runs are fast.[/dim]")

    try:
        result = build_index(root)
        console.print(f"[green]✓[/green] {result}")
    except Exception as exc:
        console.print(f"[yellow]Code index failed: {exc}[/yellow]")
        console.print("[dim]Agents can still use workspace_reader search. "
                      "Install sentence-transformers for non-default models.[/dim]")


def _run_explore(target: str, console: Console) -> None:
    """
    Scan the project directory, detect tech stacks, optionally generate a
    starter OTM threat model, and save context files so agents share the same
    picture of the project structure.
    """
    import datetime
    import json as _json

    root = (Path(target).expanduser() if target else Path.cwd()).resolve()
    if not root.exists():
        console.print(f"[red]Directory not found: {root}[/red]")
        return

    _SKIP = {".git", "vendor", "node_modules", "__pycache__", ".terraform",
              ".idea", ".vscode", "dist", "build", "coverage", ".next"}

    def _tree(path: Path, prefix: str = "", depth: int = 0, max_depth: int = 4) -> list[str]:
        if depth > max_depth:
            return [f"{prefix}…"]
        try:
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return []
        lines = []
        entries = [e for e in entries if e.name not in _SKIP and not e.name.startswith(".")]
        for i, entry in enumerate(entries):
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                ext = "    " if i == len(entries) - 1 else "│   "
                lines.extend(_tree(entry, prefix + ext, depth + 1, max_depth))
        return lines

    # Full tree for architect context only — never printed or written to structure.md
    tree_lines = _tree(root, max_depth=4)
    tree_text = "\n".join(tree_lines)

    console.print(f"\n[bold]Scanning {root}[/bold]")

    # --- Phase 1: pure-Python signal scan ---
    scan = _scan_project(root)
    stacks: list[str] = scan.pop("_stacks", [])
    svc_dirs_scan: list[str] = scan.pop("_svc_dirs", [])
    feature_dirs_scan: list[str] = scan.pop("_feature_dirs", [])
    test_dirs_scan: list[str] = scan.pop("_test_dirs", [])
    arch_style: str = scan.get("architecture.style", "")
    migration_tool: str = scan.get("db.migration_tool", "")
    migration_path: str = scan.get("db.schema_path", "")
    test_framework: str = scan.get("testing.framework", "")
    api_doc: str = scan.get("api.doc_standard", "")
    api_doc_path: str = scan.get("api.doc_path", "")
    ci_methods: list[str] = scan.get("ci.deployment_methods", [])
    compliance_standards: list[str] = scan.pop("_compliance_standards", [])
    detected_commands: dict[str, str] = scan.pop("_commands", {})
    terraform_info: dict = scan.pop("_terraform", {})

    if stacks:
        console.print(f"\n[bold]Detected stacks:[/bold] {', '.join(stacks)}")
    else:
        console.print("\n[dim]No stacks detected — set stacks: in .code-crew/config.yaml if needed.[/dim]")

    if arch_style:
        console.print(f"[bold]Detected architecture:[/bold] {arch_style}")
        os.environ["ARCHITECTURE_STYLE"] = arch_style
    else:
        console.print("[dim]Architecture pattern not detected — LLM phase will assess.[/dim]")

    if migration_tool:
        console.print(f"[bold]Detected migration tool:[/bold] {migration_tool}")
        os.environ["DB_MIGRATION_TOOL"] = migration_tool
    else:
        console.print("[dim]Migration tool not detected — set db.migration_tool in config if needed.[/dim]")

    if ci_methods:
        console.print(f"[bold]Detected CI/CD tooling:[/bold] {', '.join(ci_methods)}")
        os.environ["CI_DEPLOYMENT_METHODS"] = ",".join(ci_methods)
    else:
        console.print("[dim]CI/CD tooling not detected — set ci.deployment_methods in config if needed.[/dim]")

    # --- save structure.md ---
    out_dir = root / ".code-crew"
    out_dir.mkdir(exist_ok=True)
    stacks_yaml = "\n".join(f"  - {s}" for s in stacks) if stacks else "  # none detected"
    arch_line = f"\n## Detected architecture\n\n```yaml\narchitecture:\n  style: {arch_style}\n```\n" if arch_style else ""
    db_line = f"\n## Detected migration tool\n\n```yaml\ndb:\n  migration_tool: {migration_tool}\n```\n" if migration_tool else ""

    if ci_methods:
        # List workflow filenames for github-actions so agents know what to look at
        _ci_detail_lines = []
        for _cm in ci_methods:
            if _cm == "github-actions":
                _wf_dir = root / ".github" / "workflows"
                _wf_files = sorted(f.name for f in _wf_dir.glob("*.yml")) if _wf_dir.is_dir() else []
                _wf_files += sorted(f.name for f in _wf_dir.glob("*.yaml")) if _wf_dir.is_dir() else []
                if _wf_files:
                    _ci_detail_lines.append(f"- **github-actions**: {', '.join(_wf_files[:12])}")
                else:
                    _ci_detail_lines.append(f"- **github-actions**")
            else:
                _ci_detail_lines.append(f"- **{_cm}**")
        ci_line = "\n## CI/CD tooling\n\n" + "\n".join(_ci_detail_lines) + "\n"
    else:
        ci_line = ""

    # Merge detected commands with any already persisted in config.yaml
    import yaml as _yaml_cmd
    _cfg_path = out_dir / "config.yaml"
    _cfg_cmds: dict[str, str] = {}
    if _cfg_path.exists():
        try:
            _cfg_data = _yaml_cmd.safe_load(_cfg_path.read_text(encoding="utf-8")) or {}
            _cfg_cmds = _cfg_data.get("commands", {})
        except Exception:
            pass
    # Detected commands take precedence for new keys; config.yaml wins for existing keys
    all_commands = {**detected_commands, **_cfg_cmds}

    if all_commands:
        # Group: backend (Go/Python) vs frontend (TypeScript) vs infra
        _backend_keys = ("test", "build", "lint", "audit")
        _frontend_keys = ("test_frontend", "build_frontend", "typecheck", "lint_frontend")
        _infra_keys = ("db_migrate", "api_spec")

        def _cmd_rows(keys):
            return "\n".join(
                f"| {k:<20} | `{all_commands[k]}` |" for k in keys if k in all_commands
            )

        _sections = []
        _be_rows = _cmd_rows(_backend_keys)
        _fe_rows = _cmd_rows(_frontend_keys)
        _infra_rows = _cmd_rows(_infra_keys)
        _other_rows = "\n".join(
            f"| {k:<20} | `{v}` |"
            for k, v in all_commands.items()
            if k not in _backend_keys + _frontend_keys + _infra_keys
        )

        _hdr = "| Purpose              | Command |\n|----------------------|---------|"
        if _be_rows:
            _sections.append(f"### Backend\n\n{_hdr}\n{_be_rows}")
        if _fe_rows:
            _sections.append(f"### Frontend (TypeScript/React)\n\n{_hdr}\n{_fe_rows}")
        if _infra_rows:
            _sections.append(f"### Infrastructure\n\n{_hdr}\n{_infra_rows}")
        if _other_rows:
            _sections.append(f"### Other\n\n{_hdr}\n{_other_rows}")

        cmd_line = (
            f"\n## Project commands\n\n"
            f"Auto-detected by /explore. Override in `.code-crew/config.yaml` under `commands:`.\n\n"
            + "\n\n".join(_sections) + "\n"
        )
    else:
        cmd_line = ""
    # --- build Terraform section ---
    tf_line = ""
    if terraform_info:
        _tf_parts: list[str] = ["\n## Terraform infrastructure\n"]

        _tf_root_path = terraform_info.get("root", "")
        if _tf_root_path:
            _tf_parts.append(f"Root: `{_tf_root_path}`\n")

        _envs = terraform_info.get("environments", {})
        if _envs:
            _apply_order = terraform_info.get("apply_order", "")
            _env_rows = "\n".join(
                f"| **{env}** | `{_tf_root_path}/{env}` | {', '.join(layers)} |"
                for env, layers in sorted(_envs.items())
            )
            _tf_parts.append(
                "### Environments\n\n"
                "| Environment | Path | Layers |\n"
                "|-------------|------|--------|\n"
                + _env_rows
            )
            if _apply_order:
                _tf_parts.append(f"\nApply order: **{_apply_order}**")

        _state_bucket = terraform_info.get("state_bucket", "")
        _state_region = terraform_info.get("state_region", "")
        _state_key    = terraform_info.get("state_key_pattern", "")
        _aws_profile  = terraform_info.get("aws_profile", "")
        if _state_bucket:
            _tf_parts.append(
                "\n### State backend (S3)\n\n"
                f"| Key | Value |\n"
                f"|-----|-------|\n"
                + (f"| bucket | `{_state_bucket}` |\n" if _state_bucket else "")
                + (f"| region | `{_state_region}` |\n" if _state_region else "")
                + (f"| key pattern | `{_state_key}` |\n" if _state_key else "")
                + (f"| AWS profile | `{_aws_profile}` |\n" if _aws_profile else "")
            )

        _mods = terraform_info.get("modules", [])
        _mods_path = terraform_info.get("modules_path", "")
        if _mods:
            _mods_label = f"`{_mods_path}/`" if _mods_path else "infrastructure modules directory"
            _tf_parts.append(
                f"\n### Modules ({_mods_label})\n\n"
                + ", ".join(f"`{m}`" for m in _mods)
            )

        tf_line = "\n".join(_tf_parts) + "\n"

    (out_dir / "structure.md").write_text(
        f"# Project: `{root.name}` (auto-generated by /explore)\n\n"
        f"## Detected stacks\n\n"
        f"```yaml\nstacks:\n{stacks_yaml}\n```\n"
        + arch_line
        + db_line
        + ci_line
        + tf_line
        + cmd_line,
        encoding="utf-8",
    )
    console.print(f"\n[green]✓[/green] Saved to [dim]{out_dir / 'structure.md'}[/dim]")

    # --- Phase 2: LLM verification + architecture assessment ---
    component_descriptions: dict[str, str] = {}
    project_summary: str = ""
    # Collect CI workflow filenames to pass to architect
    _ci_workflows_for_llm: dict[str, str] = {}
    if "github-actions" in ci_methods:
        _wf_dir = root / ".github" / "workflows"
        if _wf_dir.is_dir():
            _wf_files = sorted(f.name for f in _wf_dir.glob("*.yml")) + \
                        sorted(f.name for f in _wf_dir.glob("*.yaml"))
            _ci_workflows_for_llm["github-actions"] = ", ".join(_wf_files[:20])
    try:
        from code_crew.crew import build_explore_single_task
        console.print("\n[dim]Running LLM phase (Architect — verifying detections + assessing architecture)…[/dim]")
        llm_result = build_explore_single_task(
            {
                "root_name": root.name,
                "stacks": stacks,
                "arch_style": arch_style,
                "migration_tool": migration_tool,
                "migration_path": migration_path,
                "test_framework": test_framework,
                "api_doc": api_doc,
                "api_doc_path": api_doc_path,
                "svc_dirs": svc_dirs_scan,
                "feature_dirs": feature_dirs_scan,
                "test_dirs": test_dirs_scan,
                "commands": all_commands,
                "ci_methods": ci_methods,
                "ci_workflows": _ci_workflows_for_llm,
                "terraform": terraform_info,
                "compliance_standards": compliance_standards,
            },
            extra_context=f"\n## Directory tree\n\n```\n{root.name}/\n{tree_text}\n```\n",
        )

        # Parse verification output — architect may correct any Phase 1 detection
        # Also collect DISCOVERY_BEGIN/END blocks for rich markdown sections
        verified_stacks: list[str] = []
        corrected_commands: dict[str, str] = {}
        verification_notes: list[str] = []
        discoveries: dict[str, str] = {}  # section_name → markdown content
        _in_discovery: str | None = None
        _discovery_lines: list[str] = []

        for raw_line in llm_result.splitlines():
            # Handle DISCOVERY_BEGIN/END before stripping (preserve indentation inside blocks)
            stripped = raw_line.strip()
            if stripped.startswith("DISCOVERY_BEGIN:"):
                _in_discovery = stripped.split(":", 1)[1].strip()
                _discovery_lines = []
                continue
            if stripped.startswith("DISCOVERY_END:"):
                if _in_discovery:
                    discoveries[_in_discovery] = "\n".join(_discovery_lines).strip()
                    console.print(f"  [green]✓[/green] Discovered: [bold]{_in_discovery}[/bold]")
                _in_discovery = None
                _discovery_lines = []
                continue
            if _in_discovery is not None:
                _discovery_lines.append(raw_line)
                continue

            line = stripped
            if line.startswith("ARCHITECTURE_STYLE:"):
                _arch = line.split(":", 1)[1].strip()
                if _arch and (not arch_style or _arch != "undetected"):
                    arch_style = _arch
                    os.environ["ARCHITECTURE_STYLE"] = arch_style
                    console.print(f"[bold]LLM architecture assessment:[/bold] {arch_style}")
            elif line.startswith("PROJECT_SUMMARY:"):
                project_summary = line.split(":", 1)[1].strip()
            elif line.startswith("COMPONENT:"):
                rest = line.split(":", 1)[1].strip()
                if ": " in rest:
                    cdir, desc = rest.split(": ", 1)
                    component_descriptions[cdir.strip()] = desc.strip()
            elif line.startswith("STACK_VERIFIED:"):
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    verified_stacks.append(parts[1].strip())
            elif line.startswith("STACK_ADDED:"):
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    s = parts[1].strip()
                    if s and s not in stacks:
                        stacks.append(s)
                        verified_stacks.append(s)
                        console.print(f"  [green]+[/green] Architect added stack: [bold]{s}[/bold]")
            elif line.startswith("STACK_NOT_FOUND:"):
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    s = parts[1].strip()
                    reason = parts[2].strip() if len(parts) > 2 else ""
                    if s in stacks:
                        stacks.remove(s)
                    console.print(f"  [yellow]~[/yellow] Architect removed stack [bold]{s}[/bold]: {reason}")
                    verification_notes.append(f"Stack {s} not confirmed: {reason}")
            elif line.startswith("COMMAND_CORRECTED:"):
                parts = line.split(":", 3)
                if len(parts) >= 3:
                    key = parts[1].strip()
                    cmd = parts[2].strip()
                    corrected_commands[key] = cmd
                    console.print(f"  [yellow]~[/yellow] Command corrected: [bold]{key}[/bold] → `{cmd}`")
            elif line.startswith("COMMAND_ADDED:"):
                parts = line.split(":", 3)
                if len(parts) >= 3:
                    key = parts[1].strip()
                    cmd = parts[2].strip()
                    corrected_commands[key] = cmd
                    console.print(f"  [green]+[/green] Command added: [bold]{key}[/bold] → `{cmd}`")
            elif line.startswith("COMMAND_NOT_FOUND:"):
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    key = parts[1].strip()
                    reason = parts[2].strip() if len(parts) > 2 else ""
                    if key in all_commands:
                        del all_commands[key]
                    verification_notes.append(f"Command {key} not confirmed: {reason}")
            elif line.startswith(("TF_ROOT_VERIFIED:", "TF_ENV_VERIFIED:", "TF_STATE_VERIFIED:",
                                   "TF_MODULES_VERIFIED:", "TF_CORRECTED:", "TF_DISCOVERED:")):
                tag = line.split(":", 1)[0]
                detail = line.split(":", 1)[1].strip() if ":" in line else ""
                console.print(f"  [dim]TF {tag.replace('TF_', '').lower()}: {detail[:80]}[/dim]")
                if line.startswith("TF_CORRECTED:"):
                    verification_notes.append(f"TF correction: {detail}")
            elif line.startswith(("CICD_VERIFIED:", "CICD_ADDED:", "CICD_NOT_FOUND:")):
                pass  # informational, no override needed

        # Apply corrections to all_commands
        for k, v in corrected_commands.items():
            all_commands[k] = v

        # Augment structure.md with LLM findings
        additions = ""
        if verification_notes:
            additions += "\n## Architect verification notes\n\n"
            additions += "\n".join(f"- {n}" for n in verification_notes) + "\n"
        if project_summary:
            additions += f"\n## Project summary\n\n{project_summary}\n"
        if arch_style:
            additions += f"\n## Architecture\n\n```yaml\narchitecture:\n  style: {arch_style}\n```\n"
        # Append discovery sections in a defined order
        _discovery_order = ["code_structure", "test_structure", "cicd_workflows", "entry_points", "architectural_components", "compliance_standards"]
        for _disc_key in _discovery_order:
            if _disc_key in discoveries:
                additions += "\n" + discoveries[_disc_key] + "\n"
        # Any extra discovery sections the architect added
        for _disc_key, _disc_content in discoveries.items():
            if _disc_key not in _discovery_order:
                additions += "\n" + _disc_content + "\n"
        if component_descriptions:
            additions += "\n## Components\n\n"
            additions += "\n".join(
                f"- **{k}**: {v}" for k, v in sorted(component_descriptions.items())
            ) + "\n"
        if additions:
            existing = (out_dir / "structure.md").read_text(encoding="utf-8")
            (out_dir / "structure.md").write_text(existing.rstrip() + "\n" + additions, encoding="utf-8")
    except Exception as exc:
        console.print(f"[dim]LLM phase skipped: {exc}[/dim]")

    # --- persist detected stacks + arch + CI + commands + compliance to .code-crew/config.yaml ---
    # Merge compliance standards from LLM discovery (architect may have found more than Python scan)
    _llm_compliance: list[str] = []
    if "compliance_standards" in discoveries:
        import re as _re
        for _line in discoveries["compliance_standards"].splitlines():
            _m = _re.match(r"-\s+(\w[\w\s-]+?)\s+[—–-]", _line.strip())
            if _m:
                _std = _m.group(1).strip().lower().replace(" ", "-")
                if _std not in _llm_compliance:
                    _llm_compliance.append(_std)
    # Merge: prefer LLM-confirmed list; fallback to Python-detected
    final_compliance = _llm_compliance or compliance_standards

    if stacks or arch_style or ci_methods or detected_commands or final_compliance:
        import yaml as _yaml
        cfg_path = out_dir / "config.yaml"
        cfg_data: dict = {}
        if cfg_path.exists():
            try:
                cfg_data = _yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            except Exception:
                cfg_data = {}
        if stacks:
            cfg_data["stacks"] = stacks
        if arch_style:
            cfg_data.setdefault("architecture", {})["style"] = arch_style
        if ci_methods:
            cfg_data.setdefault("ci", {})["deployment_methods"] = ci_methods
        if final_compliance:
            cfg_data["compliance_standards"] = final_compliance
            os.environ["CODE_CREW_COMPLIANCE"] = ",".join(final_compliance)
        if detected_commands:
            existing_cmds = cfg_data.get("commands", {})
            # Only write keys not already overridden by the user
            for k, v in detected_commands.items():
                existing_cmds.setdefault(k, v)
            cfg_data["commands"] = existing_cmds
            # Apply to env so this session sees them immediately
            from shared.config import _ENV_MAP, _apply_section
            _apply_section(existing_cmds, _ENV_MAP.get("commands", {}), override=False)
        cfg_path.write_text(_yaml.safe_dump(cfg_data, default_flow_style=False, sort_keys=False), encoding="utf-8")
        if stacks:
            os.environ["_CODE_CREW_STACKS_PROFILE"] = ",".join(stacks)
        _cfg_parts = ["stacks", "architecture", "CI/CD", "commands"]
        if final_compliance:
            _cfg_parts.append(f"compliance ({', '.join(final_compliance)})")
        console.print(f"[green]✓[/green] Updated [dim]{cfg_path}[/dim] with {', '.join(_cfg_parts)}")

    svc_dirs = svc_dirs_scan

    # --- Component inventory + OTM scope ---
    designs_dir = root / "designs"
    tmd_dir = (designs_dir / "TMD") if designs_dir.exists() else None
    if tmd_dir:
        tmd_dir.mkdir(exist_ok=True)

    console.print("\n[dim]Building component inventory…[/dim]")

    # Sub-executables: cmd/ sub-dirs within each svc_dir
    cmd_entries: list[str] = []
    for svc in svc_dirs:
        cmd_dir = root / svc / "cmd"
        if cmd_dir.is_dir():
            for sub in sorted(cmd_dir.iterdir()):
                if sub.is_dir():
                    cmd_entries.append(f"{svc}/cmd/{sub.name}")

    # Infrastructure modules — use detected path from terraform_info
    infra_modules: list[str] = []
    _modules_path = terraform_info.get("modules_path", "") if terraform_info else ""
    if _modules_path:
        _modules_dir = root / _modules_path
        if _modules_dir.is_dir():
            for mod in sorted(_modules_dir.iterdir()):
                if mod.is_dir():
                    infra_modules.append(mod.name)

    # Key files: build a reading list for the manager to direct the agent
    # (dependency manifests, entry points, Terraform module roots)
    # The agent reads these via workspace_reader to discover external services,
    # data flows, and infrastructure — no grepping needed.
    key_files: list[dict] = []
    _SKIP_DIRS = {".git", "vendor", "node_modules", "__pycache__", ".terraform"}

    for svc in svc_dirs:
        svc_path = root / svc
        # Dependency manifests
        for manifest in ("go.mod", "package.json", "requirements.txt", "pyproject.toml", "Cargo.toml"):
            p = svc_path / manifest
            if p.exists():
                key_files.append({"type": "dependency-manifest", "path": str(p.relative_to(root))})
        # cmd/ entry points (main.go or equivalent)
        cmd_path = svc_path / "cmd"
        if cmd_path.is_dir():
            for sub in sorted(cmd_path.iterdir()):
                if sub.is_dir() and sub.name not in _SKIP_DIRS:
                    for ep in ("main.go", "main.py", "index.ts", "server.go"):
                        p = sub / ep
                        if p.exists():
                            key_files.append({"type": "entry-point", "path": str(p.relative_to(root))})
                            break
        # Top-level entry point if no cmd/
        else:
            for ep in ("main.go", "main.py", "cmd/main.go"):
                p = svc_path / ep
                if p.exists():
                    key_files.append({"type": "entry-point", "path": str(p.relative_to(root))})
                    break

    # Terraform module roots (one variables.tf or main.tf per module)
    if _modules_path:
        for mod_name in infra_modules:
            mod_path = root / _modules_path / mod_name
            for tf_file in ("main.tf", "variables.tf"):
                p = mod_path / tf_file
                if p.exists():
                    key_files.append({"type": "terraform-module", "path": str(p.relative_to(root))})
                    break

    inventory = {
        "svc_dirs": svc_dirs,
        "cmd_entries": cmd_entries,
        "infra_modules": infra_modules,
        "key_files": key_files,
        "stacks": stacks,
        "terraform": terraform_info,
    }

    console.print(f"  Services: {', '.join(svc_dirs) or 'none'}")
    if cmd_entries:
        console.print(f"  Sub-executables: {', '.join(cmd_entries)}")
    if infra_modules:
        console.print(f"  Infra modules: {', '.join(infra_modules)}")
    if key_files:
        console.print(f"  Key files catalogued: {len(key_files)}")

    # --- Phase 3a: OTM scope decision ---
    console.print("\n[dim]Phase 3a — OTM scope decision (Architect)…[/dim]")
    svc_id_fallback = root.name.lower().replace(" ", "-")
    scope_output = ""
    try:
        from code_crew.crew import build_otm_scope_task
        scope_crew = build_otm_scope_task(inventory)
        scope_output = scope_crew.kickoff().raw
    except Exception as exc:
        console.print(f"[yellow]OTM scope phase failed: {exc}[/yellow]")
        console.print("[dim]Falling back to single-project OTM.[/dim]")
        all_components = svc_dirs + cmd_entries
        scope_output = (
            f"PROJECT: {svc_id_fallback}\n"
            f"DESCRIPTION: {project_summary or root.name + ' platform'}\n"
            f"COMPONENTS: {', '.join(all_components)}\n"
            f"OTM SCOPE COMPLETE"
        )

    # Parse PROJECT blocks from scope output
    projects: list[dict] = []
    current_proj: dict = {}
    for line in scope_output.splitlines():
        line = line.strip()
        if line.startswith("PROJECT:"):
            if current_proj:
                projects.append(current_proj)
            # Normalise to lowercase kebab-case (model sometimes omits hyphens)
            import re as _re_scope
            raw_id = line.split(":", 1)[1].strip()
            proj_id = _re_scope.sub(r"[^a-z0-9]+", "-", raw_id.lower()).strip("-")
            current_proj = {
                "id": proj_id,
                "name": proj_id.replace("-", " ").title(),
                "description": "",
                "components": [],
            }
        elif line.startswith("DESCRIPTION:") and current_proj:
            current_proj["description"] = line.split(":", 1)[1].strip()
        elif line.startswith("COMPONENTS:") and current_proj:
            current_proj["components"] = [c.strip() for c in line.split(":", 1)[1].split(",") if c.strip()]
    if current_proj:
        projects.append(current_proj)

    # Deduplicate by id (model sometimes repeats PROJECT blocks in its output)
    seen_ids: set[str] = set()
    projects = [p for p in projects if p["id"] not in seen_ids and not seen_ids.add(p["id"])]  # type: ignore[func-returns-value]

    if not projects:
        console.print("[yellow]No project blocks parsed from scope output — skipping OTM generation.[/yellow]")
        return

    console.print(f"\n[bold]OTM projects identified:[/bold] {', '.join(p['id'] for p in projects)}")

    # --- Enrich projects with Terraform deployment facts ---
    # Run Python-side grep so /threat never needs to search the infrastructure directory.
    _enrich_project_terraform(projects, root, terraform_info)

    # --- Save inventory for /threat ---
    import json as _json
    out_dir = root / ".code-crew"
    out_dir.mkdir(exist_ok=True)
    inv_path = out_dir / "inventory.json"
    inv_path.write_text(
        _json.dumps({
            "generated_at": datetime.date.today().isoformat(),
            "root": str(root),
            "projects": projects,
            "inventory": inventory,
        }, indent=2),
        encoding="utf-8",
    )

    # --- Build semantic code index ---
    console.print("\n[dim]Building semantic code index…[/dim]")
    try:
        from shared.tools.code_index import build_index as _build_index
        _idx_result = _build_index(root)
        console.print(f"[green]✓[/green] Code index: {_idx_result}")
    except Exception as _idx_exc:
        console.print(f"[dim]Code index skipped: {_idx_exc}[/dim]")
        console.print("[dim]Run /index to build manually, or /fix to install missing deps.[/dim]")

    # --- OTM coverage report ---
    if tmd_dir:
        import yaml as _yaml
        console.print()
        for proj in projects:
            tmd_file = tmd_dir / f"{proj['id']}.yaml"
            td_file = tmd_dir / f"{proj['id']}.threat-dragon.json"
            if tmd_file.exists():
                try:
                    d = _yaml.safe_load(tmd_file.read_text(encoding="utf-8"))
                    n_threats = len(d.get("threats", []))
                    mtime = datetime.date.fromtimestamp(tmd_file.stat().st_mtime).isoformat()
                    td_status = "[green]✓[/green] threat-dragon" if td_file.exists() else "[yellow]no threat-dragon[/yellow]"
                    console.print(
                        f"  [green]✓[/green] [bold]{proj['id']}[/bold]"
                        f"  [dim]{mtime}, {n_threats} threats[/dim]  {td_status}"
                    )
                except Exception:
                    console.print(f"  [yellow]![/yellow] [bold]{proj['id']}[/bold]  [yellow]invalid YAML[/yellow]")
            else:
                console.print(f"  [dim]–[/dim] [bold]{proj['id']}[/bold]  [dim]not yet generated[/dim]")
        console.print()
    console.print("[dim]Run [bold]/threat[/bold] to generate or refresh threat models.[/dim]")


def _convert_tmd(tmd_file: Path, tmd_dir: Path, root: Path, console: Console) -> None:
    """Convert an OTM YAML to the tool format configured in THREAT_MODELING_TOOL."""
    import shutil as _shutil
    import subprocess as _sp

    tool = os.environ.get("THREAT_MODELING_TOOL", "").lower().strip()
    if not tool or tool == "otm":
        return

    out_dir_env = os.environ.get("THREAT_MODELING_OUTPUT_DIR", "").strip()
    out_dir = Path(out_dir_env) if out_dir_env else tmd_dir

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(root))
        except ValueError:
            return p.name

    if tool == "threat-dragon":
        out_file = out_dir / (tmd_file.stem + ".threat-dragon.json")
        try:
            from shared.threat_model_export import otm_to_threat_dragon
            otm_to_threat_dragon(tmd_file, out_file)
            console.print(f"[green]✓[/green] Threat Dragon [dim]{_rel(out_file)}[/dim]")
        except Exception as exc:
            console.print(f"[yellow]  Threat Dragon conversion failed: {exc}[/yellow]")

    elif tool == "irius-risk":
        if not _shutil.which("startleft"):
            console.print("[yellow]  irius-risk: startleft not found — run: pip install startleft[/yellow]")
            return
        out_file = out_dir / (tmd_file.stem + ".iriusrisk.xml")
        result = _sp.run(
            ["startleft", "parse", "--type", "OTM", "--output-type", "IRIUSRISK",
             "--output-file", str(out_file), str(tmd_file)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            console.print(f"[green]✓[/green] IriusRisk XML [dim]{_rel(out_file)}[/dim]")
        else:
            console.print(f"[yellow]  IriusRisk conversion failed: {result.stderr.strip()[:200]}[/yellow]")

    elif tool == "microsoft-tmmt":
        console.print("[dim]  microsoft-tmmt (.tm7) conversion not yet supported — OTM YAML only.[/dim]")

    else:
        console.print(f"[yellow]  Unknown threat_modeling.tool: {tool!r} — expected threat-dragon, irius-risk, or microsoft-tmmt[/yellow]")


def _enrich_project_terraform(
    projects: list[dict],
    root: "Path",
    terraform_info: "dict | None" = None,
) -> None:
    """Store raw Terraform grep output per project in inventory.

    Uses the infrastructure directory detected by /explore (from terraform_info).
    Falls back to scanning common directory names if terraform_info is absent.
    Stores the raw deduplicated grep output so /threat can inject it directly
    without running any searches at threat-model time.
    Runs silently — failure is non-fatal.
    """
    import subprocess, re as _re

    # Resolve infra directory from explore results
    infra_dir: "Path | None" = None
    if terraform_info:
        tf_root = terraform_info.get("root", "")
        if tf_root:
            candidate = root / tf_root
            if candidate.exists():
                infra_dir = candidate
    if infra_dir is None:
        for name in ("infra", "terraform", "infrastructure", "ops"):
            candidate = root / name
            if candidate.exists() and any(candidate.rglob("*.tf")):
                infra_dir = candidate
                break
    if infra_dir is None:
        return

    root_str = str(root) + "/"
    _MAX_TF_LINES = 80

    for project in projects:
        proj_id = project.get("id", "")
        if not proj_id:
            continue

        # Derive search terms from the project ID (always a kebab-case slug).
        # Components are human-readable names from the scope agent ("FHIR Proxy"),
        # not directory names — so we use the project ID instead.
        # Try underscore, hyphen, and slash variants: "fhir-proxy" → fhir-proxy|fhir_proxy|fhir/proxy
        base = proj_id
        variants: set[str] = {
            base,
            base.replace("-", "_"),
            base.replace("-", "/"),
        }
        pattern = "|".join(_re.escape(v) for v in sorted(variants))

        try:
            result = subprocess.run(
                ["grep", "-rn", "--include=*.tf", "-E", pattern, str(infra_dir)],
                capture_output=True, text=True, timeout=10,
            )
        except Exception:
            continue

        raw = result.stdout.strip()
        if not raw:
            project["terraform_grep"] = None
            continue

        # Deduplicate and strip absolute path prefix; cap at _MAX_TF_LINES
        seen: set[str] = set()
        out_lines: list[str] = []
        for line in raw.splitlines():
            rel = line.replace(root_str, "")
            # Strip column-number prefix noise; keep the unique content
            content = _re.sub(r"^\S+:\d+:", "", rel).strip()
            if content and content not in seen and len(content) < 200:
                seen.add(content)
                out_lines.append(rel)
            if len(out_lines) >= _MAX_TF_LINES:
                break

        project["terraform_grep"] = "\n".join(out_lines)


def _run_threat(target: str, console: Console) -> None:
    """Generate or refresh OTM threat models for the current platform repo.

    Reads the component inventory saved by /explore. If no inventory exists,
    prompts the user to run /explore first. Accepts an optional project id to
    target a single project; without one, generates all identified projects.
    """
    import datetime
    import json as _json
    import re as _re
    import yaml as _yaml

    # Resolve root and optional project-id filter.
    # Treat target as a directory path only when it looks like one (contains /
    # or starts with . or ~). A bare word like "panome" is a project-id filter,
    # not a path — even if a directory of that name happens to exist.
    _looks_like_path = target and (
        "/" in target or target.startswith(".") or target.startswith("~")
    )
    _target_path = Path(target).expanduser() if _looks_like_path else None
    if _target_path and _target_path.is_dir():
        root = _target_path.resolve()
        filter_id = ""
    else:
        root = Path.cwd().resolve()
        filter_id = target.strip().lstrip("/") if target else ""

    # Load inventory saved by /explore
    inv_path = root / ".code-crew" / "inventory.json"
    if not inv_path.exists():
        console.print("[yellow]No inventory found. Run [bold]/explore[/bold] first to identify components.[/yellow]")
        return

    inv_data = _json.loads(inv_path.read_text(encoding="utf-8"))
    projects: list[dict] = inv_data.get("projects", [])
    inventory: dict = inv_data.get("inventory", {})

    if not projects:
        console.print("[yellow]Inventory is empty. Run [bold]/explore[/bold] to re-scan.[/yellow]")
        return

    if filter_id:
        matched = [p for p in projects if p["id"] == filter_id]
        if not matched:
            ids = ", ".join(p["id"] for p in projects)
            console.print(f"[yellow]Project '{filter_id}' not found. Known projects: {ids}[/yellow]")
            return
        projects = matched

    designs_dir = root / "designs"
    if not designs_dir.exists():
        console.print(
            "[yellow]No designs/ directory found.\n"
            "Add designs/ as a submodule: git submodule add <designs-repo> designs[/yellow]"
        )
        return

    tmd_dir = designs_dir / "TMD"
    tmd_dir.mkdir(exist_ok=True)

    from code_crew.crew import build_threat_model_crew, build_threat_patch_crew, build_threat_gate_crew
    from crewai import Task, Crew, Process, Agent

    today = datetime.date.today().isoformat()
    _run_start = datetime.datetime.now()
    stacks = inventory.get("stacks", [])
    _max_revisions = 3
    _max_lint_retries = 2
    _proj_cfg = _read_project_yaml()
    _max_run_minutes = int(
        _proj_cfg.get("threat", {}).get("timeout_minutes")
        or _proj_cfg.get("flow", {}).get("max_run_minutes", 60)
    )
    _timeout_secs = _max_run_minutes * 60 if _max_run_minutes > 0 else None

    console.print(f"\n[bold]Threat modeling:[/bold] {', '.join(p['id'] for p in projects)}\n")

    for project in projects:
        tmd_file = tmd_dir / f"{project['id']}.yaml"
        revision_feedback = ""
        _last_yaml = ""  # keep the best OTM seen so far for patch revisions

        for _revision in range(_max_revisions + 1):
            if _revision == 0:
                console.print(f"[dim]  [bold]{project['id']}[/bold] — Security Lead + Architect collaborating…[/dim]")
            else:
                console.print(
                    f"[dim]  [bold]{project['id']}[/bold] — revision {_revision}/{_max_revisions} "
                    f"— patching {len(revision_feedback.splitlines())} manager gap(s)…[/dim]"
                )

            try:
                # ── Phase 1: full hierarchical crew on first pass; targeted patch on revisions ──
                # Use patch crew only when we have a valid base OTM to patch. If _last_yaml is
                # empty (no YAML was produced yet) always re-run the full crew — the patch crew
                # with an empty OTM gets confused and searches the filesystem for its own instructions.
                if _revision == 0 or not _last_yaml:
                    model_crew = build_threat_model_crew(project, inventory, revision_feedback)
                else:
                    model_crew = build_threat_patch_crew(project, _last_yaml, revision_feedback)

                if _timeout_secs:
                    from concurrent.futures import ThreadPoolExecutor as _TPE, TimeoutError as _TE
                    import threading as _threading
                    _crew_result_holder = [None]
                    _crew_exc_holder = [None]

                    def _run_crew():
                        try:
                            _crew_result_holder[0] = model_crew.kickoff()
                        except Exception as _e:
                            _crew_exc_holder[0] = _e

                    _t = _threading.Thread(target=_run_crew, daemon=True)
                    _t.start()
                    _t.join(timeout=_timeout_secs)
                    if _t.is_alive():
                        # Thread still running — daemon=True means it dies with the process
                        console.print(
                            f"\n[bold red]  ✗ Run exceeded {_max_run_minutes}-minute limit "
                            f"— stopping (set flow.max_run_minutes in config to change).[/bold red]"
                        )
                        raise RuntimeError(f"Crew timed out after {_max_run_minutes} minutes")
                    if _crew_exc_holder[0] is not None:
                        raise _crew_exc_holder[0]
                    crew_result = _crew_result_holder[0]
                else:
                    crew_result = model_crew.kickoff()
                build_output = crew_result.raw

                # In Process.hierarchical the manager writes the FINAL ANSWER in prose.
                # The actual OTM YAML may be in the worker task's output instead — check both.
                candidate_outputs = [build_output]
                if hasattr(model_crew, "tasks") and model_crew.tasks:
                    for _t in model_crew.tasks:
                        if _t.output and str(_t.output.raw or "").strip():
                            candidate_outputs.append(str(_t.output.raw))

                def _extract_from(text: str) -> str:
                    cleaned = _re.sub(r"<\|[^|>]+\|>[^\n]*\n?", "", text)
                    m = _re.search(
                        r"(otmVersion:.*?)(?:OTM BUILD COMPLETE|```\s*$)", cleaned, _re.DOTALL
                    )
                    if m:
                        return m.group(1).strip()
                    candidate = cleaned.split("OTM BUILD COMPLETE")[0].strip()
                    candidate = _re.sub(r"^```ya?ml\s*\n?", "", candidate, flags=_re.MULTILINE)
                    candidate = _re.sub(r"^```\s*$", "", candidate, flags=_re.MULTILINE).strip()
                    return candidate if "otmVersion:" in candidate else ""

                yaml_text = ""
                for _candidate in candidate_outputs:
                    yaml_text = _extract_from(_candidate)
                    if yaml_text:
                        break

                # Strip NVIDIA/LLaMA model artifacts for the final clean_output used downstream
                clean_output = _re.sub(r"<\|[^|>]+\|>[^\n]*\n?", "", build_output)

                if not yaml_text or "otmVersion:" not in yaml_text:
                    # Agent may have written the file via shell instead of outputting text.
                    # Only use the disk file if the agent wrote it THIS run (mtime after run start).
                    _disk_ok = False
                    if tmd_file.exists():
                        import os as _os
                        _mtime = datetime.datetime.fromtimestamp(_os.path.getmtime(tmd_file))
                        _disk_content = tmd_file.read_text(encoding="utf-8")
                        if _mtime > _run_start and "otmVersion:" in _disk_content:
                            _disk_ok = True
                    if _disk_ok:
                        console.print(f"[dim]  No YAML in response — reading from disk (agent wrote directly)[/dim]")
                        yaml_text = _disk_content
                        # Strip our own file header if present
                        yaml_text = _re.sub(r"^#[^\n]*\n", "", yaml_text, flags=_re.MULTILINE).strip()
                    else:
                        # Log a snippet of what the manager actually returned to aid diagnosis
                        _preview = (build_output or "").strip()[:300].replace("\n", "↵")
                        console.print(
                            f"[yellow]  No valid OTM YAML extracted for {project['id']} "
                            f"on attempt {_revision + 1} — retrying.[/yellow]\n"
                            f"[dim]  Manager output preview: {_preview}[/dim]"
                        )
                        # Carry the previous attempt's established content forward so the
                        # Architect does not re-read files and re-discover zones from scratch.
                        _prev_content = (build_output or "").strip()[:3000]
                        revision_feedback = (
                            "## Established context from previous attempt\n\n"
                            "The previous attempt produced the analysis below but did NOT output OTM YAML.\n"
                            "The trust zones, component boundaries, and findings below are already established — "
                            "do NOT re-read source files, Terraform, or design docs to re-discover them.\n\n"
                            f"{_prev_content}\n\n"
                            "## What to do now\n\n"
                            "Proceed directly to Phase 1b (component inventory using the zones above) and then "
                            "produce the complete OTM YAML as plain text in your response. "
                            "End with OTM BUILD COMPLETE. Do NOT write any files to disk."
                        )
                        continue

                # ── Lint → AI-fix loop ────────────────────────────────────────────────
                # Only re-trigger the AI fix when the same error (same line/column)
                # persists — a different error means the fix changed something, so stop.
                _prev_err_mark: tuple | None = None
                for _lint_attempt in range(_max_lint_retries + 1):
                    try:
                        _yaml.safe_load(yaml_text)
                        break
                    except _yaml.YAMLError as _ye:
                        _mark = _ye.problem_mark
                        _err_key = (_mark.line, _mark.column) if _mark else str(_ye)

                        if _lint_attempt > 0 and _err_key != _prev_err_mark:
                            # Error shifted — fix changed the YAML; stop here to avoid
                            # chasing a moving target
                            console.print(
                                f"[dim]  Lint error shifted after fix (now line {_mark.line + 1 if _mark else '?'}) "
                                f"— stopping lint loop.[/dim]"
                            )
                            break

                        if _lint_attempt == _max_lint_retries:
                            console.print(
                                f"[yellow]  OTM YAML for {project['id']} still invalid after "
                                f"{_max_lint_retries} fix attempts — same error persists.[/yellow]"
                            )
                            yaml_text = ""
                            break

                        _prev_err_mark = _err_key
                        _line = _mark.line + 1 if _mark else "?"
                        console.print(f"[dim]  Lint error at line {_line}: {_ye.problem} — asking architect to fix…[/dim]")
                        from code_crew.crew import build_agents, _make_tools
                        _fix_task = Task(
                            name=f"fix_otm_yaml_{project['id']}",
                            description=(
                                f"The OTM YAML for project '{project['id']}' has a YAML syntax error:\n\n"
                                f"  Line {_line}: {_ye.problem}\n\n"
                                f"Here is the invalid YAML:\n\n```yaml\n{yaml_text}\n```\n\n"
                                "Output the fully corrected YAML. Do not truncate. "
                                "End with OTM BUILD COMPLETE.\n\n"
                                "CRITICAL: Write the YAML as plain text. Do NOT call any tools."
                            ),
                            expected_output="Complete valid OTM YAML. Ends with OTM BUILD COMPLETE.",
                            agent=build_agents(_make_tools())["architect"],
                        )
                        _fix_crew = Crew(
                            agents=[_fix_task.agent], tasks=[_fix_task],
                            process=Process.sequential, verbose=True,
                        )
                        _fix_out = _re.sub(r"<\|[^|>]+\|>[^\n]*\n?", "", _fix_crew.kickoff().raw)
                        _fx = _re.search(
                            r"(otmVersion:.*?)(?:OTM BUILD COMPLETE|```\s*$)", _fix_out, _re.DOTALL
                        )
                        yaml_text = _fx.group(1).strip() if _fx else _fix_out.split("OTM BUILD COMPLETE")[0].strip()

                if not yaml_text:
                    if _revision < _max_revisions:
                        revision_feedback = (
                            "The OTM YAML produced contained YAML syntax errors that could not be auto-fixed. "
                            "Pay careful attention to YAML structure — ensure every risk block has "
                            "explicit `likelihood:` and `impact:` keys, not bare scalars."
                        )
                        continue
                    console.print(f"[yellow]  Skipping {project['id']} — YAML could not be fixed.[/yellow]")
                    break

                # Save the best valid OTM seen so far for patch revisions.
                # Only set this AFTER lint succeeds so _last_yaml is always valid YAML.
                _last_yaml = yaml_text

                # ── Phase 2: Manager gate ─────────────────────────────────────────────
                console.print(f"[dim]  [bold]{project['id']}[/bold] — manager reviewing completeness…[/dim]")
                gate_crew = build_threat_gate_crew(project, yaml_text, stacks)
                gate_output = gate_crew.kickoff().raw

                if "THREAT MODEL APPROVED" in gate_output:
                    residual = gate_output.split("THREAT MODEL APPROVED", 1)[1].strip()
                    tmd_file.write_text(
                        f"# OpenThreatModel v0.2.0 — generated by /threat on {today}\n"
                        f"# Project: {project['name']}\n\n"
                        + yaml_text + "\n",
                        encoding="utf-8",
                    )
                    _rel = tmd_file.relative_to(root) if tmd_file.is_relative_to(root) else tmd_file.name
                    console.print(f"[green]✓[/green] [bold]{project['id']}[/bold] approved. Written [dim]{_rel}[/dim]")
                    if residual:
                        console.print(f"[dim]  Residual risk: {residual.strip()[:300]}[/dim]")
                    _convert_tmd(tmd_file, tmd_dir, root, console)
                    break  # done for this project

                elif "NEEDS REVISION" in gate_output and _revision < _max_revisions:
                    gaps = gate_output.split("NEEDS REVISION", 1)[1].strip()
                    console.print(
                        f"[yellow]  Manager sent {project['id']} back for revision:[/yellow]\n"
                        f"  [dim]{gaps[:400]}[/dim]"
                    )
                    revision_feedback = gaps
                    # loop: re-run model crew with the manager's feedback injected

                else:
                    # max revisions reached or unexpected gate output — write best effort
                    console.print(
                        f"[yellow]  {project['id']}: max revisions reached or gate inconclusive — "
                        f"writing best-effort OTM.[/yellow]"
                    )
                    tmd_file.write_text(
                        f"# OpenThreatModel v0.2.0 — generated by /threat on {today} [UNREVIEWED]\n"
                        f"# Project: {project['name']}\n\n"
                        + yaml_text + "\n",
                        encoding="utf-8",
                    )
                    _rel = tmd_file.relative_to(root) if tmd_file.is_relative_to(root) else tmd_file.name
                    console.print(f"[dim]  Written (unreviewed): {_rel}[/dim]")
                    _convert_tmd(tmd_file, tmd_dir, root, console)
                    break

            except Exception as exc:
                console.print(f"[yellow]  OTM build failed for {project['id']}: {exc}[/yellow]")
                break


def _run_fix(console: Console) -> None:
    """Install all missing tools using the fix hints from startup checks."""
    import subprocess
    from code_crew.startup import run_checks

    summary = run_checks()
    failed = [c for c in summary.checks if not c.ok and c.fix]

    # Handle designs dir separately — interactive, not a brew/pip command
    designs_check = next((c for c in failed if c.name == "designs"), None)
    if designs_check:
        _init_designs_dir(Path.cwd(), console)
        failed = [c for c in failed if c.name != "designs"]

    _RUNNABLE = ("brew install", "pip install", "go install", "npm install", "npm i", "cargo install")
    to_run = [(c.name, c.fix.split("#")[0].strip()) for c in failed
              if any(c.fix.startswith(p) for p in _RUNNABLE)]

    if not to_run:
        if not designs_check:
            console.print("[dim]Nothing to fix — all tools present.[/dim]")
        return

    console.print(f"[bold]Installing {len(to_run)} missing tool(s)...[/bold]")
    for name, cmd in to_run:
        console.print(f"\n[dim]→ {cmd}[/dim]")
        # shell=True so && and | work correctly (brew install gh && gh auth login,
        # curl ... | sh, etc.). Commands come from _cli_install_hints(), not user
        # input, so shell injection is not a concern.
        result = subprocess.run(cmd, shell=True)
        if result.returncode == 0:
            console.print(f"  [green]✓[/green] {name}")
        else:
            console.print(f"  [red]✗[/red] {name} — failed (exit {result.returncode})")

    console.print()


def _inject_help(feedback: str, state: ReplState, console: Console) -> None:
    stuck = state.get_stuck()
    if not stuck:
        console.print("[yellow]No flow is currently waiting for help.[/yellow]")
        return
    key = stuck[0]
    flow, _ = state.active[key]

    if flow.state.needs_help_gate == "chief_architect_consultation":
        arch_out = flow.state.task_outputs.get("architecture_review", "")
        parsed = _parse_consultation(arch_out)
        if parsed and feedback.strip().isdigit():
            idx = int(feedback.strip()) - 1
            if 0 <= idx < len(parsed["options"]):
                opt = parsed["options"][idx]
                feedback = (
                    f"Selected Option {idx + 1}: {opt['name']}. "
                    "Please document this decision in a new ADR (Status: Accepted), "
                    "update the relevant SAD section, and update or create the ADD "
                    "for the affected component. Then confirm APPROVED TO PROCEED."
                )
        _shown_consultation.discard(key)

    flow.inject_feedback(feedback)
    console.print(f"[green]Feedback sent to {key}. Resuming...[/green]")


# ---------------------------------------------------------------------------
# Other commands
# ---------------------------------------------------------------------------

def _show_context(key: str, state: ReplState, console: Console) -> None:
    """Show completed task outputs and Q&A for the given key.

    Source priority:
    1. In-memory task_outputs from an active flow (live run).
    2. Session file entries (role starts with 'task:') — covers past runs and
       the current session after the flow finishes.
    3. Relay Q&A log from the active flow.
    """
    import time as _time

    with state.lock:
        flows = list(state.active.values())

    matched = [(flow, fut) for flow, fut in flows if not key or flow.state.jira_key == key]
    relay_log: list[dict] = []
    shown_tasks: set[str] = set()

    # --- Source 1: in-memory task_outputs (active flow) ---
    for flow, _ in matched:
        jira_key = flow.state.jira_key
        outputs = getattr(flow.state, "task_outputs", {})
        if outputs:
            console.print(f"\n[bold]Completed tasks — {jira_key} (live)[/bold]")
            for task_name, output in outputs.items():
                shown_tasks.add(task_name)
                snippet = output.replace("\n", " ")[:200]
                if len(output) > 200:
                    snippet += "…"
                console.print(f"  [green]✓[/green] [bold]{task_name}[/bold]: [dim]{snippet}[/dim]")
        relay_log.extend(flow.relay.log)

    # --- Source 2: session file task entries ---
    session_tasks = [
        ex for ex in state.session._exchanges
        if ex.role.startswith("task:") and ex.role[5:] not in shown_tasks
    ]
    # Filter by key prefix if requested (e.g. task content usually references the jira key)
    if key and session_tasks:
        session_tasks = [ex for ex in session_tasks if key.lower() in ex.content.lower()
                         or key.lower() in ex.role.lower()]
    if session_tasks:
        console.print(f"\n[bold]Session history — {state.session.name}[/bold]")
        for ex in session_tasks:
            task_name = ex.role[5:]  # strip "task:" prefix
            snippet = ex.content.replace("\n", " ")[:200]
            if len(ex.content) > 200:
                snippet += "…"
            console.print(f"  [dim]✓[/dim] [bold]{task_name}[/bold]: [dim]{snippet}[/dim]")

    if not matched and not session_tasks:
        console.print(
            f"[dim]No task history for {key}.[/dim]" if key
            else "[dim]No task history in this session. Run /issue to start a flow.[/dim]"
        )
        return

    # --- Source 3: agent Q&A relay log ---
    if relay_log:
        console.print(f"\n[bold]Agent questions & answers ({len(relay_log)})[/bold]")
        for i, entry in enumerate(relay_log, 1):
            ts = _time.strftime("%H:%M", _time.localtime(entry["timestamp"]))
            console.print(f"\n  [dim]{i}. {entry['jira_key']}  {ts}[/dim]")
            console.print(f"  [cyan]Q:[/cyan] {entry['question']}")
            console.print(f"  [green]A:[/green] {entry['answer']}")

        console.print(
            f"\n[dim]Export Q&A to [bold].code-crew/decisions/{(key or 'session').lower()}.md[/bold]? [y/N][/dim] ",
            end="",
        )
        answer = input().strip().lower()
        if answer in ("y", "yes"):
            _export_context(key or "session", relay_log, console)


def _export_context(stem: str, log: list[dict], console: Console) -> None:
    import time as _time
    out_dir = Path.cwd() / ".code-crew" / "decisions"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{stem.lower()}.md"
    lines = [f"# Decisions & clarifications — {stem}\n\n"]
    lines.append(f"*Generated {_time.strftime('%Y-%m-%d %H:%M')}*\n\n")
    lines.append(
        "> Review these Q&A pairs and promote relevant decisions to ADR or ADD entries.\n\n"
    )
    for i, entry in enumerate(log, 1):
        ts = _time.strftime("%Y-%m-%d %H:%M", _time.localtime(entry["timestamp"]))
        lines.append(f"## {i}. {entry['jira_key']}  _{ts}_\n\n")
        lines.append(f"**Q (agent):** {entry['question']}\n\n")
        lines.append(f"**A (human):** {entry['answer']}\n\n")
    out_file.write_text("".join(lines), encoding="utf-8")
    console.print(f"[green]✓[/green] Saved to [dim]{out_file}[/dim]")


def _collect_status_parts(state: ReplState) -> list[str]:
    """Build HTML fragments for each active flow. Called each prompt redraw."""
    import time as _t
    from code_crew.flow import _fmt_k

    parts: list[str] = []
    with state.lock:
        for key, (flow, _) in list(state.active.items()):
            s = flow.state
            if s.status == "passed":
                continue
            if s.status == "failed":
                parts.append(f"<ansired>✗ {key} failed</ansired>")
                continue
            if s.status == "needs_help":
                parts.append(f"<ansiyellow>⚑ {key}: needs help</ansiyellow>")
                continue
            task = (s.current_task or "starting").replace("_", " ")
            task_start = getattr(flow, "_task_start", 0.0)
            elapsed = ""
            if task_start:
                secs = int(_t.monotonic() - task_start)
                m, sec = divmod(secs, 60)
                elapsed = f"{m}m {sec:02d}s" if m else f"{sec}s"
            tok = _fmt_k(s.session_tokens) if s.session_tokens else ""
            meta = " · ".join(p for p in [elapsed, f"↓ {tok}" if tok else ""] if p)
            entry = f"<b>✻</b> {task}  <ansicyan>{key}</ansicyan>"
            if meta:
                entry += f"  <ansiblue>{meta}</ansiblue>"
            parts.append(entry)
    return parts


def _build_prompt(state: ReplState) -> HTML:
    """Build the prompt prefix shown above the ❯ cursor.

    Layout (top to bottom):
      ─────── separator ───────────   (always shown — marks boundary of prior output)
        ✻ task  2m 15s  ↓ 5k  │ …   (status row — only shown when flows are active)
      ─────── separator ───────────   (only shown when status row is present)
      ❯ ▌                             (cursor on its own line)

    The separator + status scroll into terminal history on submit, giving useful
    context (what the agent was doing when you sent that message).
    The hint never scrolls — it lives in the bottom_toolbar below the cursor.
    """
    _SEP = "─" * 300

    parts = _collect_status_parts(state)
    pending_q = state.get_pending_question()
    stuck = state.get_stuck()

    if pending_q:
        cursor = (
            f"<ansicyan><b>[{pending_q.jira_key}] answer</b></ansicyan>"
            f" <ansigreen><b>❯</b></ansigreen> "
        )
    elif stuck and _is_in_consultation(stuck, state):
        cursor = (
            f"<ansiyellow><b>({stuck[0]} awaits decision)</b></ansiyellow>"
            f" <ansigreen><b>❯</b></ansigreen> "
        )
    elif stuck:
        cursor = (
            f"<ansiyellow><b>({stuck[0]} needs help)</b></ansiyellow>"
            f" <ansigreen><b>❯</b></ansigreen> "
        )
    else:
        cursor = "<ansigreen><b>❯</b></ansigreen> "

    sep = f"<ansibrightblack>{_SEP}</ansibrightblack>"

    if parts:
        status_row = "  " + "   <ansibrightblack>│</ansibrightblack>   ".join(parts)
        return HTML(f"{sep}\n{status_row}\n{sep}\n{cursor}")

    return HTML(f"{sep}\n{cursor}")


def _bottom_toolbar(_state: ReplState) -> HTML:
    """Fixed bar below the cursor — hint only, never scrolls into history."""
    hint = "Alt+Enter for newline  ·  /help for stuck flows"
    return HTML(f"<ansibrightblack>  {hint}</ansibrightblack>")


def _show_status(state: ReplState, console: Console) -> None:
    import time as _time
    with state.lock:
        if not state.active:
            console.print("[dim]No active runs.[/dim]")
            return
        for key, (flow, future) in state.active.items():
            s = flow.state
            task = s.current_task or "—"
            agent = (s.current_agent or "").upper() or "—"
            retries = f"cr={s.code_review_retries} sec={s.sec_review_retries} dod={s.dod_retries}"
            # Live elapsed for the current task (resets each task)
            task_start = getattr(flow, "_task_start", 0.0)
            if s.status == "running" and task_start:
                secs = _time.monotonic() - task_start
                mins, sec = divmod(int(secs), 60)
                elapsed = f"{mins}m{sec:02d}s" if mins else f"{sec}s"
            else:
                elapsed = "—"
            console.print(
                f"  [cyan]{key}[/cyan]  {s.status}"
                f"  task=[bold]{task}[/bold]  agent={agent}"
                f"  elapsed={elapsed}  retries({retries})"
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

def _handle_session(args: list[str], state: ReplState, console: Console) -> None:
    """Handle /session [new [name] | use <name> | list]."""
    from shared.session import Session

    sub = args[0].lower() if args else "show"

    if sub == "list":
        sessions = Session.list_all()
        if not sessions:
            console.print("[dim]No sessions yet.[/dim]")
            return
        for name in sessions:
            marker = "[bold cyan]→[/bold cyan] " if name == state.session.name else "  "
            console.print(f"{marker}{name}")

    elif sub == "new":
        name = args[1] if len(args) > 1 else Session.default_name()
        state.session = Session.load_or_create(name)
        console.print(f"[green]New session:[/green] [bold]{name}[/bold]")

    elif sub == "use":
        if len(args) < 2:
            console.print("[red]Usage: /session use <name>[/red]")
            return
        name = args[1]
        state.session = Session.load_or_create(name)
        exchanges = len(state.session._exchanges)
        console.print(
            f"[green]Resumed session:[/green] [bold]{name}[/bold]"
            f"  [dim]({exchanges} exchange(s))[/dim]"
        )
        if exchanges:
            console.print(state.session.summary())

    else:  # /session or /session show
        s = state.session
        exchanges = len(s._exchanges)
        console.print(
            f"[bold]Session:[/bold] {s.name}  "
            f"[dim]{s._path}  ({exchanges} exchange(s))[/dim]"
        )
        if exchanges:
            console.print(s.summary())
        console.print(
            "[dim]  /session new [name] · /session use <name> · /session list[/dim]"
        )


def _task_complete_callback(ui: "SprintUI", session: "Session", task_outputs: dict):
    """Return an on_task_complete that prints via UI and persists the full output to session."""
    def _cb(issue_key: str, task_name: str, summary: str) -> None:
        ui.show_summary(issue_key, task_name, summary)
        # task_outputs[task_name] is set with the full output before this callback fires
        full = task_outputs.get(task_name, summary)
        session.add(f"task:{task_name}", full)
    return _cb


def _ask_agent(agent_name: str, question: str, state: ReplState, console: Console) -> None:
    from code_crew.chat_agent import ask_agent, AGENT_ALIASES
    canonical = AGENT_ALIASES.get(agent_name)
    if not canonical:
        known = ", ".join(sorted(set(AGENT_ALIASES.values())))
        console.print(f"[red]Unknown agent '{agent_name}'.[/red] Known: {known}")
        return
    console.print(f"[dim][session: {state.session.name}] Asking {canonical}…[/dim]")
    sprint_ctx = _sprint_context_str(state)
    session_ctx = state.session.context_block()
    ctx = "\n\n".join(filter(None, [session_ctx, sprint_ctx]))
    state.session.add("user", f"[to {canonical}] {question}")
    try:
        answer = ask_agent(agent_name, question, sprint_context=ctx)
        console.print(answer)
        state.session.add(canonical, answer)
    except Exception as exc:
        console.print(f"[red]Error from {canonical}: {exc}[/red]")


def _handle_chat(line: str, state: ReplState, console: Console) -> None:
    from code_crew.chat_agent import ask

    sprint_ctx = _sprint_context_str(state)
    session_ctx = state.session.context_block()
    ctx = "\n\n".join(filter(None, [session_ctx, sprint_ctx]))
    console.print(f"[dim][session: {state.session.name}] Thinking…[/dim]")
    state.session.add("user", line)
    try:
        answer = ask(line, sprint_context=ctx)
        console.print(answer)
        state.session.add("assistant", answer)
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
    # Tech stacks
    "go-backend",
    "typescript-react",
    "python",
    "terraform",
    "terraform-aws",
    # Compliance frameworks
    "owasp",
    "hipaa",
    "soc2",
    "gdpr",
    "ccpa",
    "fips-140-3",
    "nist",
    "cfr-part-11",
    # AI/ML security
    "ai-ml",
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
        source = "[dim](.code-crew/config.yaml)[/dim]"
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
            f"[dim]No profiles found. Add [bold]{PROFILES_DIR}/<name>.yaml[/bold] to create one.[/dim]"
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


def _print_startup_banner(console: Console, summary) -> None:
    from rich.table import Table

    active_profile = os.environ.get("CODE_CREW_PROFILE", "")
    profile_str = f"  [dim cyan]profile: {active_profile}[/dim cyan]" if active_profile else ""

    console.print()
    console.print(f"[bold]code-crew[/bold]{profile_str}", end="  ")
    meta_parts = []
    if summary.detected_stacks:
        meta_parts.append(f"stacks: {', '.join(summary.detected_stacks)}")
    if summary.detected_ci_methods:
        meta_parts.append(f"ci: {', '.join(summary.detected_ci_methods)}")
    if meta_parts:
        console.print(f"[dim]{' · '.join(meta_parts)}[/dim]")
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
