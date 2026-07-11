---
type: CrewAI Task
title: BDD Spec Review — Architect
description: Architect reviews Gherkin scenarios against ADD contracts, security coverage, and technical feasibility
tags: [bdd, review, architect, add, security, phase-14]
timestamp: 2026-06-20T00:00:00Z
agent: architect
context_agents:
  - qa_lead
expected_output: >
  APPROVED with notes on technical alignment, OR NEEDS REVISION with a specific list of:
  ADD contract gaps, missing security scenarios, and test structure concerns. No partial summaries.
---

Review the QA Lead's Gherkin BDD feature files for the story in the sprint input.

**Step 1 — Load the ADD** (`knowledge_reader`).
Identify the ADD referenced in the architecture review for this story. Load it to understand
the API contract (endpoints, request/response shapes, error codes).

**Step 2 — Load the issue tracker ticket** (use the issue tracker tool).
Confirm the feature scope and any technical constraints in the ticket description.

**Step 3 — Read the feature files.**
Use `workspace_reader` to list and read the relevant feature files for this issue key
using the feature directory convention from the `bdd-authoring` function.

**Step 4 — Check ADD alignment.**
API scenarios must test the endpoints defined in the ADD:
- Correct HTTP methods and paths
- Request shapes match ADD specifications
- Response assertions match the ADD contract (status codes, field names)
- Error responses match the ADD error definitions

Flag any scenario that tests an endpoint or response shape not in the ADD — the ADD
may need updating, or the scenario may be wrong.

**Step 5 — Check security coverage.**
Every feature that accepts user input or accesses protected resources must have:
- At least one unauthenticated request scenario (401 expected)
- At least one wrong-role scenario (403 expected) if the feature has role restrictions
- Input validation scenarios covering injection-relevant inputs (SQL metacharacters, XSS vectors)

**Step 6 — Check test structure feasibility.**
- Can the scenarios use the feature-level reset (single `POST /internal/test/reset`)?
- Is the sequential ordering correct — stateless/negative first, stateful lifecycle later?
- Does the seed data implied by the scenarios exist or need documenting?

**Output** — end with exactly one of:

```
APPROVED

ADD alignment: confirmed against [ADD-NNN]
Security coverage: [list of security scenarios found]
Test structure: feature reset is feasible with seed [feature-slug]
```

or:

```
NEEDS REVISION

ADD contract gaps:
- Scenario "..." tests endpoint "X" but the ADD defines it as "Y"
- Response assertion for field "Z" does not match ADD schema

Missing security scenarios:
- No unauthenticated scenario for [endpoint]
- No wrong-role scenario; feature has [role restriction per ADD]

Test structure concerns:
- Scenario "..." depends on state that cannot be seeded via feature reset
```

Do NOT end with a planning statement. Output APPROVED or NEEDS REVISION — nothing else.
