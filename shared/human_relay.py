"""
HumanRelay — thread-safe bridge so flow-thread agents can ask the REPL-thread human
a specific question and block until an answer arrives.

Usage:
  Flow thread:  answer = relay.ask(jira_key, question)   # blocks
  REPL thread:  relay.answer(text)                        # unblocks flow thread

The relay also accumulates a log of all Q&A for post-run review.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class PendingQuestion:
    jira_key: str
    question: str


class HumanRelay:
    """
    One relay per TicketFlow.  Flow threads call ask(); the REPL thread polls
    pending() and calls answer().
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: PendingQuestion | None = None
        self._answer: str = ""
        self._answer_ready = threading.Event()
        self.log: list[dict] = []   # [{question, answer, timestamp}]

    # ------------------------------------------------------------------
    # Flow-thread side
    # ------------------------------------------------------------------

    def ask(self, jira_key: str, question: str) -> str:
        """Block the calling (flow) thread until the REPL provides an answer."""
        from shared.pt_console import pt_print

        with self._lock:
            self._pending = PendingQuestion(jira_key=jira_key, question=question)
            self._answer_ready.clear()

        # Print the question above the current prompt so the human sees it immediately.
        pt_print([
            ("", "\n"),
            ("ansicyan bold",  f"  ┌─ {jira_key} asks\n"),
            ("",               f"  │  {question}\n"),
            ("ansicyan",       "  └─ type your answer and press Enter\n"),
        ])

        self._answer_ready.wait()

        with self._lock:
            answer = self._answer
            self._pending = None

        self.log.append({
            "jira_key": jira_key,
            "question": question,
            "answer": answer,
            "timestamp": time.time(),
        })
        return answer

    # ------------------------------------------------------------------
    # REPL-thread side
    # ------------------------------------------------------------------

    def pending(self) -> PendingQuestion | None:
        with self._lock:
            return self._pending

    def answer(self, text: str) -> None:
        with self._lock:
            self._answer = text
        self._answer_ready.set()
