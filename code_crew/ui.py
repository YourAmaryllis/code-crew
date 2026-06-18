"""
Rich-based live display for code-crew runs.

Shows one status row per active ticket. Detail output is captured per task
and toggled with /details <ticket>. When a flow needs human input, the stuck
row is highlighted and the prompt changes.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import TYPE_CHECKING

from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from code_crew.flow import TicketState

_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class SprintUI:
    """
    Thread-safe live display. Call update() from any thread.
    The internal Live context runs on the main thread.
    """

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()
        self._lock = threading.Lock()
        self._rows: dict[str, _Row] = {}          # ticket_key → Row
        self._details: dict[str, list[str]] = defaultdict(list)  # ticket_key → task outputs
        self._expanded: set[str] = set()           # tickets with expanded detail
        self._live: Live | None = None
        self._tick = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=4,
            transient=False,
        )
        self._live.__enter__()

    def stop(self) -> None:
        if self._live:
            self._live.__exit__(None, None, None)
            self._live = None

    def __enter__(self) -> "SprintUI":
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # State updates (called from flow threads)
    # ------------------------------------------------------------------

    def update(self, state: "TicketState") -> None:
        with self._lock:
            row = self._rows.setdefault(state.jira_key, _Row(state.jira_key))
            row.task = state.current_task
            row.agent = state.current_agent
            row.status = state.status
            row.elapsed = state.elapsed_seconds
            row.needs_help_gate = state.needs_help_gate
            row.updated_at = time.monotonic()
            if state.status in ("passed", "failed"):
                row.done = True
        self._refresh()

    def append_detail(self, ticket_key: str, task_name: str, output: str) -> None:
        with self._lock:
            self._details[ticket_key].append(f"[bold]{task_name}[/bold]\n{output}")
        self._refresh()

    def toggle_details(self, ticket_key: str) -> None:
        with self._lock:
            if ticket_key in self._expanded:
                self._expanded.discard(ticket_key)
            else:
                self._expanded.add(ticket_key)
        self._refresh()

    def print_above(self, text: str) -> None:
        """Print a line above the live display (e.g. system messages)."""
        with self._lock:
            if self._live:
                self._live.console.print(text)
            else:
                self._console.print(text)

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        self._tick = (self._tick + 1) % len(_SPINNER)
        if self._live:
            self._live.update(self._render())

    def _render(self) -> Table:
        table = Table.grid(padding=(0, 1))
        table.add_column(width=12)   # ticket key
        table.add_column(width=22)   # task
        table.add_column(width=16)   # agent
        table.add_column(width=12)   # status
        table.add_column(width=8)    # elapsed

        with self._lock:
            rows = list(self._rows.values())

        for row in rows:
            key_text = Text(row.ticket_key, style="bold cyan")
            status_icon, status_style = _status_display(row.status, self._tick)
            task_text = Text(row.task or "—", style="dim" if not row.task else "")
            agent_text = Text(row.agent or "", style="dim")
            status_text = Text(f"{status_icon} {row.status}", style=status_style)
            elapsed_text = Text(_fmt_elapsed(row.elapsed), style="dim")

            table.add_row(key_text, task_text, agent_text, status_text, elapsed_text)

            if row.ticket_key in self._expanded:
                detail_lines = self._details.get(row.ticket_key, [])
                if detail_lines:
                    panel = Panel(
                        "\n\n".join(detail_lines[-3:]),  # last 3 tasks
                        title=f"{row.ticket_key} detail",
                        style="dim",
                    )
                    table.add_row("", Columns([panel], expand=True), "", "", "")

            if row.status == "needs_help":
                hint = Text(
                    f"  ↳ {row.needs_help_gate} exhausted retries — type your guidance and press Enter",
                    style="bold yellow",
                )
                table.add_row("", hint, "", "", "")

        return table


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Row:
    def __init__(self, key: str) -> None:
        self.ticket_key = key
        self.task = ""
        self.agent = ""
        self.status = "running"
        self.elapsed = 0.0
        self.needs_help_gate = ""
        self.done = False
        self.updated_at = time.monotonic()


def _status_display(status: str, tick: int) -> tuple[str, str]:
    return {
        "running":    (_SPINNER[tick], "green"),
        "needs_help": ("⚠", "bold yellow"),
        "passed":     ("✓", "bold green"),
        "failed":     ("✗", "bold red"),
    }.get(status, ("?", "dim"))


def _fmt_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    return f"{int(seconds // 60)}m{int(seconds % 60)}s"
