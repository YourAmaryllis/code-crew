# ADD-005: Ticket and Sprint Flow Design

**Status:** Accepted
**Date:** 2026-07-03
**Related:**
- [ADR-007: Python flow orchestration](../adr/ADR-007-Python-Flow-Orchestration.md)
- [ADR-006: Manager-worker execution model](../adr/ADR-006-Manager-Worker-Execution-Model.md)
- [ADR-003: Async wait points](../adr/ADR-003-Async-Wait-Points.md)
- [SAD-001: code-crew system architecture](../sad/SAD-001-code-crew.md)

---

## Purpose

`/issue <KEY>` and `/sprint <name>` are the primary entry points for the main SDLC pipeline. This document describes the full flow lifecycle: ticket fetch, phase sequence, BDD cycle, implementation gate, staging loop, human gates, checkpointing, and resume.

---

## Entry Points

### `/issue <KEY>`
Full SDLC pipeline for a single ticket from any supported issue tracker (Jira, Linear, GitHub Issues).

```bash
/issue PROJ-123
code-crew issue PROJ-123    # CLI equivalent
```

### `/sprint <name>`
Fetches all open tickets in the named sprint/iteration, then runs each through TicketFlow. Stories run sequentially by default; limited parallelism is possible for independent tasks.

```bash
/sprint "Sprint 12"
```

---

## Ticket Fetch

`IssueViewTool` fetches the ticket before the flow starts:

| Field | Source | Used by |
|-------|--------|---------|
| `jira_key` | Issue key | Context injected into every task |
| `story` | Summary + description | Sprint planning, implementation |
| `acceptance_criteria` | AC fields or parsed from description | Every task |
| `figma_url` | Custom field or description link | UX tasks, implementation |
| `html_design_ref` | Custom field | Implementation |
| `add_refs` | Linked design docs | Architecture review, implementation |
| `comment_context` | Recent comments | Implementation (may include human decisions) |
| `raw_ticket` | Full ticket body | Design flow, sprint planning |

The assembled `sprint_input` dict is passed to every `build_single_task_crew()` call and injected into each task description via `_format_context()`.

---

## Full Phase Sequence

```
sprint_planning_check     scrum_master       DoR gate — ACs testable, story sized
architecture_review       architect          Reads ADRs/ADDs, proposes approach
scaffold_code             manager→engineer   Creates stubs; build check
scaffold_test             manager→qa_lead    Creates test stubs matching scaffold

[BDD CYCLE — loops until BDD APPROVED or max_retries]
  bdd_test_authoring      manager→qa_lead    Writes Gherkin .feature files
  bdd_po_review           product_owner      Validates business language
  bdd_arch_review         architect          Validates technical correctness
  bdd_finalization        manager→qa_lead    Consolidates feedback
  → if BDD APPROVED: continue
  → if not: re-run from bdd_test_authoring with feedback

[IMPLEMENTATION LOOP — loops on gate failure]
  implementation           manager→engineer   Implements against BDD; unit tests inline
  devops_coordination      manager→devops_lead Dockerfile, CI pipeline, migration config
  code_review              architect          [gate] REJECTED → retry from implementation
  security_review          security_lead      [gate] REJECTED → retry from implementation
  compliance_review        compliance_officer [gate] REJECTED → retry from implementation
  dod_check                scrum_master       [gate] REJECTED → retry from implementation
  → if all gates pass: continue

release_notes              manager→release_engineer  Changelog entry + GitHub Release draft

[STAGING LOOP — loops on verification failure]
  promote_staging          manager→devops_lead  Push rc tag; trigger deploy
  staging_verification     manager→qa_lead     BDD smoke on staging
  → if STAGING FAILED: re-run promote_staging
  → if STAGING VERIFIED: continue

launch_decision            release_engineer    Go/no-go (human gate follows)

[HUMAN GATE: workflow_dispatch / GitLab manual job → production]

smoke_test                 manager→qa_lead     Read-only smoke on production
```

Manager-driven tasks (`manager→`) use `Process.hierarchical`. All others use `Process.sequential`.

---

## Retry Logic

### BDD cycle
```python
for attempt in range(max_retries):
    bdd_authoring_output = run("bdd_test_authoring")
    po_output = run("bdd_po_review")
    arch_output = run("bdd_arch_review")
    final_output = run("bdd_finalization")
    if "BDD APPROVED" in final_output:
        break
    # inject po + arch feedback into next iteration
else:
    escalate_to_human("BDD not approved after max_retries")
```

### Implementation gate
```python
for attempt in range(max_retries):
    impl_output = run("implementation")
    devops_output = run("devops_coordination")
    review_output = run("code_review")
    sec_output = run("security_review")
    comp_output = run("compliance_review")
    dod_output = run("dod_check")
    if not any("REJECTED" in o for o in [review_output, sec_output, comp_output, dod_output]):
        break
    # inject rejection reasons into sprint_input["human_feedback"] for next iteration
else:
    escalate_to_human("Implementation not approved after max_retries")
```

---

## Human Escalation

When `max_retries` is exhausted:

1. Flow sets `state.status = "needs_help"` and `state.needs_help_gate = <task_name>`
2. REPL prompt changes from green `→` to yellow `!` with the stuck task name
3. User types `/help <message>` → `inject_feedback()` appends message to `sprint_input["human_feedback"]`
4. User types `/retry` → flow re-runs the stuck task with the injected context
5. User types `/abort` → flow terminates

Human feedback is injected into the sprint context block prepended to every subsequent task description — all agents in the next attempt see the guidance.

---

## Checkpointing

After each task completes, `TicketFlow` writes:
```json
// .code-crew/checkpoints/PROJ-123.json
{
  "sprint_planning": "SPRINT PLANNING COMPLETE\n...",
  "architecture_review": "ARCHITECTURE REVIEW COMPLETE\n...",
  "scaffold_code": "TASK COMPLETE\n..."
}
```

On re-run with the same key:
```
Checkpoint found for PROJ-123 (3 tasks complete: sprint_planning, architecture_review, scaffold_code).
Resume? [Y/n]
```
- **Y**: replays 3 completed tasks as `[checkpoint]` instantly, picks up from `scaffold_test`
- **N**: discards checkpoint, starts from scratch

Checkpoints are cleared on normal completion (all tasks through `smoke_test`) or manually by deleting the file.

---

## Context Assembly

`_format_context(sprint_input)` builds the context block prepended to every task description:

```
[Active skills — if any]

## Sprint context

**Issue key**: PROJ-123
**Sprint goal**: <sprint goal from issue tracker>
**Story**: <summary and description>
**Figma**: <URL or "not provided">
**HTML design**: <ref or "not provided">
**Relevant ADDs**: ADD-012, ADD-015
**Designs directory**: ./designs — use this path for ADR/ADD file operations
**Architecture pattern**: hexagonal — load stacks/arch-hexagonal.md via knowledge_reader

**Acceptance criteria**:
- User can log in with email + password
- Invalid credentials return 401 with error message

## Context from issue tracker comments
<recent comments truncated to 2000 chars>

## Project structure
<.code-crew/structure.md content>
```

This block is the same for every task in the run. Agents see ticket context, designs path, and project structure without any inter-agent shared memory. Upstream task outputs reach downstream tasks only via `Task.context=` typed outputs.

---

## Sprint Flow (`/sprint`)

1. `IssueListTool` fetches all open tickets in the named sprint/iteration
2. User confirms the list (REPL: "Run N tickets? [Y/n]")
3. Each ticket runs through `TicketFlow` sequentially
4. On failure mid-sprint: REPL shows which ticket is stuck, exposes `/help`, `/retry`, `/skip`
5. Sprint summary at end: N complete, M failed, time elapsed, total token estimate

---

## Key Files

| File | Purpose |
|------|---------|
| `code_crew/flow.py` | `TicketFlow` — phase sequence, retry loops, human escalation, checkpoint read/write |
| `code_crew/crew.py` | `build_single_task_crew()` — builds one crew per task; `_format_context()` |
| `code_crew/repl.py` | `/issue`, `/sprint` commands; REPL prompt state; `/help`, `/retry`, `/abort` |
| `shared/tools/` | `IssueViewTool`, `IssueListTool` — issue tracker backends |
| `.code-crew/checkpoints/<KEY>.json` | Task output cache for resume |
| `.code-crew/flow-state.json` | Async wait state (staging/CI suspends) |
