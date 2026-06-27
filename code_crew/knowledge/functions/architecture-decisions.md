---
name: SDLC-Architect-ArchitectureDecisions
description: ADR/ADD format, when to write them, who triggers them, and how they integrate with Jira and the code review process
metadata:
  type: process
  role: architect
  phase: "5, 7, 11, 19"
---

# Architecture Decisions: ADRs and ADDs

This document covers the three architecture document types, their formats, and how they relate to each other. For SAD update process and structure, see `sad-maintenance`.

---

## Document Hierarchy

```
SAD  (Solution Architecture Document)
 │   Overarching. Covers the whole application.
 │   Ultimate source of truth for structure, data flow, and security posture.
 │   Updated when architecture changes. Almost every update needs a new ADR.
 │
 ├── ADR  (Architecture Decision Record)
 │    Captures WHY a decision was made.
 │    One ADR per decision. Immutable once accepted.
 │    A SAD change without an ADR is an undocumented decision.
 │
 └── ADD  (Architecture Design Document)
      Expands on a specific component or module from the SAD.
      Answers HOW — implementation detail, data models, API contracts, sequence diagrams.
      Does not replace the SAD; references the SAD section it elaborates.
```

**Flow when making an architectural change:**
1. Write the ADR (captures the decision and its context)
2. Update the relevant SAD section(s) to reflect the outcome
3. Write or update the ADD for the affected component if implementation detail changed

---

## Architect Gate: Before QA and Engineering

The architect's job is not just review — it is documentation first, then handoff.

Before the crew proceeds to BDD authoring and implementation, the architect must:

1. Load all relevant ADRs and ADDs for the story
2. Assess alignment: ALIGNED / DEVIATION / NEW-DECISION-NEEDED for each
3. Resolve deviations and documented decisions (update or write ADR/ADD/SAD)
4. Escalate genuinely novel decisions to the Chief Architect (see below)
5. Only then issue APPROVED TO PROCEED

QA and the engineer do not start until the architecture gate is cleared. This prevents
discovering design conflicts mid-implementation.

---

## Chief Architect Role

The **Chief Architect is a human**, not an AI agent. The crew consults the Chief
Architect only when the architect encounters a cross-cutting decision with no existing
ADR or ADD precedent.

### When consultation is triggered

The architect escalates when:
- A story introduces a choice that will affect multiple components, be hard to reverse,
  and has no similar existing ADR/ADD to reference
- A proposed deviation from an existing ADR is substantial enough to warrant a new
  architectural direction

The architect presents:
- The decision point in one sentence
- Numbered options, each with pros and cons
- An optional recommendation if one option is clearly preferred

### Chief Architect response options

1. **Type a number** (1, 2, 3…) — selects that option. The architect documents the
   decision in a new ADR (Status: Accepted), updates the SAD and ADD, then proceeds.
2. **Type free text** — provides guidance, asks questions, or specifies a different
   approach. The architect incorporates it and re-runs the review.

### After a Chief Architect decision

The architect agent:
1. Writes a new ADR capturing the decision (Status: Accepted)
2. Updates the relevant SAD view (Decomposition, Data Flow, Security, etc.)
3. Writes or updates the ADD for the affected component
4. Re-runs the architecture review to confirm alignment
5. Produces APPROVED TO PROCEED

---

## Who Can Trigger an ADR or ADD

Anyone on the team can propose an ADR or ADD by:

1. Writing a Jira comment on the relevant ticket with a draft or request
2. Creating a branch in `designs` and opening a PR

The **architect** is the final approver for all ADRs and ADDs.

---

## ADR: When to Write One

Write an ADR when you are making a decision that:

- Affects multiple components or teams
- Will be hard to reverse (technology choice, data model, security posture)
- Someone in 6 months would reasonably ask "why did we do it this way?"

**Examples of ADR-worthy decisions:**

- Choosing Go over Python for a new backend service
- Adopting trunk-based development as the branching strategy
- Selecting Ant Design v6 for the portal UI
- Deciding to use ECS + Fargate instead of EKS
- Choosing AWS Bedrock for LLM inference
- Adopting zero-custody PHI as a product constraint

**Not ADR-worthy (use an ADD or a PR comment):**

- Implementation details within a single service
- One-sprint tactical choices that are easily reversed
- Bug fixes

---

## ADD: When to Write One

Write an ADD when you are designing a feature or component that:

- Involves non-trivial data modeling or API design
- Spans multiple services or layers
- Other engineers need to reference to implement correctly
- Has meaningful trade-offs that aren't obvious from the code

**Examples of ADD-worthy work:**

- Designing the data curation pipeline (ADD-020)
- Defining the Terraform module structure (ADD-018)
- Specifying the portal authentication flow
- Designing the BDD test reporting integration

**Not ADD-worthy:**

- Simple CRUD endpoints following established patterns
- Refactors that don't change the design
- Minor UI changes (Figma suffices)

---

## Workflow: New Feature with an ADD

``` text
1. Architect writes ADD draft during Phase 11 (Technical Design)
2. ADD is linked in the Jira ticket description: "ADD: ADD-NNN-Title"
3. Engineer reads ADD before implementation (Phase 17/18)
4. During code review (Phase 19): architect checks implementation against ADD
5. If implementation diverges meaningfully from ADD:
   - Minor: note in PR review comment
   - Significant: update ADD before approving PR
```

---

## Workflow: Unplanned Architectural Decision During Implementation

Sometimes engineers encounter a decision during implementation that wasn't anticipated:

1. Engineer documents the decision in a Jira comment
2. Architect reviews and decides: ADR needed, ADD section, or just a PR comment?
3. If ADR: create in `designs/ADR/` before merging the PR
4. PR description references the ADR/ADD

---

## ADR Format (Michael Nygard template)

Default template for all ADRs. Four sections only — keep each one concise.

```markdown
# ADR-NNN: Title

## Status

Proposed | Accepted | Rejected | Deprecated | Superseded by ADR-NNN

## Context

What situation, constraint, or problem is forcing this decision?
What forces are at play (technical, political, social, project)?

## Decision

What is the change being made or the position being adopted?
Write it as an active statement: "We will …"

## Consequences

What becomes easier or harder after this decision?
Include positive, negative, and neutral consequences.
Note anything that will need to be revisited later.
```

**Rules:**

- One ADR per decision — don't bundle multiple choices into one record
- Status `Superseded` must reference the new ADR: "Superseded by ADR-031"
- Never edit a past ADR's Decision or Consequences — instead, write a new ADR that supersedes it
- Consequences must be honest: if there are known downsides, list them

---

## ADD Format

ADDs are implementation-focused — they answer "how" for a specific component, feature, or integration. They complement ADRs (which capture "why") and are the primary reference engineers read before touching the thing.

Structure inspired by [gvatsal60/high-level-design-docs](https://github.com/gvatsal60/high-level-design-docs), aligned with project ADD conventions:

### OKF Frontmatter

Every ADD has a YAML frontmatter block at the top. The `stacks` field is mandatory — it tells agents which tech stack conventions apply to this component:

```yaml
---
type: ADD
title: "ADD-NNN: Title"
description: One-sentence summary of what this component does.
tags:
  - add
  - short-slug
stacks:
  - go-backend        # implementation language / framework
  - ecs-deployment    # hosting / runtime
  - terraform-aws     # infra layer
references:
  - ADD-009           # internal: other ADDs this component depends on or must satisfy
  - ADR-015           # internal: decisions that govern this component
  - https://example.com/spec   # external: standards, RFCs, upstream docs
status: Draft         # Draft | Accepted | Deprecated | Superseded by ADD-NNN
date: YYYY-MM-DD
resource: designs/ADD/ADD-NNN-Title.md
---
```

**`stacks` field rules:**

- List every stack whose conventions directly govern this component's implementation. Use the exact slug from `stacks/` (e.g. `go-backend`, `typescript-react`, `python`, `terraform`, `terraform-aws`, `ecs-deployment`, `ai-ml`, `bdd-testing`).
- Stack categories to consider:
  - **Language/framework**: `go-backend`, `typescript-react`, `python`
  - **Infra**: `terraform`, `terraform-aws`, `ecs-deployment`
  - **Specialised**: `ai-ml`, `bdd-testing`, `owasp`, `fips-140-3`
- If the ADD is system-wide (architecture principle, legal template, encryption design) and not tied to a specific implementation stack, use `stacks: []`.
- A component may list multiple stacks (e.g. a feature with a Go API + React frontend + Terraform infra).

**How agents use `stacks`:**

When implementing or reviewing a story, the engineer and architect read the relevant ADDs from the Jira ticket references. For each ADD:
1. They read the `stacks` field to know which stack's conventions apply to this component.
2. They load those stack docs via `knowledge_reader` (e.g. `go-backend`, `terraform-aws`).
3. They apply those conventions — naming, structure, patterns — when implementing or reviewing the component.

This means an ADD for a Go API component explicitly signals "use Go conventions", and an ADD for a Python pipeline explicitly signals "use Python conventions" — even when both exist in the same software system.

**`references` field rules:**

- List every internal document (ADD-NNN, ADR-NNN) and external resource that a reader must load to understand or correctly implement this component.
- Internal IDs use the canonical prefix: `ADD-NNN` or `ADR-NNN` (3-digit, zero-padded). No file extension, no path.
- External entries are full URLs: `https://…`
- This is the machine-readable reference list. Agents load these after reading the ADD body. The `## References` section in the body can retain human-readable descriptions of the same links.
- ADRs that govern this component belong here even if they are also referenced in the SAD.
- Platform constraint documents (data handling rules, custody boundaries, access policies) must appear here so any agent reading this ADD automatically knows what constraints apply.
- Use `references: []` if this ADD has no dependencies on other docs.

**How agents use `references`:**

After reading an ADD, agents iterate its `references` list:
- `ADD-NNN` / `ADR-NNN` → load via `workspace_reader` from `designs/ADD/` or `designs/ADR/`
- `https://…` → note as external standard; fetch if needed for interpretation

This replaces the need to hardcode platform-specific knowledge (e.g. "load ADD-009") into crew task instructions. The ADD itself declares what else must be consulted.

---

### Body Format

````markdown
# ADD-NNN: Title

**Status:** Draft | Accepted | Deprecated | Superseded by ADD-NNN
**Date:** YYYY-MM-DD

---

## Overview

One paragraph. What is this component, why does it exist, what problem does it solve?
Not "how" yet — save that for Components and Interactions.

## Goals

| # | Goal |
|---|------|
| G1 | <specific, testable objective> |
| G2 | ... |

## Scope

### In scope
- ...

### Out of scope
- ... (prevents scope creep; points to where adjacent work lives)

## Architecture

High-level description of the design — the shape of the solution before the detail.

```mermaid
flowchart TB
  ...
```

## Components

### [Component A]

Responsibility, public interface, constraints.

### [Component B]

...

## Interactions

How components talk to each other. Show the happy path first, then key error/edge paths.

```mermaid
sequenceDiagram
  ...
```

## Considerations

**Trade-offs**: what was chosen and what was left on the table, and why.
**Security**: access patterns, encryption, trust boundaries.
**Scalability / Cost**: known limits and when they bite.
**Operational**: observability, runbook pointers, failure modes.

## Future Enhancements

Known limitations and planned follow-on work.
Signals what this design intentionally does not cover.

## References

- [ADR-NNN: Title](../ADR/ADR-NNN-Title.md)
- [ADD-NNN: Title](ADD-NNN-Title.md)

````

**Rules:**

- `stacks` in frontmatter is mandatory — every ADD must declare which tech stacks apply (or `[]` for system-wide docs)
- Overview is one paragraph — if it needs more, the scope is too large; split the ADD
- Goals must be testable: "users can do X" beats "improve Y"
- Out of scope is mandatory — it prevents scope creep and tells readers where else to look
- Diagrams are expected — mermaid preferred (renders in GitHub and most doc tools)
- Considerations must be honest about trade-offs chosen; if there were no alternatives considered, note that
- ADDs are updated when implementation diverges from design; the doc tracks the real thing, not the original intention

---

## Numbering Conventions

- ADRs: `ADR-NNN-Short-Title.md` (sequential, never reuse a number)
- ADDs: `ADD-NNN-Short-Title.md` (sequential, never reuse a number)
- Pad to 3 digits: `ADR-025`, `ADD-043`

---

## Reading ADD/ADR References in Code-Crew

The code-crew agents automatically extract ADD and ADR references from:

1. Jira ticket description — patterns like `ADD-018`, `ADR-025`
2. Jira ticket comments — design notes, architect comments

The extracted references are passed to all agents so they have design context during implementation and code review.

**Stack-aware ADD reading:** When an agent reads an ADD, it checks the `stacks` field in the frontmatter. It then loads the matching stack documents via `knowledge_reader` to apply the correct conventions for that component. Example: a ticket referencing `ADD-039` (stacks: `typescript-react`) and `ADD-001` (stacks: `go-backend`, `ecs-deployment`) tells the engineer to follow Go conventions for the container service and TypeScript conventions for the marketing site — even though both are in the same sprint.
