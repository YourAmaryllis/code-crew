"""
TicketFlow: drives a single ticket through the SDLC task sequence with
retry loops on review gates and human-escalation when retries are exhausted.

Flow sequence:
  sprint_planning → architecture_review → scaffold_code → scaffold_test
  → bdd_authoring → [implementation loop] → done

Implementation loop (retried up to max_retries times per gate):
  backend_implementation + frontend_implementation
  → code_review        (fail → retry impl)
  → security_review    (fail → retry impl)
  → dod_check          (fail → retry impl)
  → DONE

On exhausted retries the flow pauses and waits for human feedback via
inject_feedback(). The REPL calls this method from the main thread.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Literal


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class TicketState:
    jira_key: str
    sprint_name: str = ""
    code_path: str = ""          # worktree path; empty = cwd
    max_retries: int = 3

    # Task outputs keyed by task name
    task_outputs: dict[str, str] = field(default_factory=dict)

    # Feedback from the most recent failed review
    review_feedback: str = ""
    # Human-injected guidance after retries exhausted
    human_feedback: str = ""

    # Per-gate retry counts
    code_review_retries: int = 0
    sec_review_retries: int = 0
    dod_retries: int = 0

    # Current position
    current_task: str = ""
    current_agent: str = ""
    elapsed_seconds: float = 0.0

    # Overall status
    status: Literal["running", "needs_help", "passed", "failed"] = "running"
    needs_help_gate: str = ""    # which gate triggered the escalation


@dataclass
class ReviewResult:
    passed: bool
    feedback: str = ""

    @classmethod
    def from_output(cls, output: str) -> "ReviewResult":
        """Parse APPROVED / REJECTED from task output."""
        upper = output.upper()
        passed = (
            "APPROVED" in upper
            or "PASSED" in upper
            or "LGTM" in upper
            or ("REVIEW" in upper and "FAILED" not in upper and "REJECTED" not in upper)
        )
        return cls(passed=passed, feedback=output if not passed else "")


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------

# Callback type: (state: TicketState) -> None  — called on status changes
StatusCallback = Callable[[TicketState], None]
# Callback type: (jira_key, task_name, summary) -> None  — called after each task
SummaryCallback = Callable[[str, str, str], None]


class TicketFlow:
    """
    Drives a single Jira/Linear ticket through the full SDLC task sequence.

    Thread-safe: run() blocks the calling thread. inject_feedback() may be
    called from a different thread while the flow is paused at needs_help.
    """

    def __init__(
        self,
        state: TicketState,
        on_status: StatusCallback | None = None,
        on_task_complete: SummaryCallback | None = None,
    ) -> None:
        self.state = state
        self._on_status = on_status or (lambda _: None)
        self._on_task_complete = on_task_complete or (lambda *_: None)
        self._feedback_event = threading.Event()
        self._task_start: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> TicketState:
        """Execute the full flow. Blocks until done, failed, or human gives up."""
        try:
            self._linear_phase()
            self._implementation_loop()
            self.state.status = "passed"
        except _FlowFailed as exc:
            self.state.status = "failed"
            self.state.current_task = f"FAILED: {exc}"
        self._emit()
        return self.state

    def inject_feedback(self, feedback: str) -> None:
        """Called by the REPL when the user provides guidance for a stuck gate."""
        self.state.human_feedback = feedback
        self.state.status = "running"
        self._feedback_event.set()

    # ------------------------------------------------------------------
    # Phases
    # ------------------------------------------------------------------

    LINEAR_TASKS = [
        "sprint_planning",
        "architecture_review",
        "scaffold_code",
        "scaffold_test",
        "bdd_authoring",
    ]

    def _linear_phase(self) -> None:
        for task_name in self.LINEAR_TASKS:
            self._run_task(task_name)

    def _implementation_loop(self) -> None:
        """
        Runs backend+frontend impl then three review gates.
        On gate failure: retry impl up to max_retries, then escalate to human.
        Human injection resets the retry counter for that gate and continues.
        """
        gates = [
            ("code_review",      "code_review_retries"),
            ("security_review",  "sec_review_retries"),
            ("dod_check",        "dod_retries"),
        ]

        # Run impl once before entering gate loop
        self._run_implementation()

        for gate_task, retry_attr in gates:
            while True:
                result = self._run_review_gate(gate_task)
                if result.passed:
                    break

                retries: int = getattr(self.state, retry_attr)
                retries += 1
                setattr(self.state, retry_attr, retries)
                self.state.review_feedback = result.feedback

                reason = _extract_summary(result.feedback, max_len=100)
                if retries > self.state.max_retries:
                    self._on_task_complete(
                        self.state.jira_key, gate_task,
                        f"↩ exhausted retries — escalating to human: {reason}",
                    )
                    self._escalate(gate_task)
                    setattr(self.state, retry_attr, 0)
                else:
                    self._on_task_complete(
                        self.state.jira_key, gate_task,
                        f"↩ REJECTED (attempt {retries}/{self.state.max_retries}) — {reason}",
                    )

                # Re-run implementation with feedback, then re-check this gate
                self._run_implementation()

    def _run_implementation(self) -> None:
        self._run_task("backend_implementation")
        self._run_task("frontend_implementation")

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def _run_task(self, task_name: str) -> str:
        """Run one task and store its output. Returns the output string."""
        self.state.current_task = task_name
        self.state.current_agent = _TASK_AGENTS.get(task_name, "")
        self._task_start = time.monotonic()
        self._emit()

        output = self._execute(task_name)

        self.state.task_outputs[task_name] = output
        self.state.elapsed_seconds = time.monotonic() - self._task_start
        self._on_task_complete(self.state.jira_key, task_name, _extract_summary(output))
        return output

    def _run_review_gate(self, task_name: str) -> ReviewResult:
        output = self._run_task(task_name)
        return ReviewResult.from_output(output)

    def _execute(self, task_name: str) -> str:
        """
        Build and run a single-task crew. Injects review feedback and human
        guidance into the task context when present.
        """
        from code_crew.crew import build_single_task_crew
        from shared.aws_auth import is_aws_auth_error

        extra_context = ""
        if self.state.review_feedback:
            extra_context += f"\n\n## Review feedback (address before proceeding)\n\n{self.state.review_feedback}"
        if self.state.human_feedback:
            extra_context += f"\n\n## Human guidance\n\n{self.state.human_feedback}"
            self.state.human_feedback = ""  # consume once

        sprint_input = _build_sprint_input(self.state, extra_context)
        crew = build_single_task_crew(task_name, sprint_input, code_path=self.state.code_path)
        try:
            result = crew.kickoff(inputs=sprint_input)
        except Exception as exc:
            if is_aws_auth_error(exc):
                aws_profile = __import__("os").environ.get("AWS_PROFILE", "")
                hint = f"aws sso login{' --profile ' + aws_profile if aws_profile else ''}"
                raise _FlowFailed(
                    f"AWS credentials expired during {task_name}. "
                    f"Run `{hint}` then re-run /jira {self.state.jira_key}."
                ) from exc
            raise
        return str(result)

    # ------------------------------------------------------------------
    # Human escalation
    # ------------------------------------------------------------------

    def _escalate(self, gate: str) -> None:
        self.state.status = "needs_help"
        self.state.needs_help_gate = gate
        self._emit()
        # Block until REPL calls inject_feedback()
        self._feedback_event.clear()
        self._feedback_event.wait()

    # ------------------------------------------------------------------

    def _emit(self) -> None:
        self._on_status(self.state)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TASK_AGENTS: dict[str, str] = {
    "sprint_planning": "scrum-master",
    "architecture_review": "tech-lead",
    "scaffold_code": "backend-dev",
    "scaffold_test": "qa-engineer",
    "bdd_authoring": "qa-engineer",
    "backend_implementation": "backend-dev",
    "frontend_implementation": "frontend-dev",
    "code_review": "tech-lead",
    "security_review": "security-reviewer",
    "dod_check": "scrum-master",
}


def _build_sprint_input(state: TicketState, extra_context: str = "") -> dict:
    """Build the sprint_input dict passed to crew tasks."""
    return {
        "jira_key": state.jira_key,
        "sprint_name": state.sprint_name,
        "review_feedback": state.review_feedback,
        "human_feedback": extra_context,
        # Remaining fields are populated by main.py before creating the flow
        "story": "",
        "acceptance_criteria": [],
        "sprint_goal": "",
        "figma_url": "",
        "html_design_ref": "",
        "add_refs": [],
        "comment_context": "",
        "user_context": "",
    }


class _FlowFailed(Exception):
    pass


def _extract_summary(output: str, max_len: int = 120) -> str:
    """Return the first meaningful line of task output, capped at max_len chars."""
    for line in output.strip().splitlines():
        line = line.strip(" #*-|")
        if line and not line.startswith("---") and not line.startswith("```"):
            return line[:max_len]
    return output.strip()[:max_len]
