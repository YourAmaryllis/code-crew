"""
Terminal UI for code-crew runs.

Prints one line per meaningful state transition (task start, task complete,
gate failure, needs-help). This model works correctly with prompt_toolkit's
PromptSession — output scrolls above the fixed input bar with no cursor fighting.

The status table (rendered on /status) is built on demand from current state.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import TYPE_CHECKING

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText
from rich.console import Console
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from code_crew.flow import TicketState

# Column widths for the inline status lines
_KEY_W  = 12
_TASK_W = 26
_AGT_W  = 18

# Bold color per agent role — makes it immediately obvious who is working
_AGENT_COLOR: dict[str, str] = {
    "scrum-master":      "ansiyellow bold",
    "tech-lead":         "ansicyan bold",
    "backend-dev":       "ansiblue bold",
    "frontend-dev":      "ansimagenta bold",
    "qa-engineer":       "ansigreen bold",
    "security-reviewer": "ansired bold",
}


class SprintUI:
    """
    Thread-safe status printer.  Flow threads call update(); the REPL calls
    render_status_table() for /status and toggle_details() for /details.
    """

    def __init__(self, console: Console | None = None) -> None:
        if console is None:
            from shared.pt_console import PTConsole
            console = PTConsole(force_terminal=True, highlight=False)
        self._console = console
        self._lock = threading.Lock()
        self._rows: dict[str, _Row] = {}
        self._details: dict[str, list[str]] = defaultdict(list)
        self._expanded: set[str] = set()

    # ------------------------------------------------------------------
    # Called by flow threads
    # ------------------------------------------------------------------

    def update(self, state: "TicketState") -> None:
        """Print a status line whenever a meaningful transition occurs."""
        with self._lock:
            row = self._rows.setdefault(state.jira_key, _Row(state.jira_key))
            prev_task   = row.task
            prev_status = row.status

            row.task            = state.current_task
            row.agent           = state.current_agent
            row.status          = state.status
            row.elapsed         = state.elapsed_seconds
            row.needs_help_gate = state.needs_help_gate
            row.updated_at      = time.monotonic()

            # Decide whether to emit a line
            task_changed   = state.current_task  and state.current_task  != prev_task
            status_changed = state.status        and state.status        != prev_status
            emit = task_changed or status_changed

        if emit:
            self._print_line(state)

    def show_summary(self, ticket_key: str, task_name: str, summary: str) -> None:
        """Print one dim line explaining what a task decided / why we're moving on."""
        if not summary:
            return
        if summary.startswith("↩"):
            _pt_print([("ansiyellow", f"    {summary}")])
        else:
            _pt_print([("dim", f"    {summary}")])

    def append_detail(self, ticket_key: str, task_name: str, output: str) -> None:
        with self._lock:
            self._details[ticket_key].append(f"{task_name}:\n{output}")

    # ------------------------------------------------------------------
    # Called by REPL
    # ------------------------------------------------------------------

    def toggle_details(self, ticket_key: str) -> None:
        with self._lock:
            if ticket_key in self._expanded:
                self._expanded.discard(ticket_key)
                return
            self._expanded.add(ticket_key)
            lines = self._details.get(ticket_key, [])

        if lines:
            self._console.print(f"\n[bold]{ticket_key} — task detail[/bold]")
            for entry in lines[-5:]:
                self._console.print(entry, style="dim")
        else:
            self._console.print(f"[dim]{ticket_key}: no task output captured yet.[/dim]")

    def render_status_table(self) -> Table:
        """Return a Rich Table of all current ticket states (for /status)."""
        table = Table(show_header=True, header_style="bold dim", box=None, padding=(0, 1))
        table.add_column("Ticket",  width=_KEY_W,  style="cyan")
        table.add_column("Task",    width=_TASK_W)
        table.add_column("Agent",   width=_AGT_W,  style="dim")
        table.add_column("Status",  width=12)
        table.add_column("Elapsed", width=8, style="dim")

        with self._lock:
            rows = list(self._rows.values())

        for row in rows:
            icon, style = _status_display(row.status)
            table.add_row(
                row.ticket_key,
                row.task or "—",
                row.agent or "",
                Text(f"{icon} {row.status}", style=style),
                _fmt_elapsed(row.elapsed),
            )
        return table

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _print_line(self, state: "TicketState") -> None:
        icon, _ = _status_display(state.status)
        key     = state.jira_key.ljust(_KEY_W)
        task    = (state.current_task or "").replace("_", " ").ljust(_TASK_W)
        agent   = (state.current_agent or "").upper()
        astyle  = _AGENT_COLOR.get(state.current_agent or "", "bold")
        elapsed = _fmt_elapsed(state.elapsed_seconds).rjust(6)

        if state.status == "needs_help":
            _pt_print([
                (astyle,          f"  ⚠  {agent.ljust(_AGT_W)}"),
                ("dim",           f"  {key}"),
                ("ansiyellow",    f"  {state.needs_help_gate} exhausted retries — type /help <guidance>"),
            ])
        elif state.status == "passed":
            _pt_print([
                (astyle,          f"  ✓  {agent.ljust(_AGT_W)}"),
                ("dim",           f"  {key}"),
                ("",              f"  {task}"),
                ("ansigreen",     f"  {elapsed}"),
            ])
        elif state.status == "failed":
            _pt_print([
                (astyle,          f"  ✗  {agent.ljust(_AGT_W)}"),
                ("dim",           f"  {key}"),
                ("",              f"  {task}"),
                ("ansired",       "  failed"),
            ])
        else:
            # running — role first, bold + color-coded so it's immediately obvious who is working
            _pt_print([
                (astyle,          f"  ►  {agent.ljust(_AGT_W)}"),
                ("dim",           f"  {key}"),
                ("",              f"  {task}"),
            ])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Row:
    def __init__(self, key: str) -> None:
        self.ticket_key     = key
        self.task           = ""
        self.agent          = ""
        self.status         = "running"
        self.elapsed        = 0.0
        self.needs_help_gate = ""
        self.updated_at     = time.monotonic()


def _status_display(status: str) -> tuple[str, str]:
    return {
        "running":    ("►", "green"),
        "needs_help": ("⚠", "bold yellow"),
        "passed":     ("✓", "bold green"),
        "failed":     ("✗", "bold red"),
    }.get(status, ("?", "dim"))


def _fmt_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    return f"{int(seconds // 60)}m{int(seconds % 60)}s"


def _pt_print(fragments: list[tuple[str, str]]) -> None:
    """Thread-safe print via prompt_toolkit (safe inside patch_stdout context)."""
    try:
        print_formatted_text(FormattedText(fragments))
    except Exception:
        # Fallback if called outside a prompt_toolkit context
        print("".join(text for _, text in fragments))
