---
name: SDLC-QA-TestReporting
description: Test report formats, Jira comment evidence, CI integration, and staging sign-off process
metadata:
  type: process
  role: qa
  phase: "15, 19, 20"
---

# Test Reporting

Test reports are the evidence that acceptance criteria have been met. They are attached to Jira tickets and reviewed by the Scrum Master during DoD check.

---

## Local Test Report Generation

### Go (Godog HTML)

```bash
# Run BDD suite and generate HTML report
go test ./... -v \
  --godog.format=html \
  --godog.output=reports/test-report.html \
  --godog.tags="@PROJ-92"
```

### TypeScript (Playwright HTML)

```bash
npx playwright test --reporter=html --grep @PROJ-92
# Report at playwright-report/index.html
```

### All stories in a sprint

```bash
# Run all BDD scenarios and produce combined report
go test ./... --godog.format=html --godog.output=reports/sprint-5-report.html
```

---

## CI Test Report

GitHub Actions publishes test reports as:
- Artifacts (downloadable HTML)
- Job summary (inline pass/fail table)
- PR check status (pass = green check, fail = red X)

The CI run URL serves as valid evidence for DoD when the run is publicly visible on the repo.

---

## Jira Evidence Comment

After a successful test run, post a comment on the Jira ticket:

```
BDD test run for PROJ-92: ✅ PASSED
Run: https://github.com/your-org/platform/actions/runs/XXXXXXX
Scenarios: 4 passing, 0 failing
Coverage: 
  - AC 1: ✅ Scenario "Successful registration triggers verification email"
  - AC 2: ✅ Scenario "Invalid email is rejected at registration"
  - AC 3: ✅ Scenario "Verification link expires after 24 hours"
```

The Scrum Master reads this comment during DoD check as evidence of completion.

---

## Staging Acceptance (Phase 20)

Before production promotion:

1. E2E suite runs against staging: `@e2e` tagged scenarios
2. Smoke test suite must pass: `@smoke` tagged scenarios
3. QA Lead reviews staging acceptance results
4. Sign-off comment added to the release Jira ticket:

```
Staging acceptance: ✅ PASSED
E2E run: [link]
Smoke tests: [link]
Date: YYYY-MM-DD
Sign-off: QA Lead name
```

Production promotion is blocked until staging acceptance is signed off.

---

## Test Failure Triage

When a BDD scenario fails:

1. Determine: test bug or product bug?
2. **Product bug**: create Jira bug with severity, steps to reproduce, actual vs expected
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
