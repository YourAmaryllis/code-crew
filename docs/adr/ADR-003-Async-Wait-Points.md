# ADR-003: Async Wait Points for Long-Running Flow Tasks

**Status:** Accepted
**Date:** 2026-07-02
**Related:**
- [ADD-001: Virtual AI Development Team Design](../add/ADD-001-Virtual-AI-Development-Team.md)
- [SAD-001: code-crew system architecture](../sad/SAD-001-code-crew.md)

---

## Context

The code-crew flow includes three phases that invoke external processes:

| Task | External process | Typical duration |
|------|-----------------|-----------------|
| `promote_staging` | `workflow_dispatch` → GitHub Actions deploy | 5–15 min |
| `staging_verification` | BDD test suite (Cucumber / Playwright) | 10–30 min |
| `smoke_test` | Post-production smoke check | 2–5 min |

Currently the REPL blocks synchronously on each of these. If the agent polls via a shell loop, every poll burns an API call. If CrewAI times the task out, the run fails. Neither is acceptable for production use.

The REPL already runs `explore` and `threat` as background processes and uses `ScheduleWakeup` (via Claude Code's `/loop` mechanism) to check on them non-blocking. The same pattern should apply to the flow's long-running tasks.

---

## Decision

Introduce **async wait points** in the flow. When the crew enters a long-running task:

1. The agent kicks off the external process and returns a **run handle** (GitHub Actions run ID, ECS service ARN, or similar).
2. The REPL serialises a **flow state** record to disk and exits the current crew.
3. `ScheduleWakeup` fires after a sensible interval (60–270 s to stay inside the LLM prompt cache TTL).
4. On wakeup, the REPL reads the state, polls the external process for completion, and either resumes the next crew task or reschedules.
5. On completion, the result (success / failure / logs URL) is fed as context into the next task.

---

## Flow state schema

Persisted to `.code-crew/flow-state.json` in the platform repo root.

```json
{
  "project_id": "<project-id>",
  "phase": "staging_verification",
  "run_handle": {
    "type": "gh_actions",
    "run_id": 12345678,
    "workflow": "bdd.yml",
    "repo": "org/platform"
  },
  "started_at": "2026-07-02T14:30:00Z",
  "context": {
    "jira_issue": "<ISSUE-KEY>",
    "branch": "feat/<issue-slug>",
    "stacks": ["go-backend", "typescript-react"],
    "otm_path": "designs/TMD/<project>.yaml"
  },
  "attempt": 1,
  "max_attempts": 3
}
```

`run_handle.type` is one of:
- `gh_actions` — poll with `gh run view {run_id} --json status,conclusion,url`
- `ecs_deploy` — poll with `aws ecs describe-services` until `runningCount == desiredCount`
- `manual` — operator has been notified; poll until a sentinel file appears or `/resume` is typed

---

## Wakeup schedule

| Phase | Poll interval | Rationale |
|-------|--------------|-----------|
| `promote_staging` | 60 s | Deploy usually finishes in 5–10 min; short interval catches it quickly |
| `staging_verification` | 120 s | BDD suite is 10–30 min; 120 s is fine granularity |
| `smoke_test` | 60 s | Short process; fast feedback matters |

All intervals stay under 270 s to keep the LLM prompt cache warm.

---

## Implementation (as built)

### 1 — `async_job` tool  (`shared/tools/async_job.py`)

`AsyncJobTool` with two operations (`start` / `poll`) and three backends the agent picks based on context:

| type | params | what it does |
|------|--------|-------------|
| `gh_actions` | `{workflow, ref?, inputs?, repo?}` | `gh workflow run` + fetch run_id |
| `shell` | `{command, label?, cwd?}` | Runs any command in background; writes exit code to `.code-crew/jobs/<id>.status` |
| `ecs` | `{cluster, service, image?, region?}` | `aws ecs update-service --force-new-deployment` |

`CiStatusTool` is a backward-compat alias for `AsyncJobTool`.
Wire to: `devops_lead` and `qa_lead` agents in `crew.py`.

### 2 — Flow state persistence  (`code_crew/repl.py`)

Add two helpers:

```python
def _save_flow_state(state: dict) -> None:
    path = Path.cwd() / ".code-crew" / "flow-state.json"
    path.write_text(json.dumps(state, indent=2))

def _load_flow_state() -> dict | None:
    path = Path.cwd() / ".code-crew" / "flow-state.json"
    return json.loads(path.read_text()) if path.exists() else None

def _clear_flow_state() -> None:
    path = Path.cwd() / ".code-crew" / "flow-state.json"
    path.unlink(missing_ok=True)
```

### 3 — Async wait points in the flow

In the task execution loop, after each long-running task returns a run handle:

```python
# Pseudocode — integrate into _run_flow() or wherever promote_staging is invoked
run_handle = promote_staging_crew.kickoff(inputs=inputs)
if run_handle.get("type") in ("gh_actions", "ecs_deploy"):
    _save_flow_state({
        "project_id": project["id"],
        "phase": "promote_staging",
        "run_handle": run_handle,
        "started_at": datetime.utcnow().isoformat() + "Z",
        "context": flow_context,
        "attempt": attempt,
        "max_attempts": max_staging_retries,
    })
    console.print("[dim]  Deploy kicked off — suspending flow. Will resume when complete.[/dim]")
    return  # exit; ScheduleWakeup takes over
```

### 4 — `/loop` resume path  (`code_crew/repl.py`)

Add a `/loop` REPL command (or wire it to Claude Code's `ScheduleWakeup`). On each tick:

```python
state = _load_flow_state()
if not state:
    console.print("No suspended flow.")
    return

handle = state["run_handle"]
if handle["type"] == "gh_actions":
    result = subprocess.run(
        ["gh", "run", "view", str(handle["run_id"]), "--json", "status,conclusion,url"],
        capture_output=True, text=True,
    )
    info = json.loads(result.stdout)
    if info["status"] == "completed":
        if info["conclusion"] == "success":
            _clear_flow_state()
            _resume_flow(state, result=info)   # continue to next task
        else:
            _handle_flow_failure(state, info)  # escalate or retry
    else:
        # Still running — reschedule
        console.print(f"[dim]  {state['phase']} still running ({info['status']})…[/dim]")
        # ScheduleWakeup is called by the outer /loop harness
```

### 5 — `_resume_flow(state, result)`

Maps `state["phase"]` to the next task:

```python
NEXT_PHASE = {
    "promote_staging": "staging_verification",
    "staging_verification": "launch_decision",
    "smoke_test": None,  # flow complete
}
```

Feeds `result` (logs URL, conclusion) into the next crew's context so the agent has evidence.

### 6 — `/resume` REPL command

Allow the operator to manually trigger resume without waiting for the next wakeup:

```
/resume          — check state + poll immediately
/resume abort    — clear state + mark flow failed
```

---

## What the manager-worker loop already handles

The CrewAI hierarchical crew (Security Lead + Architect, manager + worker) handles **iterative revision within a single task** — the manager sends work back to the worker until output meets the acceptance criteria. This does not require `ScheduleWakeup`; it is synchronous and runs to completion in a single crew kickoff.

`ScheduleWakeup` is only needed for tasks that block on **external processes** (CI runners, ECS deployments, BDD suites) that run outside the LLM loop entirely.

---

## Files created / modified

| File | Change |
|------|--------|
| `shared/tools/async_job.py` | New — `AsyncJobTool` with `start`/`poll` + three backends (`gh_actions`, `shell`, `ecs`) |
| `shared/tools/__init__.py` | Export `AsyncJobTool`; `CiStatusTool` re-exported as backward-compat alias |
| `code_crew/crew.py` | `async_job` in `_make_tools()`; wired to `devops_lead` and `qa_lead` |
| `code_crew/flow.py` | `StagingHandedOff` exception; `_extract_run_handle()`; `_staging_loop()` suspends on RUN_HANDLE |
| `code_crew/repl.py` | `_save/load/clear_flow_state`, `_poll_ci_run` (delegates to `AsyncJobTool`), `/loop` + `/resume` commands |
| `code_crew/knowledge/tasks/promote_staging.md` | Agent uses `async_job` (GHA or ECS); emits `RUN_HANDLE:` |
| `code_crew/knowledge/tasks/staging_verification.md` | Agent uses `async_job` (GHA or shell); emits `RUN_HANDLE:` |
| `code_crew/knowledge/tasks/smoke_test.md` | Agent uses `async_job` (GHA or shell); emits `RUN_HANDLE:` |
