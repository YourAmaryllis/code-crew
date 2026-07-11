---
name: SDLC-Engineer-BDDImplementation
description: How engineers implement BDD step definitions, annotate tests with issue keys, run the BDD runner, and attach results
metadata:
  type: process
  role: engineer
  phase: "15, 18"
---

# BDD Implementation

Engineers implement step definitions for BDD scenarios written by QA. Tests must be tagged with the issue key and run to generate a passing test report before a story can be closed.

---

## Step Definition Implementation

BDD scenarios are written by QA in Gherkin (`.feature` files). Engineers write the step definitions in the language appropriate for the test type:
- API/backend BDD: use the backend stack's BDD framework (see the active stack document)
- UI BDD: use the frontend stack's browser automation framework (see the active stack document)

The step definition file location and naming convention are defined in the active stack document.

---

## Test Tagging

Every BDD scenario must be tagged with the issue key and a category tag:

```gherkin
@<issue-key> @<feature-area> @<test-type>
Scenario: <description>
  Given ...
  When ...
  Then ...
```

Tag conventions:
- `@<issue-key>` — issue tracker key (required on every scenario)
- Feature area: a short domain label (e.g. `@auth`, `@billing`, `@search`)
- Test type: `@negative`, `@edge-case`, `@smoke` as appropriate

---

## Running the BDD Runner

Run locally before pushing. Use `commands.test` from `.code-crew/structure.md`, filtering by the issue key tag:

```bash
# Example — actual command is from commands.test in structure.md, filtered by tag
<commands.test> --tags="@<issue-key>"
```

The test runner must produce a report (HTML or JSON) that is attached as evidence for DoD.

---

## Test Report Requirements

For a story to pass the DoD check, the test report must show:
1. All BDD scenarios tagged `@<issue-key>` executed
2. All scenarios passing (green)
3. Report format: HTML or CI run URL with test step output

Acceptable evidence:
- Test report file attached to the issue tracker ticket
- CI run URL where the BDD suite passed
- Inline BDD runner output in an issue tracker comment

**"Scenarios exist"** is not sufficient — runner output showing pass/fail is required.

---

## Coverage Requirement

100% of acceptance criteria must be covered by BDD scenarios.

- Each AC maps to at least one Gherkin scenario
- Both happy path and relevant negative/edge cases covered
- QA authors the scenarios; engineers verify step definitions make them meaningful

---

## Issue Tracker Comment: Test Evidence

After BDD suite passes, add a comment to the issue tracker ticket:

```
BDD test run for <issue-key>: PASSED
Run: <CI run URL>
Scenarios: N passing, 0 failing
Coverage: All N ACs covered
```

The Scrum Master's DoD check reads this comment as evidence.

---

## Unit Tests

Unit tests are separate from BDD scenarios and cover:
- Domain logic edge cases
- Error handling paths
- Pure functions with complex logic

Unit test files live alongside the code they test. They do not need issue tracker tags.

Use `commands.test` from `.code-crew/structure.md` to run all unit tests.

Coverage target: no specific percentage — all business logic in the domain layer must be tested. CI reports coverage; significant drops flag a review.
