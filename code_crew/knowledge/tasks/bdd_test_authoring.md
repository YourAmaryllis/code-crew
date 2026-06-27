---
type: CrewAI Task
title: BDD Test Authoring
description: Write Gherkin feature files covering all acceptance criteria before implementation
tags: [bdd, gherkin, testing, phase-14, coverage]
timestamp: 2026-06-17T00:00:00Z
agent: qa_engineer
context_agents:
  - scrum_master
  - tech_lead
expected_output: >
  One or more Gherkin .feature files (full content, ready to commit) covering all
  acceptance criteria. A coverage matrix mapping each acceptance criterion to at least
  one scenario. File paths follow the integration/features/ convention.
---

Write Gherkin BDD feature files for the user story in the sprint input.

**Before writing**, use the `knowledge_reader` tool to load `bdd-authoring` to confirm
file naming, tagging conventions, and the API vs UI scope split for this feature.

**Check what already exists.** Use `workspace_reader` with `list_dir` on
`integration/features/` to see existing feature files. If a feature file already covers
this Jira key, read it and extend it rather than recreating it.

**Coverage requirements** (100% AC coverage mandatory):
- Every acceptance criterion maps to at least one scenario
- Happy path covered
- All significant alternative paths covered
- Error and boundary cases covered
- Security-relevant scenarios included (invalid input, unauthorized access, data boundary)

**Annotation requirements**:
- Each scenario tagged with the Jira key (lowercase): `@looplat-92` or `@cto-XX`
- Each scenario tagged with a domain category: `@dataset`, `@auth`, `@fhir`, `@registration`, etc.
- API tests tagged `@api`; UI interaction tests tagged `@ui`

**File naming**:
- API BDD: `integration/features/<feature-slug>.feature`
- UI BDD: `integration/features/<feature-slug>_ui.feature`

Do **not** duplicate coverage between API and UI files. If API tests cover all data matrix
outcomes, the UI file tests one representative flow plus any shared UI controls.

**Do NOT run the BDD test suite.** Implementation has not started — all scenarios will
fail by design. Running tests here is incorrect and a waste of iterations. The `bdd_runner`
is called during the DoD check *after* implementation is complete.

Produce the full `.feature` file content and a coverage matrix:

| Acceptance Criterion | Scenario(s) | File | Tag |
|---|---|---|---|
| AC-1 | Scenario: ... | feature-slug.feature | @looplat-92 |

**Completion signal — required.**
End your output with exactly one of:
- `TASK COMPLETE` — you have produced the full output described above.
- `INCOMPLETE: <reason>` — you could not finish (missing data, tool failure, ambiguity).

Do NOT end with a planning statement or partial summary.
