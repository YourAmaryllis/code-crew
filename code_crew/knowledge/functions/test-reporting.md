---
name: SDLC-QA-TestReporting
description: Test report formats, issue tracker evidence comment, CI integration, and staging sign-off process
metadata:
  type: process
  role: qa
  phase: "15, 19, 20"
---

# Test Reporting

Test reports are the evidence that acceptance criteria have been met. They are attached to issue tracker tickets and reviewed by the Scrum Master during DoD check.

---

## Local Test Report Generation

Run the BDD suite filtered by the issue key and generate a report. Use `commands.test` from `.code-crew/structure.md`, passing the issue key tag. The exact command and report format depend on the active BDD stack (see the `bdd-testing` stack document).

Example output: an HTML report file or structured JSON that lists each scenario and its pass/fail status.

---

## CI Test Report

CI publishes test reports as:
- Artifacts (downloadable HTML or JSON)
- Job summary (inline pass/fail table)
- PR check status (pass = green check, fail = red X)

The CI run URL serves as valid evidence for DoD when the run is publicly visible on the repo.

---

## Issue Tracker Evidence Comment

After a successful test run, post a comment on the issue tracker ticket:

```
BDD test run for <issue-key>: PASSED
Run: <CI run URL>
Scenarios: N passing, 0 failing
Coverage:
  - AC 1: Scenario "<description>"
  - AC 2: Scenario "<description>"
  - AC 3: Scenario "<description>"
```

The Scrum Master reads this comment during DoD check as evidence of completion.

---

## Staging Acceptance (Phase 20)

Before production promotion:

1. E2E suite runs against staging: `@e2e` tagged scenarios
2. Smoke test suite must pass: `@smoke` tagged scenarios
3. QA Lead reviews staging acceptance results
4. Sign-off comment added to the release ticket:

```
Staging acceptance: PASSED
E2E run: <link>
Smoke tests: <link>
Date: YYYY-MM-DD
Sign-off: QA Lead name
```

Production promotion is blocked until staging acceptance is signed off.

---

## Test Failure Triage

When a BDD scenario fails:

1. Determine: test bug or product bug?
2. **Product bug**: create a bug ticket with severity, steps to reproduce, actual vs expected
3. **Test bug** (wrong step definition, environment issue): fix the test; do not close the scenario
4. Critical/High bugs: block the PR/story; fix before proceeding
5. Medium/Low bugs: create bug ticket, link to story, can proceed if agreed with PO

---

## Flaky Tests

Flaky tests (pass/fail non-deterministically) are as bad as failing tests:
- Mark with `@flaky` temporarily and create a fix ticket with High priority
- Do not merge code that makes existing tests flaky
- Fix within the same sprint or escalate to Tech Lead

---

## Test Metrics (per Sprint)

Tracked by QA Lead and reviewed in retrospective:
- Total BDD scenarios: authored, implemented, passing
- Bugs found in BDD vs. production (catch rate)
- Flaky test count (target: 0)
- Test run duration (target: < 10 min for unit + integration)
