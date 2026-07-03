# ADR-006: Manager-Worker Execution Model for Implementation Tasks

**Status:** Accepted
**Date:** 2026-07-03
**Related:**
- [ADR-007: Python flow orchestration](ADR-007-Python-Flow-Orchestration.md)
- [ADR-002: Full-stack engineer agent](ADR-002-Fullstack-Engineer-Agent.md)
- [SAD-001](../sad/SAD-001-code-crew.md)

---

## Context

LLM agents in a multi-step SDLC workflow have a consistent failure mode: they **describe work instead of doing it**. An engineer agent asked to implement a feature will often produce a plan ("I would create a handler at `api/users.go`..."), then output `IMPLEMENTATION COMPLETE` — without writing a single file.

CrewAI's `Process.sequential` provides no mechanism to catch this. The task receives the plan as output and the flow proceeds, leaving no files written.

Two approaches were considered:

**Option A: Guardrails only (no manager)**
Add a `guardrail` function to each task. If the required completion signal is absent, CrewAI retries the task automatically up to `guardrail_max_retries`. The guardrail message is injected as the next user turn.

- Pros: simpler setup; no extra LLM tier needed
- Cons: each retry is a fresh agent turn with no memory of what was already tried; agent may repeat the same plan-instead-of-execute mistake; guardrail message has limited influence on a single-agent retry

**Option B: Manager-worker (`Process.hierarchical`)**
A fast manager LLM drives the worker in a dialogue. The manager sees the worker's output and either accepts it (work done) or sends specific instructions back. The worker retains conversational context across turns.

- Pros: manager can give targeted feedback ("you described a plan — write the file now"); worker remembers what it has already tried; manager can escalate after N failed attempts
- Cons: extra LLM cost (manager turn per rejection); setup is more complex

## Decision

Use **manager-worker (`Process.hierarchical`) for execution tasks; guardrails as a second layer**.

1. **`MANAGED_TASKS`** frozenset identifies tasks where plan-instead-of-execute is a real risk: `scaffold_code`, `scaffold_test`, `bdd_authoring`, `bdd_finalization`, `implementation`, `devops_coordination`, `release_notes`, `promote_staging`, `staging_verification`, `smoke_test`.

2. **Manager LLM tier**: `standard` for `implementation` (must judge whether actual code was written — requires reasoning); `fast` for all other managed tasks (simpler verification: did the expected signal appear?).

3. **Manager agent** is built from `knowledge/agents/manager_engineer.md` — an OKF file defining the manager's role ("drive the worker to complete the work, not describe it") and backstory. No manager prompt is hardcoded in Python.

4. **Guardrails** are a second validation layer: each managed task has a `guardrail` function that checks for the required completion signal. If absent, the guardrail returns `(False, error_message)` and CrewAI auto-retries up to `guardrail_max_retries=5`.

5. **`INCOMPLETE:` protocol**: if the worker cannot complete the task (missing file, auth error, etc.), it outputs `INCOMPLETE: <reason>`. The guardrail detects this and returns a specific message to the manager: "Worker reported INCOMPLETE. Send them back to resolve the blocker." This prevents the manager from treating an honest admission as a completion.

6. **`implementation` guardrail** (`_impl_guardrail`) requires BOTH `IMPLEMENTATION COMPLETE` AND a `FILES CHANGED:` block listing every modified file. This prevents the manager from accepting output that claims completion but provides no evidence.

7. **CI tasks** (`promote_staging`, `staging_verification`, `smoke_test`) use `_make_ci_guardrail()` — accepts `success_signal`, `fail_signal`, OR `RUN_HANDLE: {...}` (async path). The manager accepts any of the three as valid completion.

8. **Threat modeling** uses the same hierarchical pattern with reversed roles: Security Lead as manager, Architect as worker. Security Lead drives the conversation through OWASP TMP phases; Architect reads source files and answers. This is a separate `build_threat_model_crew()` function, not part of `MANAGED_TASKS`.

9. **Sequential tasks** (review, planning, evaluation) use `Process.sequential` with no manager. These tasks produce analysis, not file changes — the plan-vs-execute problem does not apply.

## Consequences

**Positive:**
- Manager eliminates the most common failure mode (plan without executing) through targeted dialogue
- Worker retains conversational context — "send it back" means the worker remembers what it has already tried
- Guardrail as a second layer catches cases where the manager mistakenly accepts incomplete output
- `FILES CHANGED:` requirement on implementation tasks provides evidence of actual work

**Negative / Risks:**
- Each manager rejection adds 1–2 LLM calls (manager prompt + worker response) — cost scales with retry count
- Manager tier must be chosen carefully: `fast` for simple signal checks, `standard` for implementation (needs to read code vs plan)
- If `max_iter` is hit inside the hierarchical crew before completion, the task fails with no partial output — mitigation: `max_iter=25` for engineer, `max_iter=35` for threat architect

**Operational:**
- `MANAGED_TASKS` in `code_crew/crew.py` — add/remove task names to change which tasks use the manager
- `_STANDARD_MANAGER_TASKS` — subset of `MANAGED_TASKS` that use the `standard` (not `fast`) manager
- `knowledge/agents/manager_engineer.md` — manager instructions (OKF file)
- `ProgressGuard` (`shared/progress_guard.py`) — `step_callback` that detects zero-progress loops and fails fast rather than hitting `max_iter`
