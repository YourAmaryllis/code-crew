---
name: SDLC-Engineer-BDDImplementation
description: How engineers implement BDD step definitions, annotate tests with Jira keys, run the BDD runner, and attach results
metadata:
  type: process
  role: engineer
  phase: "15, 18"
---

# BDD Implementation

Engineers implement step definitions for BDD scenarios written by QA. Tests must be tagged with the Jira key and run to generate a passing test report before a story can be closed.

---

## Step Definition Implementation

BDD scenarios are written by QA in Gherkin (`.feature` files). Engineers write the step definitions in Go or TypeScript.

### Go (Godog)

```go
// features/email_verification_test.go
func InitializeScenario(ctx *godog.ScenarioContext) {
    ctx.Step(`^a user registers with email "([^"]*)"$`, registerWithEmail)
    ctx.Step(`^the system sends a verification email$`, systemSendsVerificationEmail)
    ctx.Step(`^the user clicks the verification link$`, clickVerificationLink)
    ctx.Step(`^the account is marked as verified$`, accountIsVerified)
}

func registerWithEmail(email string) error {
    // implementation
}
```

### TypeScript (Playwright/Cucumber)

```typescript
// features/step-definitions/email-verification.ts
Given('a user registers with email {string}', async (email: string) => {
    await page.goto('/register');
    await page.fill('[data-testid="email"]', email);
    await page.click('[data-testid="submit"]');
});
```

---

## Test Tagging

Every BDD scenario must be tagged with the Jira key and a category tag:

```gherkin
@PROJ-92 @authentication @registration
Scenario: Email verification required on registration
  Given a user registers with email "user@example.com"
  When the registration form is submitted
  Then the system sends a verification email
  And the account is pending verification

@PROJ-92 @authentication @negative
Scenario: Invalid email rejected at registration
  Given a user attempts to register with "not-an-email"
  When the registration form is submitted
  Then a validation error is displayed
```

Tag conventions:
- `@PROJ-NNN` — Jira key (required on every scenario)
- Feature area: `@authentication`, `@billing`, `@portal`, etc.
- Test type: `@negative`, `@edge-case`, `@smoke`

---

## Running the BDD Runner

Run locally before pushing:

```bash
# Go — run scenarios tagged with a Jira key
go test ./... -v --godog.tags="@PROJ-92"

# All BDD scenarios
go test ./... -v --godog.format=html --godog.output=test-report.html

# TypeScript / Playwright
npx playwright test --grep @PROJ-92
```

The test runner must produce a report (HTML or JSON) that is attached as evidence for DoD.

---

## Test Report Requirements

For a story to pass the DoD check, the test report must show:
1. All BDD scenarios tagged `@PROJ-NNN` executed
2. All scenarios passing (green)
3. Report format: Godog HTML, Playwright HTML, or CI run URL with test step output

Acceptable evidence:
- `test-report.html` attached to the Jira ticket
- GitHub Actions run URL where the BDD suite passed
- Inline BDD runner output pasted into a Jira comment

**"Scenarios exist"** is not sufficient — runner output showing pass/fail is required.

---

## Coverage Requirement

Per ADR-010: 100% of acceptance criteria must be covered by BDD scenarios.

- Each AC maps to at least one Gherkin scenario
- Both happy path and relevant negative/edge cases covered
- QA authors the scenarios; engineers verify step definitions make them meaningful

---

## Jira Comment: Test Evidence

After BDD suite passes, add a Jira comment:

```
BDD test run for PROJ-92: PASSED
Run: https://github.com/your-org/platform/actions/runs/XXXXXXX
Scenarios: 4 passing, 0 failing
Coverage: All 3 ACs covered
```

The Scrum Master's DoD check reads this comment as evidence.

---

## Unit Tests

Unit tests are separate from BDD scenarios and cover:
- Domain logic edge cases
- Error handling paths
- Pure functions with complex logic

Unit test files live alongside the code they test. They do not need Jira tags.

```bash
# Run all unit tests
go test ./...
npm test -- --coverage
```

Coverage target: no specific percentage — all business logic in the domain layer must be tested. CI reports coverage; significant drops flag a review.
