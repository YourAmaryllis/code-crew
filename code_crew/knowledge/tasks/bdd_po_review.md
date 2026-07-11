---
type: CrewAI Task
title: BDD Spec Review — Product Owner
description: Product Owner reviews Gherkin scenarios against acceptance criteria and business intent
tags: [bdd, review, product-owner, acceptance-criteria, phase-14]
timestamp: 2026-06-20T00:00:00Z
agent: product_owner
context_agents:
  - qa_lead
expected_output: >
  APPROVED with a coverage confirmation listing each AC and its covering scenario(s), OR
  NEEDS REVISION with a specific list of: missing AC coverage, business logic issues, and
  suggested additions. No partial summaries.
---

Review the QA Lead's Gherkin BDD feature files for the story in the sprint input.

**Step 1 — Load the issue tracker ticket** (use the issue tracker tool).
Read the full story description and every acceptance criterion. These are the contract
you are checking the scenarios against.

**Step 2 — Read the feature files.**
Use `workspace_reader` to list and read the relevant feature files for this issue key
using the feature directory convention from the `bdd-authoring` function.

**Step 3 — Check AC coverage.**
Every acceptance criterion must have at least one Gherkin scenario. List any AC with no
corresponding scenario — this is a blocking gap.

**Step 4 — Check business correctness.**
Do the scenario steps reflect actual user-visible behaviour? Steps should read as plain
English description of what the user does and what they see — not technical implementation
details. Flag any step that is technically correct but misrepresents the business intent.

**Step 5 — Check completeness.**
Are there user paths, edge cases, or error messages the scenarios miss? Consider:
- Validation error messages shown to the user
- Permission boundary cases (unauthenticated, wrong role)
- Data boundary conditions (empty, max length, duplicate)
- User-facing feedback (success confirmations, warning messages)

**Step 6 — Check concreteness.**
Scenarios must use concrete values. Reject vague placeholders like `"<field>"` or `"some value"`.

**Output** — end with exactly one of:

```
APPROVED

Coverage confirmed:
- AC-1: covered by Scenario "..."
- AC-2: covered by Scenarios "..." and "..."
```

or:

```
NEEDS REVISION

Missing coverage:
- AC-N has no scenario for [specific case]

Business logic issues:
- Scenario "..." says "X" but the AC requires "Y"

Suggested additions:
- Scenario: [concrete suggestion]
```

Do NOT end with a planning statement. Output APPROVED or NEEDS REVISION — nothing else.
