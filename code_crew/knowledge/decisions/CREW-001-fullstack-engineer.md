---
name: CREW-001-FullstackEngineer
description: Decision to align crew agents with SDLC roles and use a single full-stack engineer instead of split backend/frontend agents
metadata:
  type: decision
  status: accepted
  date: 2026-06-20
---

# CREW-001: SDLC Role Alignment and Full-Stack Engineer

## Status

Accepted — 2026-06-20

## Context

The crew originally had two implementation agents (`backend_developer`, `frontend_developer`) whose
backstories were authored independently of the platform SDLC. The platform SDLC
(`designs/SDLC/roles/`) defines a canonical set of roles derived from the same SOPs the crew is
meant to enforce. Having crew agents diverge from SDLC role definitions creates a maintenance split —
two sources of truth for how the same role should behave.

Two approaches for feature implementation were also compared:

**Option A: Split agents + API contract step**
- `backend_developer` implements Go API and backend logic
- `frontend_developer` implements React components
- Requires an intermediate "API spec agreement" task between them before each can work
- Adds an extra agent, an extra task, and another failure point

**Option B: Full-stack engineer**
- Single `engineer` agent handles both backend and frontend
- No API coordination step — the same agent makes holistic decisions
- Aligned with SDLC `engineer` role (phases 17 and 18 are the same role in the SDLC)

## Decision

1. **Align all crew agent definitions with `designs/SDLC/roles/`** — agent backstories derive from
   SDLC role documents, not independent definitions.
2. **Use a single full-stack `engineer` agent** (Option B) — replacing split `backend_developer`
   and `frontend_developer`.
3. **Add `product_owner` and `devops_lead` agents** — both are SDLC roles required for the BDD
   review cycle and deployment coordination cycle.

## Rationale

**SDLC alignment**: SOPs are the source of truth for role behaviour. Crew agent backstories should
derive from SDLC role definitions so that SOP updates propagate automatically rather than requiring
a separate code change.

**Full-stack over split**: An LLM already has deep knowledge of both Go and TypeScript/React. The
specialisation benefit of split human roles does not apply. Option A's API contract step adds
overhead with no quality gain for an AI agent that can make both decisions in a single pass.

**BDD review cycle**: The QA spec authoring cycle (QA writes → PO + Architect review → QA revises →
repeat until both approve) requires both roles as active reviewing agents. Neither existed before.

**DevOps coordination cycle**: Features that introduce new env vars, secrets, or IAM permissions
require a handoff from the engineer to the DevOps lead before integration tests can pass. This cycle
may repeat 2–3 times per story. The `devops_lead` agent owns this step.

## Manager-Worker Execution Model

`TicketFlow` controls the SDLC phase sequence in Python — it is the outer orchestrator.
Within tasks that require writing to files or running commands, `Process.hierarchical` is
used with a **fast manager LLM** that drives the worker agent until work is genuinely
complete (not just planned). Review and evaluation tasks run sequentially with no manager.

This is not LLM-based orchestration of the SDLC sequence — the phase order is fixed by the
SDLC and enforced in Python. The manager only operates within a single task boundary.

```
TicketFlow (Python) → dispatch "implementation"
  Manager LLM (fast): drives engineer agent to completion
    Worker (engineer): writes code, runs tests, confirms done
  Manager LLM: confirms IMPLEMENTATION COMPLETE
TicketFlow → proceeds to devops_coordination
```

## Consequences

- `backend_developer.md`, `frontend_developer.md` agents deleted; replaced by `engineer.md`
- `backend_implementation.md`, `frontend_implementation.md` tasks replaced by `implementation.md`
- `tech_lead.md` renamed to `architect.md`
- `qa_engineer.md` renamed to `qa_lead.md`
- `security_reviewer.md` renamed to `security_lead.md`
- New `product_owner.md` and `devops_lead.md` agents added
- New BDD cycle tasks added: `bdd_po_review`, `bdd_arch_review`, `bdd_finalization`
- New `devops_coordination` task added after implementation
- TicketFlow updated: linear phase → BDD cycle → implementation loop (with devops coordination)
