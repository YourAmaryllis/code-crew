"""
Interactive REPL for code-crew.

Slash commands:
  /design <KEY>                 — requirement → ADD/ADR design docs (runs before /issue)
  /ux <KEY>                     — Figma → component spec → implementation → UX review loop
  /issue <KEY> [--retries N]    — run a single ticket (Jira, Linear, or GitHub; /jira is an alias)
  /sprint <name> [--retries N]  — plan + run a sprint (parallel where safe)
  /init                         — scaffold a new project in cwd
  /status                       — show active runs
  /details <KEY>                — toggle detail output for a ticket
  /help <message>               — inject guidance into a stuck flow
  /retry                        — force retry the stuck flow
  /abort [KEY]                  — abort a run
  /verify                       — full codebase audit: arch + security + compliance → report + optional issue creation
  /explore [path]               — scan platform dir tree, save as agent context
  /mcp list|connect|disconnect|status  — manage MCP server connections
  /skills                       — list available/active skills
  /skill install <url|user/repo> — install skill(s) from GitHub repo or raw URL
  /skill <name>                 — activate a skill
  /skill off [name]             — deactivate one or all skills
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
    args, _ = parser.parse_known_args()

    _bootstrap(profile=args.profile)

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
        _last_interrupt = 0.0
        try:
            while True:
                pending_q = state.get_pending_question()
                stuck = state.get_stuck()

                # Show consultation panel the first time we detect the gate
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

                if pending_q:
                    prompt_msg = HTML(
                        f'<ansicyan><b>[{pending_q.jira_key}] answer</b></ansicyan>'
                        f' <ansigreen><b>&gt;</b></ansigreen> '
                    )
                elif stuck and _is_in_consultation(stuck, state):
                    prompt_msg = HTML(
                        f'<ansiyellow><b>({stuck[0]} awaits decision)</b></ansiyellow>'
                        f' <ansigreen><b>&gt;</b></ansigreen> '
                    )
                elif stuck:
                    prompt_msg = HTML(
                        f'<ansiyellow><b>({stuck[0]} needs help)</b></ansiyellow>'
                        f' <ansigreen><b>&gt;</b></ansigreen> '
                    )
                else:
                    tok = state.session_tokens()
                    tok_str = f'<ansiblue>[{tok}]</ansiblue> ' if tok else ''
                    prompt_msg = HTML(f'{tok_str}<ansigreen><b>&gt;</b></ansigreen> ')

                try:
                    line = session.prompt(prompt_msg)
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

                try:
                    if pending_q:
                        # Any input while an agent is waiting → answer that agent
                        state.answer_pending(line)
                    elif _is_in_consultation(stuck, state) and not line.startswith("/"):
                        # Direct input (number or text) routes to architect feedback
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
            console.print("[dim]Bye.[/dim]")
            # Force-kill after 10s if background flow threads don't finish.
            # Langfuse flush() above is synchronous, so spans are already sent.
            t = threading.Timer(10.0, os._exit, args=(0,))
            t.daemon = True
            t.start()


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

    elif cmd in ("/issue", "/jira"):
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

    elif cmd == "/fix":
        _run_fix(console)

    elif cmd == "/verify":
        _start_verify(console)

    elif cmd == "/domain":
        _handle_domain(parts[1:], console)

    elif cmd == "/explore":
        target = parts[1] if len(parts) > 1 else ""
        _run_explore(target, console)

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

def _detect_project(root: Path) -> dict:
    """Scan root for signals and return discovered config values."""
    import json as _json

    found: dict = {}

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
    for candidate in ("docs/swagger.json", "docs/swagger.yaml", "docs/openapi.json",
                       "docs/openapi.yaml", "openapi.yaml", "openapi.json"):
        if (root / candidate).exists():
            found["api.doc_standard"] = "openapi"
            break

    # --- architecture style ---
    all_dirs = {p.name for p in root.rglob("*") if p.is_dir()}
    if "ports" in all_dirs and ("driving" in all_dirs or "driven" in all_dirs):
        found["architecture.style"] = "hexagonal"
    elif "domain" in all_dirs and "application" in all_dirs and any(
        (root / "domain" / sub).exists() for sub in ("model", "services", "repositories")
    ):
        found["architecture.style"] = "onion"
    elif "usecases" in all_dirs or ("domain" in all_dirs and "adapters" in all_dirs):
        found["architecture.style"] = "clean"

    return found


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
        console.print("Project name: ", end="")
        name = input().strip() or root.name
        console.print("Issue tracker [jira/linear/github]: ", end="")
        tracker = input().strip() or "jira"
        console.print("Project key (e.g. PROJ): ", end="")
        project_key = input().strip().upper() or "PROJ"

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
    detected = _detect_project(root)

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

    console.print("\n[bold green]Done.[/bold green] Run [bold]/jira KEY[/bold] to start.")


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

def _start_verify(console: Console) -> None:
    """Run the full verification audit and prompt to open issues for REQUIRED findings."""
    import re
    import urllib.request
    import urllib.error
    import json as _json

    from code_crew.crew import build_verify_crew

    console.print("\n[bold]Starting verification audit…[/bold]")
    console.print("[dim]Scans: architecture · security · compliance → chief review → report[/dim]\n")

    crew = build_verify_crew(project_root=str(Path.cwd()))
    result = crew.kickoff()
    output = str(result)

    # --- parse REQUIRED findings from chief review output ---
    required = re.findall(r"^REQUIRED:\s+(.+)$", output, re.MULTILINE)

    # --- find report path ---
    report_match = re.search(r"REPORT SAVED:\s+(\S+)", output)
    report_path = report_match.group(1) if report_match else ".code-crew/verify-report.md"

    console.print(f"\n[green]✓[/green] Report saved: [bold]{report_path}[/bold]")

    if not required:
        console.print("[green]No REQUIRED findings — codebase is clean.[/green]")
        return

    console.print(f"\n[red bold]{len(required)} REQUIRED finding(s):[/red bold]")
    for i, r in enumerate(required, 1):
        console.print(f"  [red]{i}.[/red] {r}")

    # --- prompt to open issues ---
    console.print(f"\nOpen {len(required)} Jira issue(s) for REQUIRED findings? [y/N] ", end="")
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"

    if answer != "y":
        console.print("[dim]Issues not created. Fix findings manually.[/dim]")
        return

    jira_url = os.environ.get("JIRA_URL", "").rstrip("/")
    jira_user = os.environ.get("JIRA_USER", "")
    jira_token = os.environ.get("JIRA_TOKEN", "")
    project_key = os.environ.get("PROJECT_KEY", "PROJ")

    if not all([jira_url, jira_user, jira_token]):
        console.print("[yellow]JIRA_URL / JIRA_USER / JIRA_TOKEN not set — printing issues instead:[/yellow]")
        for r in required:
            console.print(f"  [bold]Title:[/bold] {r[:100]}")
            console.print(f"  [bold]Labels:[/bold] verify, security\n")
        return

    import base64
    creds = base64.b64encode(f"{jira_user}:{jira_token}".encode()).decode()
    created: list[str] = []

    for finding in required:
        # Strip tag prefix like [SEC] or [ARCH] for the summary
        summary = re.sub(r"^\[(ARCH|SEC|COMP)\]\s*", "", finding)[:200]
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
                "labels": ["verify", "security-audit"],
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

    crew = build_domain_extract_crew(target_path=target)
    result = crew.kickoff()
    output = str(result)

    import re
    match = re.search(r"DOMAIN EXTRACT COMPLETE", output, re.IGNORECASE)
    if match:
        console.print("\n[green bold]Domain extract complete.[/green bold]")
        console.print("[dim]Outputs saved to designs/DMD/[/dim]")
    else:
        console.print("\n[yellow]Extract may be incomplete — check agent output above.[/yellow]")


def _run_explore(target: str, console: Console) -> None:
    """
    Scan the project directory, detect tech stacks, optionally generate a
    starter OTM threat model, and save context files so agents share the same
    picture of the project structure.
    """
    import datetime
    import json as _json

    root = Path(target).expanduser() if target else Path.cwd()
    if not root.exists():
        console.print(f"[red]Directory not found: {root}[/red]")
        return

    _SKIP = {".git", "vendor", "node_modules", "__pycache__", ".terraform",
              ".idea", ".vscode", "dist", "build", "coverage", ".next"}

    def _tree(path: Path, prefix: str = "", depth: int = 0) -> list[str]:
        if depth > 4:
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
                lines.extend(_tree(entry, prefix + ext, depth + 1))
        return lines

    # --- tree ---
    console.print(f"\n[bold]{root}[/bold]")
    tree_lines = _tree(root)
    tree_text = "\n".join(tree_lines)
    console.print(tree_text)

    # --- stack detection ---
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
    if list(root.glob("requirements*.txt")) or list(root.glob("pyproject.toml")):
        stacks.append("python")
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
    elif list(root.rglob("requirements*.txt")):
        for f in list(root.rglob("requirements*.txt"))[:5]:
            try:
                if any(kw in f.read_text().lower() for kw in
                       ("torch", "transformers", "openai", "anthropic", "langchain", "bedrock")):
                    stacks.append("ai-ml")
                    break
            except Exception:
                pass
    if any(root.rglob("*.feature")):
        stacks.append("bdd-testing")

    if stacks:
        console.print(f"\n[bold]Detected stacks:[/bold] {', '.join(stacks)}")
    else:
        console.print("\n[dim]No stacks detected — set stacks: in .code-crew/config.yaml if needed.[/dim]")

    # --- architecture pattern detection ---
    arch_style: str = ""
    all_dirs = {p.name for p in root.rglob("*") if p.is_dir() and p.name not in _SKIP}
    if "ports" in all_dirs and ("driving" in all_dirs or "driven" in all_dirs):
        arch_style = "hexagonal"
    elif "domain" in all_dirs and "application" in all_dirs and any(
        (root / "domain" / sub).exists() for sub in ("model", "services", "repositories")
    ):
        arch_style = "onion"
    elif "usecases" in all_dirs or ("domain" in all_dirs and "adapters" in all_dirs):
        arch_style = "clean"

    if arch_style:
        console.print(f"[bold]Detected architecture:[/bold] {arch_style}")
        os.environ["ARCHITECTURE_STYLE"] = arch_style
    else:
        console.print("[dim]Architecture pattern not detected — set architecture.style in config if needed.[/dim]")

    # --- migration tool detection ---
    migration_tool: str = ""
    if (root / "alembic.ini").exists():
        migration_tool = "alembic"
    elif (root / "atlas.hcl").exists() or (root / "atlas.sum").exists():
        migration_tool = "atlas"
    else:
        for mf in list(root.rglob("*.sql"))[:20]:
            try:
                if "-- +goose" in mf.read_text(encoding="utf-8", errors="ignore"):
                    migration_tool = "goose"
                    break
            except OSError:
                pass

    if migration_tool:
        console.print(f"[bold]Detected migration tool:[/bold] {migration_tool}")
        os.environ["DB_MIGRATION_TOOL"] = migration_tool
    else:
        console.print("[dim]Migration tool not detected — set db.migration_tool in config if needed.[/dim]")

    # --- save structure.md ---
    out_dir = root / ".code-crew"
    out_dir.mkdir(exist_ok=True)
    stacks_yaml = "\n".join(f"  - {s}" for s in stacks) if stacks else "  # none detected"
    arch_line = f"\n## Detected architecture\n\n```yaml\narchitecture:\n  style: {arch_style}\n```\n" if arch_style else ""
    db_line = f"\n## Detected migration tool\n\n```yaml\ndb:\n  migration_tool: {migration_tool}\n```\n" if migration_tool else ""
    (out_dir / "structure.md").write_text(
        f"Directory tree of `{root.name}` (auto-generated by /explore):\n\n"
        f"```\n{root.name}/\n{tree_text}\n```\n\n"
        f"## Detected stacks\n\n"
        f"```yaml\nstacks:\n{stacks_yaml}\n```\n"
        + arch_line
        + db_line,
        encoding="utf-8",
    )
    console.print(f"\n[green]✓[/green] Saved to [dim]{out_dir / 'structure.md'}[/dim]")

    # --- OTM threat model generation ---
    designs_dir = root / "designs"
    if not designs_dir.exists():
        console.print(
            "\n[dim]No designs/ directory found — skipping threat model generation.\n"
            "Add designs/ as a submodule: git submodule add <designs-repo> designs[/dim]"
        )
        return

    tmd_dir = designs_dir / "TMD"
    tmd_dir.mkdir(exist_ok=True)
    service_id = root.name.lower().replace(" ", "-")
    tmd_file = tmd_dir / f"{service_id}.yaml"

    if tmd_file.exists():
        console.print(f"\n[dim]Threat model already exists: designs/TMD/{tmd_file.name} — skipping.[/dim]")
        return

    # Candidate service directories: top-level dirs containing source files
    svc_dirs = [
        d.name for d in sorted(root.iterdir())
        if d.is_dir() and d.name not in _SKIP and not d.name.startswith(".")
        and (any(d.rglob("*.go")) or any(d.rglob("*.py"))
             or any(d.rglob("*.ts")) or any(d.rglob("*.tsx")))
    ][:8]

    today = datetime.date.today().isoformat()
    has_ai = "ai-ml" in stacks

    components = ["  - name: External User\n    id: external-user\n"
                  "    description: End user or external system\n"
                  "    parent:\n      trustZone: internet\n    type: actor"]
    for svc in svc_dirs:
        svc_id = svc.lower().replace("_", "-")
        components.append(
            f"  - name: {svc}\n    id: {svc_id}\n    description: ''\n"
            f"    parent:\n      trustZone: private\n    type: service\n"
            f"    assets:\n      processed: []\n      stored: []"
        )
    if has_ai:
        components.append(
            "  - name: LLM Inference\n    id: llm-inference\n"
            "    description: Large language model inference endpoint\n"
            "    parent:\n      trustZone: private\n    type: ai-model\n"
            "    assets:\n      processed: []\n      stored: []"
        )

    tmd_file.write_text(
        f"# OpenThreatModel v0.2.0 — auto-generated by /explore on {today}\n"
        f"# Edit: add descriptions, assets, dataflows, and threats.\n"
        f"# See designs/functions/threat-model for instructions.\n\n"
        f"otmVersion: 0.2.0\n\n"
        f"project:\n  name: {root.name}\n  id: {service_id}\n"
        f"  description: ''\n  owner: Security Lead\n"
        f"  attributes:\n    stacks: {stacks}\n\n"
        f"representations:\n  - name: Architecture Diagram\n    id: arch-diagram\n    type: diagram\n\n"
        f"assets: []\n\n"
        f"components:\n" + "\n\n".join(components) + "\n\n"
        f"trustZones:\n"
        f"  - name: Internet\n    id: internet\n    description: Public internet — untrusted\n"
        f"    risk:\n      trustRating: 0\n\n"
        f"  - name: Private\n    id: private\n    description: Internal network — restricted access\n"
        f"    risk:\n      trustRating: 75\n\n"
        f"  - name: Data\n    id: data\n    description: Persistent storage layer\n"
        f"    risk:\n      trustRating: 80\n\n"
        f"dataflows: []\n\nthreats: []\n\nmitigations: []\n",
        encoding="utf-8",
    )
    console.print(f"[green]✓[/green] Created [dim]designs/TMD/{tmd_file.name}[/dim] — add components, dataflows, and threats")


def _run_fix(console: Console) -> None:
    """Install all missing tools using the fix hints from startup checks."""
    import subprocess
    from code_crew.startup import run_checks

    summary = run_checks()
    failed = [c for c in summary.checks if not c.ok and c.fix]

    _RUNNABLE = ("brew install", "pip install", "go install", "npm install", "npm i")
    to_run = [(c.name, c.fix.split("#")[0].strip()) for c in failed
              if any(c.fix.startswith(p) for p in _RUNNABLE)]

    if not to_run:
        console.print("[dim]Nothing to fix — all tools present.[/dim]")
        return

    console.print(f"[bold]Installing {len(to_run)} missing tool(s)...[/bold]")
    for name, cmd in to_run:
        console.print(f"\n[dim]→ {cmd}[/dim]")
        result = subprocess.run(cmd.split())
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
    """Show Q&A log from agent human-input calls; optionally export to .code-crew/decisions/."""
    import time as _time

    with state.lock:
        flows = list(state.active.values())

    log: list[dict] = []
    for flow, _ in flows:
        if not key or flow.state.jira_key == key:
            log.extend(flow.relay.log)

    if not log:
        console.print("[dim]No agent questions recorded this session.[/dim]")
        return

    console.print(f"\n[bold]Agent questions & answers ({len(log)})[/bold]")
    for i, entry in enumerate(log, 1):
        ts = _time.strftime("%H:%M", _time.localtime(entry["timestamp"]))
        console.print(f"\n  [dim]{i}. {entry['jira_key']}  {ts}[/dim]")
        console.print(f"  [cyan]Q:[/cyan] {entry['question']}")
        console.print(f"  [green]A:[/green] {entry['answer']}")

    # Offer to export
    console.print(
        f"\n[dim]Export to [bold].code-crew/decisions/{(key or 'session').lower()}.md[/bold]? [y/N][/dim] ",
        end="",
    )
    answer = input().strip().lower()
    if answer in ("y", "yes"):
        _export_context(key or "session", log, console)


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
