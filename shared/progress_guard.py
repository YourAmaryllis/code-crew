"""
ProgressGuard — CrewAI step_callback that detects stuck agent loops.

Plugged in as Crew(step_callback=ProgressGuard()) so it fires after every
agent tool call. Raises NoProgressError when the agent is looping without
advancing, which flow.py catches and immediately escalates to the human.

Two heuristics (both configurable via env vars):

  CONSECUTIVE_REPEAT_LIMIT (default 3)
    Same (tool + input fingerprint) called this many times in a row.
    Almost always a bug or a hallucination loop.

  NO_PROGRESS_LIMIT (default 10)
    Sliding window of this size where ≤ 3 unique tool calls appear.
    Catches slow drift loops where the agent alternates between 2-3 tools
    without writing any output.
"""

from __future__ import annotations

import os
from collections import deque


class NoProgressError(Exception):
    """Raised by ProgressGuard when the agent appears stuck."""

    def __init__(self, reason: str, recent_calls: list[str]) -> None:
        super().__init__(reason)
        self.reason = reason
        self.recent_calls = recent_calls


class ProgressGuard:
    """
    step_callback for CrewAI agents.

    Each Crew run should get its own instance so counts reset per task.
    """

    def __init__(self) -> None:
        self._window = int(os.environ.get("NO_PROGRESS_LIMIT", "10"))
        self._consec_limit = int(os.environ.get("CONSECUTIVE_REPEAT_LIMIT", "3"))
        self._unique_threshold = 3   # ≤ this many unique calls in window = stuck

        self._calls: deque[str] = deque(maxlen=self._window)
        self._last = ""
        self._consecutive = 0

    def __call__(self, step: object) -> None:
        # Import here to avoid circular import at module load time
        try:
            from crewai.agents.parser import AgentAction
        except ImportError:
            return

        if not isinstance(step, AgentAction):
            return  # AgentFinish — task completed normally

        fp = f"{step.tool}:{step.tool_input[:120]}"
        self._calls.append(fp)

        # 1. Consecutive repeat
        if fp == self._last:
            self._consecutive += 1
        else:
            self._consecutive = 1
            self._last = fp

        if self._consecutive >= self._consec_limit:
            raise NoProgressError(
                f"called `{step.tool}` {self._consecutive} times in a row "
                f"with identical input — no progress",
                list(self._calls),
            )

        # 2. Window diversity
        if len(self._calls) == self._window:
            unique = len(set(self._calls))
            if unique <= self._unique_threshold:
                tools = ", ".join(sorted({c.split(":")[0] for c in self._calls}))
                raise NoProgressError(
                    f"only {unique} unique tool calls in last {self._window} steps "
                    f"(cycling: {tools}) — no progress",
                    list(self._calls),
                )
