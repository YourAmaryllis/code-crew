"""
Session logger — when logging.verbose is true, records all user input and
agent I/O to a timestamped log file.

Configured via ~/.code-crew/config.yaml:

  logging:
    verbose: true
    log_file: /path/to/session.log   # optional; defaults to ~/.code-crew/session-YYYY-MM-DD.log

Or via env vars: LOG_VERBOSE=true, LOG_FILE=/path/to/file.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path


class SessionLogger:
    """Thread-safe singleton logger for verbose session recording."""

    _instance: "SessionLogger | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._file = None
        self._verbose = False
        self._write_lock = threading.Lock()
        self._log_path: str = ""

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get(cls) -> "SessionLogger":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """Read config from env and open the log file if verbose is enabled."""
        verbose_env = os.environ.get("LOG_VERBOSE", "").strip().lower()
        self._verbose = verbose_env in ("true", "1", "yes", "verbose")
        if not self._verbose:
            return

        log_file = os.environ.get("LOG_FILE", "").strip()
        if not log_file:
            today = datetime.now().strftime("%Y-%m-%d")
            log_dir = Path.home() / ".code-crew"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = str(log_dir / f"session-{today}.log")

        path = Path(log_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._log_path = str(path)
        # line-buffered so every write is immediately visible on disk
        self._file = open(path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        self._write("=" * 72)
        self._write(
            f"SESSION START  {datetime.now().isoformat(timespec='seconds')}  "
            f"pid={os.getpid()}"
        )
        self._write("=" * 72)

    @property
    def enabled(self) -> bool:
        return self._verbose and self._file is not None

    @property
    def log_path(self) -> str:
        return self._log_path

    # ------------------------------------------------------------------
    # Internal write helpers
    # ------------------------------------------------------------------

    def _write(self, text: str) -> None:
        if self._file is None:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        with self._write_lock:
            try:
                self._file.write(f"[{ts}] {text}\n")
            except Exception:
                pass

    def _block(self, header: str, body: str, max_body: int = 50_000) -> None:
        """Write a header line followed by a body block."""
        if self._file is None:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        truncated = len(body) > max_body
        body_out = body[:max_body] + ("\n… [truncated]" if truncated else "")
        with self._write_lock:
            try:
                self._file.write(
                    f"[{ts}] {header}\n"
                    f"{body_out}\n"
                    f"{'─' * 60}\n"
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public logging methods
    # ------------------------------------------------------------------

    def log_user_input(self, line: str) -> None:
        if not self.enabled:
            return
        self._write(f"USER  ❯  {line}")

    def log_task_start(
        self,
        task_name: str,
        agent: str,
        jira_key: str = "",
        context: str = "",
    ) -> None:
        if not self.enabled:
            return
        tag = f"[{jira_key}] " if jira_key else ""
        self._write(f"TASK START  {tag}{task_name}  agent={agent}")
        if context:
            self._block(f"TASK INPUT  {tag}{task_name}", context)

    def log_task_output(
        self,
        task_name: str,
        output: str,
        jira_key: str = "",
        tokens: int = 0,
    ) -> None:
        if not self.enabled:
            return
        tag = f"[{jira_key}] " if jira_key else ""
        tok_str = f"  tokens={tokens}" if tokens else ""
        self._block(f"TASK OUTPUT  {tag}{task_name}{tok_str}", output)

    def log_tool_call(self, tool_name: str, args: object) -> None:
        if not self.enabled:
            return
        self._write(f"TOOL CALL   {tool_name}  args={str(args)[:300]}")

    def log_tool_result(self, tool_name: str, output: str) -> None:
        if not self.enabled:
            return
        self._block(f"TOOL RESULT {tool_name}", output, max_body=10_000)

    def log_event(self, category: str, message: str) -> None:
        if not self.enabled:
            return
        self._write(f"{category.upper():<12} {message}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        if self._file:
            self._write("SESSION END")
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None
