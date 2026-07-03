# ADR-007: Python Controls SDLC Phase Sequence; Agents Control Individual Task Execution

**Status:** Accepted
**Date:** 2026-07-03
**Related:**
- [ADR-006: Manager-worker execution model](ADR-006-Manager-Worker-Execution-Model.md)
- [ADR-002: Full-stack engineer agent](ADR-002-Fullstack-Engineer-Agent.md)
- [ADD-005: Ticket and sprint flow design](../add/ADD-005-Ticket-And-Sprint-Flow.md)

---

## Context

A multi-phase SDLC pipeline needs two kinds of control:

1. **Phase sequencing**: which task runs after which, when to retry, when to escalate, what passes to what
2. **Task execution**: how to do the work within a single task — which files to read, which tools to call, how many steps to take

Two architectures were considered:

**Option A: LLM-based orchestration (CrewAI manager drives the full sequence)**
One "orchestrator" LLM receives the full ticket and decides which crew to run next. Each crew output is fed back to the orchestrator, which decides whether to retry or proceed.

- Pros: flexible; the orchestrator can dynamically adapt the sequence
- Cons: phase order is non-negotiable in an SDLC (security review ALWAYS follows implementation — there is no dynamic); the orchestrator consumes tokens deciding something that is already decided; LLM hallucinations can skip gates; harder to checkpoint; harder to inject human feedback at specific points

**Option B: Python controls the sequence; agents control each task**
A Python class (`TicketFlow`) encodes the SDLC phase sequence. Each phase is a single `build_single_task_crew()` call. The agent (+ optional manager) decides how to execute that one phase. Python handles retries, gates, human escalation, and checkpointing.

- Pros: sequence is deterministic and auditable; gates cannot be skipped by LLM decision; clean checkpointing per task; human feedback injectable at task boundaries; cost-efficient (no orchestrator tokens per phase)
- Cons: sequence changes require code changes (acceptable — SDLC phases are not volatile)

## Decision

**Python (`TicketFlow`) owns the SDLC phase sequence. Agents (+ optional manager) own individual task execution.**

1. `TicketFlow` is a Python class that steps through the task sequence: `sprint_planning → architecture_review → scaffold_code → ... → smoke_test`. It calls `build_single_task_crew(task_name, ...)` for each phase.

2. **Retry gates** are Python logic:
   - BDD cycle: if `bdd_finalization` output does not contain `BDD APPROVED`, Python re-runs `bdd_authoring → bdd_po_review + bdd_arch_review → bdd_finalization`, up to `max_retries` times
   - Implementation gate: if `code_review`, `security_review`, `compliance_review`, or `dod_check` contains `REJECTED`, Python re-runs `implementation + devops_coordination` and re-runs all four gates
   - Staging loop: if `staging_verification` contains `STAGING FAILED`, Python re-runs `promote_staging → staging_verification`
   - Retry counts enforced in Python — LLM cannot override

3. **Gate signals** are plain text in agent output — `BDD APPROVED`, `REJECTED`, `STAGING FAILED`, `RUN_HANDLE:`. Python scans the output string. Agents do not call any Python API to advance the flow.

4. **Human escalation**: when `max_retries` is exhausted, Python calls `inject_feedback()` and waits. The REPL surfaces `/help <message>` to inject guidance, and `/retry` to force re-attempt. The flow blocks on a threading event; no polling.

5. **Async wait points**: when an agent emits `RUN_HANDLE: {...}` (e.g. a CI workflow run ID), Python serialises flow state to `.code-crew/flow-state.json` and exits the current run. `/loop` or `/resume` polls the external process and resumes when done. See ADR-003.

6. **Checkpointing**: after each task completes, Python writes `.code-crew/checkpoints/<KEY>.json` with a map of `task_name → output_string`. On re-run with the same key, completed tasks are replayed from cache (no LLM call). Failed tasks and all subsequent tasks re-run.

7. **`DesignFlow`, `UxFlow`, `DomainFlow`** follow the same Python-outer-loop pattern — each is a distinct Python class with its own phase sequence, retry logic, and state.

8. **Within a task**, the agent makes all decisions: which tools to call, how many iterations to use, whether to ask the human via `AskHumanTool`, whether to emit `INCOMPLETE:`. The Python layer does not control agent behaviour inside a task.

## Consequences

**Positive:**
- Phase order is deterministic and auditable in code — `TicketFlow._run()` reads like a spec
- Gate signals can be tracked and reported via the REPL without parsing LLM reasoning
- Checkpointing per task is simple — write the output string after each successful `crew.kickoff()`
- Human feedback injectable at task boundaries without interrupting mid-task execution
- Cost-efficient — no orchestrator LLM between phases

**Negative / Risks:**
- Sequence changes require code changes to `flow.py` — acceptable but not zero-effort
- Gate signals are string-matched — if the model uses a synonym (`"BDD ACCEPTED"` instead of `"BDD APPROVED"`), the gate will not pass. Mitigation: expected signals are in the task `expected_output` OKF field; models are instructed to use exact strings

**Operational:**
- `code_crew/flow.py` — `TicketFlow`, `DesignFlow`, `UxFlow`, `DomainFlow`
- `code_crew/crew.py` — `build_single_task_crew()` — builds one crew per task; no shared state
- Flow state: `.code-crew/flow-state.json` (async wait), `.code-crew/checkpoints/<KEY>.json` (task cache)
