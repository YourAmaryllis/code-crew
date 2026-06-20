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

**Before writing**, use the `sop_reader` tool to load SOP-3-Dev-Process (Phase 14 section)
and ADR-028 to confirm the API vs UI scope split for this feature.

**Coverage requirements** (ADR-010: 100% BDD requirement coverage):
- Every acceptance criterion in the Jira story maps to at least one scenario
- Happy path covered
- All significant alternative paths covered
- Error and boundary cases covered
- Security-relevant scenarios included (invalid input, unauthorized access, data boundary)

**Annotation requirements** (DoD §2):
- Each scenario tagged with the Jira key: `@looplat-72` or `@cto-XX`
- Each scenario tagged with a domain category: `@dataset`, `@auth`, `@fhir`, `@upload`, etc.
- API tests tagged `@api`; UI interaction tests tagged `@ui`

**File naming**:
- API BDD: `integration/features/<feature-slug>.feature`
- UI BDD: `integration/features/<feature-slug>_ui.feature`

**Do not duplicate** what the other test type already covers (ADR-028). If API tests
cover all data matrix outcomes, the UI feature file tests one representative flow plus
any shared UI controls.

Produce the full `.feature` file content and a coverage matrix table:

| Acceptance Criterion | Scenario(s) | Status |
|---------------------|-------------|--------|
| AC-1 | Scenario: ... | ✓ |

**After writing**, use the `bdd_runner` tool to run the feature files for a syntax and compilation check. Scenarios will fail (implementation isn't done) — that is expected. Report the runner output in your summary so the backend developer can see what test IDs will need to pass.
