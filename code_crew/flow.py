"""
TicketFlow: drives a single ticket through the SDLC task sequence with
retry loops on review gates and human-escalation when retries are exhausted.

Flow sequence:
  sprint_planning → architecture_review → scaffold_code → scaffold_test
  → [BDD cycle]
      bdd_authoring
      → bdd_po_review + bdd_arch_review  (sequential, but independent reviews)
      → bdd_finalization                 (QA consolidates feedback)
      → repeat until BDD APPROVED, or human escalation after max_retries
  → [implementation loop]
      implementation + devops_coordination
      → code_review       (fail → retry impl+devops)
      → security_review   (fail → retry impl+devops)
      → compliance_review (fail → retry impl+devops)
      → dod_check         (fail → retry impl+devops)
  → release_notes        (changelog entry + version impact + GitHub Release draft)
  → [staging loop]
      promote_staging    (DevOps: push rc tag, ECS redeploy staging)
      → staging_verification (QA: BDD smoke on staging)
      → repeat if staging fails, or human escalation after max_retries
  → launch_decision      (Release Engineer: go/no-go for production promotion)
  → [human gate: production promotion via workflow_dispatch / GitLab UI]
  → smoke_test           (QA: read-only smoke on production)
  → DONE

On exhausted retries the flow pauses and waits for human feedback via
inject_feedback(). The REPL calls this method from the main thread.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal

if TYPE_CHECKING:
    from shared.human_relay import HumanRelay


# ---------------------------------------------------------------------------
# Design flow
# ---------------------------------------------------------------------------

_DESIGN_DRAFT_TASKS = [
    "design_requirements",
    "design_add_draft",
    "design_security_input",
    "design_compliance_input",
]


@dataclass
class DesignState:
    issue_key: str
    status: Literal["running", "needs_help", "passed", "failed"] = "running"
    needs_help_gate: str = ""
    session_tokens: int = 0


class DesignReviewExhausted(Exception):
    pass


class DesignFlow:
    """
    Drives a design ticket through the Chief Architect approval loop.

    Flow:
      [draft tasks: requirements → add_draft → security → compliance]
      → design_chief_review  (architect presents via ask_human; blocks for CA input)
        DESIGN APPROVED → design_finalize (commit + push + PR + merge + update ticket)
        DESIGN NEEDS REVISION → re-run draft tasks with feedback, loop
      escalates after max_retries unapproved rounds
    """

    def __init__(
        self,
        design_input: dict,
        on_task_complete: "SummaryCallback | None" = None,
        max_retries: int = 3,
    ) -> None:
        from shared.human_relay import HumanRelay

        self.design_input = design_input
        self._on_task_complete = on_task_complete or (lambda *_: None)
        self.max_retries = max_retries
        self.task_outputs: dict[str, str] = {}
        self.chief_feedback: str = ""
        self.revision_count: int = 0
        self.relay: "HumanRelay" = HumanRelay()
        self.state = DesignState(issue_key=design_input.get("issue_key", ""))

    def run(self) -> None:
        try:
            while True:
                self._run_drafting()
                if self._run_chief_review():
                    break
                self.revision_count += 1
                if self.revision_count > self.max_retries:
                    raise DesignReviewExhausted(
                        f"Chief Architect provided {self.revision_count} rounds of "
                        "feedback without approving. /abort and clarify the requirement."
                    )
                for t in _DESIGN_DRAFT_TASKS:
                    self.task_outputs.pop(t, None)
                self.task_outputs.pop("design_chief_review", None)
            self._run_finalize()
            self.state.status = "passed"
        except DesignReviewExhausted:
            self.state.status = "failed"
            raise
        except Exception:
            self.state.status = "failed"
            raise

    # ------------------------------------------------------------------

    def _run_drafting(self) -> None:
        for task_name in _DESIGN_DRAFT_TASKS:
            if task_name in self.task_outputs:
                continue
            output = self._execute(task_name)
            self.task_outputs[task_name] = output
            self._on_task_complete(
                self.state.issue_key, task_name, _extract_summary(output)
            )

    def _run_chief_review(self) -> bool:
        output = self._execute("design_chief_review")
        self.task_outputs["design_chief_review"] = output
        self._on_task_complete(
            self.state.issue_key, "design_chief_review", _extract_summary(output)
        )
        if "DESIGN APPROVED" in output.upper():
            return True
        # Extract Chief Architect feedback for next iteration
        idx = output.upper().find("DESIGN NEEDS REVISION:")
        self.chief_feedback = (
            output[idx + len("DESIGN NEEDS REVISION:"):].strip()
            if idx >= 0
            else output.strip()
        )
        return False

    def _run_finalize(self) -> None:
        output = self._execute("design_finalize")
        self.task_outputs["design_finalize"] = output
        self._on_task_complete(
            self.state.issue_key, "design_finalize", _extract_summary(output)
        )

    def _execute(self, task_name: str) -> str:
        from code_crew.crew import build_design_single_task

        extra = ""
        # Inject outputs of previously completed tasks as context
        for prev_task, prev_output in self.task_outputs.items():
            if prev_output:
                label = prev_task.replace("design_", "").replace("_", " ").title()
                extra += f"\n\n## Previous: {label}\n\n{prev_output[:2000]}"
        # Inject Chief Architect feedback for revision rounds
        if self.chief_feedback and task_name in _DESIGN_DRAFT_TASKS:
            extra += (
                "\n\n## Chief Architect Feedback — address in this revision\n\n"
                + self.chief_feedback
            )

        return build_design_single_task(
            task_name, self.design_input, relay=self.relay, extra_context=extra
        )


# ---------------------------------------------------------------------------
# Domain modeling flow
# ---------------------------------------------------------------------------


@dataclass
class DomainState:
    system_name: str
    issue_key: str = ""
    status: Literal["running", "needs_help", "passed", "failed"] = "running"
    session_tokens: int = 0


class DomainFlowExhausted(Exception):
    pass


class DomainFlow:
    """
    Drives a domain modeling session through three phases:
      Phase 1 — Flow Discovery (once): identify named business flows
      Phase 2 — Per-flow Event Storming (once per flow): full event board per flow
      Phase 3 — Synthesis (once): bounded contexts, aggregates, glossary, Mermaid diagram

    Each phase is a single crew run that blocks for SME input via ask_human/HumanRelay.
    Prior phase outputs are injected as context for subsequent phases.
    """

    def __init__(
        self,
        domain_input: dict,
        on_task_complete: "SummaryCallback | None" = None,
    ) -> None:
        from shared.human_relay import HumanRelay

        self.domain_input = domain_input
        self._on_task_complete = on_task_complete or (lambda *_: None)
        self.task_outputs: dict[str, str] = {}
        self.relay: "HumanRelay" = HumanRelay()
        self.state = DomainState(
            system_name=domain_input.get("system_name", "unknown"),
            issue_key=domain_input.get("issue_key", ""),
        )

    def run(self) -> None:
        try:
            discovery_out = self._execute("domain_flow_discovery")
            self.task_outputs["domain_flow_discovery"] = discovery_out
            self._on_task_complete(self.state.issue_key, "domain_flow_discovery", _extract_summary(discovery_out))

            flows = self._parse_flows(discovery_out)
            for flow_name in flows:
                task_key = f"domain_event_storming_{flow_name.lower().replace(' ', '_')}"
                out = self._execute("domain_event_storming", flow_name=flow_name)
                self.task_outputs[task_key] = out
                self._on_task_complete(self.state.issue_key, f"event_storming:{flow_name}", _extract_summary(out))

            synthesis_out = self._execute("domain_synthesis")
            self.task_outputs["domain_synthesis"] = synthesis_out
            self._on_task_complete(self.state.issue_key, "domain_synthesis", _extract_summary(synthesis_out))

            self.state.status = "passed"
        except Exception:
            self.state.status = "failed"
            raise

    def _execute(self, task_name: str, flow_name: str = "") -> str:
        from code_crew.crew import build_domain_single_task

        extra = ""
        for prev_task, prev_output in self.task_outputs.items():
            if prev_output:
                label = prev_task.replace("domain_", "").replace("_", " ").title()
                extra += f"\n\n## Previous: {label}\n\n{prev_output[:3000]}"
        if flow_name:
            extra += f"\n\n## Current flow to storm: {flow_name}"

        inp = {**self.domain_input}
        if flow_name:
            inp["current_flow"] = flow_name
        return build_domain_single_task(task_name, inp, relay=self.relay, extra_context=extra)

    @staticmethod
    def _parse_flows(discovery_out: str) -> list[str]:
        """Extract ordered flow names from FLOWS IDENTIFIED: block."""
        import re
        flows: list[str] = []
        in_block = False
        for line in discovery_out.splitlines():
            if "FLOWS IDENTIFIED:" in line.upper():
                in_block = True
                continue
            if not in_block:
                continue
            m = re.match(r"^\s*\d+\.\s+(.+?)\s+—", line)
            if m:
                flows.append(m.group(1).strip())
            elif line.strip() and not line.strip().startswith("#"):
                break
        return flows


# ---------------------------------------------------------------------------
# UX flow
# ---------------------------------------------------------------------------

_UX_IMPL_TASKS = ["ux_implementation"]


class UxFlow:
    """
    Drives a UX ticket through spec extraction → implementation → review loop.

    Flow:
      ux_spec  (UX Lead: fetch Figma frame + tokens, write spec.md + tokens.json)
      → [loop]
          ux_implementation (Engineer: generate component from spec)
          → ux_review (UX Lead: verify spec match + WCAG 2.1 AA)
          APPROVED → done
          REVISION NEEDED → re-run ux_implementation with feedback
      escalates after max_retries failed reviews
    """

    def __init__(
        self,
        ux_input: dict,
        on_task_complete: "SummaryCallback | None" = None,
        max_retries: int = 3,
    ) -> None:
        from shared.human_relay import HumanRelay

        self.ux_input = ux_input
        self._on_task_complete = on_task_complete or (lambda *_: None)
        self.max_retries = max_retries
        self.task_outputs: dict[str, str] = {}
        self.review_feedback: str = ""
        self.relay: "HumanRelay" = HumanRelay()
        self.state = DesignState(issue_key=ux_input.get("issue_key", ""))

    def run(self) -> None:
        try:
            self._run_spec()
            for attempt in range(self.max_retries + 1):
                self._run_implementation()
                if self._run_review():
                    break
                if attempt >= self.max_retries:
                    raise DesignReviewExhausted(
                        f"UX review did not approve after {self.max_retries + 1} attempts. "
                        "Check the UX review output for required changes."
                    )
                self.task_outputs.pop("ux_implementation", None)
                self.task_outputs.pop("ux_review", None)
            self.state.status = "passed"
        except DesignReviewExhausted:
            self.state.status = "failed"
            raise
        except Exception:
            self.state.status = "failed"
            raise

    def _run_spec(self) -> None:
        output = self._execute("ux_spec")
        self.task_outputs["ux_spec"] = output
        self._on_task_complete(self.state.issue_key, "ux_spec", _extract_summary(output))

    def _run_implementation(self) -> None:
        output = self._execute("ux_implementation")
        self.task_outputs["ux_implementation"] = output
        self._on_task_complete(
            self.state.issue_key, "ux_implementation", _extract_summary(output)
        )

    def _run_review(self) -> bool:
        output = self._execute("ux_review")
        self.task_outputs["ux_review"] = output
        self._on_task_complete(self.state.issue_key, "ux_review", _extract_summary(output))
        if "REVISION NEEDED" in output.upper():
            idx = output.upper().find("REVISION NEEDED:")
            self.review_feedback = (
                output[idx + len("REVISION NEEDED:"):].strip() if idx >= 0 else output.strip()
            )
            return False
        return True

    def _execute(self, task_name: str) -> str:
        from code_crew.crew import build_ux_single_task

        extra = ""
        for prev_task, prev_output in self.task_outputs.items():
            if prev_output:
                label = prev_task.replace("ux_", "").replace("_", " ").title()
                extra += f"\n\n## Previous: {label}\n\n{prev_output[:2000]}"
        if self.review_feedback and task_name in _UX_IMPL_TASKS:
            extra += (
                "\n\n## UX Review Feedback — address in this revision\n\n"
                + self.review_feedback
            )
        return build_ux_single_task(task_name, self.ux_input, relay=self.relay, extra_context=extra)


# ---------------------------------------------------------------------------
# Ticket flow state
# ---------------------------------------------------------------------------

@dataclass
class TicketState:
    jira_key: str
    sprint_name: str = ""
    code_path: str = ""          # worktree path; empty = cwd
    max_retries: int = 3

    # Task outputs keyed by task name
    task_outputs: dict[str, str] = field(default_factory=dict)

    # Feedback from the most recent failed review gate
    review_feedback: str = ""
    # Aggregated PO + Architect BDD review feedback (injected into bdd_finalization)
    bdd_feedback: str = ""
    # Human-injected guidance after retries exhausted
    human_feedback: str = ""

    # Per-gate retry counts
    bdd_review_retries: int = 0
    code_review_retries: int = 0
    sec_review_retries: int = 0
    compliance_retries: int = 0
    dod_retries: int = 0
    staging_retries: int = 0

    # Token usage (accumulated across all tasks in this flow)
    session_tokens: int = 0
    last_task_tokens: int = 0

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
            or "COMPLIANT" in upper
            or "PASSED" in upper
            or "LGTM" in upper
            or "TASK COMPLETE" in upper
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
        from shared.human_relay import HumanRelay

        self.state = state
        self._on_status = on_status or (lambda _: None)
        self._on_task_complete = on_task_complete or (lambda *_: None)
        self._feedback_event = threading.Event()
        self._task_start: float = 0.0
        self.relay: HumanRelay = HumanRelay()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> TicketState:
        """Execute the full flow. Blocks until done, failed, or human gives up."""
        try:
            self._linear_phase()
            self._bdd_cycle()
            self._implementation_loop()
            self._run_task("release_notes")
            self._staging_loop()
            self._production_gate()
            self._run_task("smoke_test")
            self.state.status = "passed"
            _delete_checkpoint(self.state.jira_key)
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
    ]

    def _linear_phase(self) -> None:
        for task_name in self.LINEAR_TASKS:
            self._run_task(task_name)
            if task_name == "architecture_review":
                self._check_arch_consultation()

    def _check_arch_consultation(self) -> None:
        """
        If architecture_review outputs CHIEF_ARCHITECT_CONSULTATION_REQUIRED,
        pause for Chief Architect input, clear the output, and re-run the review.
        Loops until the architect produces a non-consultation output.
        """
        while True:
            output = self.state.task_outputs.get("architecture_review", "")
            if "CHIEF_ARCHITECT_CONSULTATION_REQUIRED" not in output.upper():
                break
            self._on_task_complete(
                self.state.jira_key, "architecture_review",
                "⏸ Novel decision — Chief Architect input required.",
            )
            self.state.task_outputs.pop("architecture_review", None)
            _save_checkpoint(self.state)
            self._escalate("chief_architect_consultation")
            # Re-run with Chief Architect's guidance in human_feedback
            self._run_task("architecture_review")

    def _bdd_cycle(self) -> None:
        """
        BDD authoring → PO review + Architect review → QA finalization.
        Loops until finalization outputs BDD APPROVED, or escalates to human
        after max_retries failed iterations.
        """
        self._run_task("bdd_authoring")

        while True:
            po_out   = self._run_task("bdd_po_review")
            arch_out = self._run_task("bdd_arch_review")

            # Make combined feedback available to bdd_finalization via _execute
            self.state.bdd_feedback = (
                f"## Product Owner Feedback\n\n{po_out}"
                f"\n\n## Architect Feedback\n\n{arch_out}"
            )
            final_out = self._run_task("bdd_finalization")

            if ReviewResult.from_output(final_out).passed:
                break

            self.state.bdd_review_retries += 1
            reason = _extract_summary(final_out, max_lines=4, max_len=100)

            if self.state.bdd_review_retries > self.state.max_retries:
                self._on_task_complete(
                    self.state.jira_key, "bdd_finalization",
                    f"↩ BDD review exhausted retries — escalating: {reason}",
                )
                self._escalate("bdd_review")
                self.state.bdd_review_retries = 0
            else:
                self._on_task_complete(
                    self.state.jira_key, "bdd_finalization",
                    f"↩ BDD needs revision "
                    f"(attempt {self.state.bdd_review_retries}/{self.state.max_retries})"
                    f" — {reason}",
                )

            # Clear review task outputs so they re-run with updated .feature files
            for t in ("bdd_po_review", "bdd_arch_review", "bdd_finalization"):
                self.state.task_outputs.pop(t, None)
            _save_checkpoint(self.state)

    def _implementation_loop(self) -> None:
        """
        Runs implementation + devops_coordination then three review gates.
        On gate failure: retry impl+devops up to max_retries, then escalate to human.
        """
        gates = [
            ("code_review",       "code_review_retries"),
            ("security_review",   "sec_review_retries"),
            ("compliance_review", "compliance_retries"),
            ("dod_check",         "dod_retries"),
        ]

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

                self._run_implementation()

    def _staging_loop(self) -> None:
        """
        Promote to staging → run BDD smoke → loop if smoke fails.
        Escalates to human after max_retries, then re-promotes.
        """
        while True:
            self._run_task("promote_staging")
            verif_out = self._run_task("staging_verification")

            upper = verif_out.upper()
            if "STAGING VERIFIED" in upper:
                break

            self.state.staging_retries += 1
            reason = _extract_summary(verif_out, max_lines=4, max_len=100)

            if self.state.staging_retries > self.state.max_retries:
                self._on_task_complete(
                    self.state.jira_key, "staging_verification",
                    f"↩ staging smoke exhausted retries — escalating: {reason}",
                )
                self._escalate("staging_verification")
                self.state.staging_retries = 0
            else:
                self._on_task_complete(
                    self.state.jira_key, "staging_verification",
                    f"↩ staging smoke failed "
                    f"(attempt {self.state.staging_retries}/{self.state.max_retries})"
                    f" — {reason}",
                )

            for t in ("promote_staging", "staging_verification"):
                self.state.task_outputs.pop(t, None)
            _save_checkpoint(self.state)

    def _production_gate(self) -> None:
        """
        Run launch_decision, then pause for a human to trigger production promotion.
        Resumes when inject_feedback() is called.
        """
        result = self._run_task("launch_decision")
        if "LAUNCH BLOCKED" in result.upper():
            reason = _extract_summary(result, max_lines=4, max_len=120)
            self._on_task_complete(
                self.state.jira_key, "launch_decision",
                f"⛔ {reason}",
            )
            self._escalate("launch_decision")
            return

        self.state.status = "needs_help"
        self.state.needs_help_gate = "production_promotion"
        self._on_task_complete(
            self.state.jira_key, "launch_decision",
            "⏸ LAUNCH APPROVED. Trigger production promotion via workflow_dispatch "
            "(GHA) or manual pipeline job (GitLab), then resume with /feedback.",
        )
        self._emit()
        self._feedback_event.clear()
        self._feedback_event.wait()

    def _run_implementation(self) -> None:
        impl_out = self._run_task("implementation")
        if not _is_impl_done(impl_out):
            reason = _extract_summary(impl_out)
            self.state.task_outputs["implementation"] = (
                f"INCOMPLETE: implementation did not confirm completion — {reason}"
            )
            self._on_task_complete(
                self.state.jira_key, "implementation",
                f"↩ no IMPLEMENTATION COMPLETE — treating as incomplete: {reason[:80]}",
            )
            return
        self._run_task("devops_coordination")

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def _run_task(self, task_name: str) -> str:
        """Run one task and store its output. Returns the output string."""
        # Resume from checkpoint: skip LLM call, replay cached output
        if task_name in self.state.task_outputs:
            self.state.current_task = task_name
            self.state.current_agent = _TASK_AGENTS.get(task_name, "")
            self.state.elapsed_seconds = 0.0
            self._on_task_complete(self.state.jira_key, task_name, "[checkpoint]")
            return self.state.task_outputs[task_name]

        self.state.current_task = task_name
        self.state.current_agent = _TASK_AGENTS.get(task_name, "")
        self._task_start = time.monotonic()
        self._emit()

        output = self._execute(task_name)

        # Agent stuck mid-task — escalate immediately so human can add context.
        if output.startswith("STUCK:"):
            reason = output[6:].strip()
            self._on_task_complete(
                self.state.jira_key, task_name,
                f"↩ stuck — escalating: {reason[:80]}",
            )
            self._escalate(task_name)
            output = self._execute(task_name)

        self.state.task_outputs[task_name] = output
        _save_checkpoint(self.state)
        self.state.elapsed_seconds = time.monotonic() - self._task_start
        summary = _extract_summary(output)
        if self.state.last_task_tokens:
            summary = f"{summary}  [{_fmt_k(self.state.last_task_tokens)}]"
        self._on_task_complete(self.state.jira_key, task_name, summary)
        return output

    def _run_review_gate(self, task_name: str) -> ReviewResult:
        output = self._run_task(task_name)
        return ReviewResult.from_output(output)

    def _execute(self, task_name: str) -> str:
        """
        Build and run a single-task crew. Injects review feedback, BDD feedback,
        and human guidance into the task context when present.
        """
        from code_crew.crew import build_single_task_crew
        from shared.aws_auth import is_aws_auth_error

        extra_context = ""
        if self.state.review_feedback:
            extra_context += f"\n\n## Review feedback (address before proceeding)\n\n{self.state.review_feedback}"
        if self.state.bdd_feedback and task_name == "bdd_finalization":
            extra_context += f"\n\n## BDD Review Feedback\n\n{self.state.bdd_feedback}"
        if self.state.human_feedback:
            extra_context += f"\n\n## Human guidance\n\n{self.state.human_feedback}"
            self.state.human_feedback = ""  # consume once

        sprint_input = _build_sprint_input(self.state, extra_context)
        crew = build_single_task_crew(
            task_name, sprint_input,
            code_path=self.state.code_path,
            relay=self.relay,
        )
        try:
            result = crew.kickoff(inputs=sprint_input)
            output = str(result)
            tokens = getattr(crew.usage_metrics, "total_tokens", 0) or 0
            self.state.last_task_tokens = tokens
            self.state.session_tokens += tokens
        except Exception as exc:
            if is_aws_auth_error(exc):
                aws_profile = __import__("os").environ.get("AWS_PROFILE", "")
                hint = f"aws sso login{' --profile ' + aws_profile if aws_profile else ''}"
                raise _FlowFailed(
                    f"AWS credentials expired during {task_name}. "
                    f"Run `{hint}` then re-run /jira {self.state.jira_key}."
                ) from exc
            from shared.progress_guard import NoProgressError
            if isinstance(exc, NoProgressError):
                recent = "\n  ".join(exc.recent_calls[-5:])
                return (
                    f"STUCK: {exc.reason}\n"
                    f"Recent calls:\n  {recent}\n"
                    f"Please provide context or a different approach."
                )
            # pydantic: model returned a tool-call object as its "final" output instead of text.
            # The proper fix is to complete the tool round-trip, but the conversation history
            # lives inside CrewAI's agent loop so we can't inject a result externally.
            # Rebuilding and retrying is equivalent — CrewAI will call the tool and continue.
            if "Input should be a valid string" in str(exc) and "ChatCompletion" in str(exc):
                try:
                    crew2 = build_single_task_crew(
                        task_name, sprint_input,
                        code_path=self.state.code_path,
                        relay=self.relay,
                    )
                    result2 = crew2.kickoff(inputs=sprint_input)
                    output = str(result2)
                    tokens2 = getattr(crew2.usage_metrics, "total_tokens", 0) or 0
                    self.state.last_task_tokens = tokens2
                    self.state.session_tokens += tokens2
                except Exception as retry_exc:
                    output = (
                        f"INCOMPLETE: {task_name} — model returned a tool-call instead of text "
                        f"(retry also failed: {str(retry_exc)[:200]})"
                    )
            else:
                output = f"INCOMPLETE: agent failed during {task_name} — {str(exc)[:300]}"
            return output

        if "Failed to parse LLM response" in output:
            output = f"INCOMPLETE: {task_name} — LLM response could not be parsed (context may be too large)"

        return output

    # ------------------------------------------------------------------
    # Human escalation
    # ------------------------------------------------------------------

    def _escalate(self, gate: str) -> None:
        self.state.status = "needs_help"
        self.state.needs_help_gate = gate
        self._emit()
        self._feedback_event.clear()
        self._feedback_event.wait()

    # ------------------------------------------------------------------

    def _emit(self) -> None:
        self._on_status(self.state)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TASK_AGENTS: dict[str, str] = {
    # Managed tasks: fast manager LLM drives the worker to completion
    "scaffold_code":        "manager → engineer",
    "scaffold_test":        "manager → qa-lead",
    "bdd_authoring":        "manager → qa-lead",
    "bdd_finalization":     "manager → qa-lead",
    "implementation":       "manager → engineer",
    "devops_coordination":  "manager → devops-lead",
    "release_notes":        "manager → release-engineer",
    "promote_staging":      "manager → devops-lead",
    "staging_verification": "manager → qa-lead",
    "launch_decision":      "release-engineer",
    "smoke_test":           "manager → qa-lead",
    # Sequential tasks: evaluation/review — text output, no execution needed
    "sprint_planning":      "scrum-master",
    "architecture_review":  "architect",
    "bdd_po_review":        "product-owner",
    "bdd_arch_review":      "architect",
    "code_review":          "architect",
    "security_review":      "security-lead",
    "compliance_review":    "compliance-officer",
    "dod_check":            "scrum-master",
}


def _build_sprint_input(state: TicketState, extra_context: str = "") -> dict:
    """Build the sprint_input dict passed to crew tasks."""
    return {
        "jira_key": state.jira_key,
        "sprint_name": state.sprint_name,
        "review_feedback": state.review_feedback,
        "human_feedback": extra_context,
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


def _is_impl_done(output: str) -> bool:
    """Return True only if the agent explicitly confirmed IMPLEMENTATION COMPLETE."""
    if not output or output.startswith("INCOMPLETE:") or output.startswith("SKIPPED:"):
        return False
    return "IMPLEMENTATION COMPLETE" in output.upper()


def _fmt_k(tokens: int) -> str:
    """Format token count as e.g. '2.3k' or '150k'."""
    if tokens < 1000:
        return str(tokens)
    return f"{tokens / 1000:.1f}k" if tokens < 10_000 else f"{tokens // 1000}k"


_SUMMARY_SKIP = frozenset({
    "TASK COMPLETE", "IMPLEMENTATION COMPLETE", "APPROVED", "LGTM",
    "INCOMPLETE", "TASK FAILED", "---", "```",
})

def _extract_summary(output: str, max_lines: int = 8, max_len: int = 120) -> str:
    """Return the last N meaningful lines of task output (verdict tends to be at the end)."""
    lines = []
    for l in output.strip().splitlines():
        clean = l.strip(" #*-|`")
        if clean and clean.upper() not in _SUMMARY_SKIP and not clean.startswith("```"):
            lines.append(clean[:max_len])
    if not lines:
        return output.strip()[:max_len]
    return "\n".join(lines[-max_lines:])


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _checkpoint_path(jira_key: str) -> Path:
    return Path.cwd() / ".code-crew" / "checkpoints" / f"{jira_key}.json"


def _save_checkpoint(state: TicketState) -> None:
    path = _checkpoint_path(state.jira_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.task_outputs), encoding="utf-8")


def _load_checkpoint(jira_key: str) -> dict[str, str]:
    path = _checkpoint_path(jira_key)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _delete_checkpoint(jira_key: str) -> None:
    _checkpoint_path(jira_key).unlink(missing_ok=True)
