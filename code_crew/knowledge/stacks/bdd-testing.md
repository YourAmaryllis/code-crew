---
name: Stack-BDDTesting
description: BDD test design principles, environment management, scenario sequencing, and Godog conventions for integration and E2E tests
metadata:
  type: stack
  language: go
  framework: godog
  tags: [bdd, godog, integration, e2e, testing]
  detect-files:
    - "integration/features/**/*.feature"
    - "integration/suite_test.go"
---

# Stack: BDD Testing

## Framework

| Item | Tool/Convention |
|------|----------------|
| BDD runner | Godog v0.14+ |
| Feature files | `integration/features/<domain>/<slug>.feature` |
| Step definitions | `integration/steps/<domain>_steps.go` |
| Fixtures | `integration/fixtures/<feature-slug>.sql` |
| Required tags | `@<jira-key>` `@<domain>` `@api` or `@ui` |

---

## Design Principles

### 1. Fail Fast

Stop the scenario on the first step failure. Do not continue to subsequent steps when a
precondition has not been met — the remaining steps produce misleading output.

Godog's default behaviour is fail-fast. Never configure `ContinueOnStepFailure`.

---

### 2. Feature-Level Environment Reset

Each `Feature` resets the database to a known state before any of its scenarios run.
A seed-based internal HTTP API performs the reset:

```
POST /internal/test/reset
{ "seed": "<feature-slug>" }
```

**This endpoint MUST be disabled in staging and production.** It activates only when
`TEST_RESET_ENABLED=true` is set in the environment.

Seed data lives in `integration/fixtures/<feature-slug>.sql`. Keep seed data minimal —
only the rows required for the feature's scenarios.

The reset runs **once per Feature** via the `BeforeFeature` hook:

```go
suite.BeforeFeature(func(f *godog.Feature) {
    if os.Getenv("TEST_RESET_ENABLED") != "true" {
        return
    }
    resetTestEnvironment(f.Name) // POSTs to /internal/test/reset
})
```

Never reset per-scenario. It is expensive and breaks sequential scenario dependencies
(see Principle 3).

---

### 3. Sequential Scenario Dependency

Scenarios within a feature file are ordered intentionally. Each scenario may assume:
- All previous scenarios in the file have passed
- Their side effects (database rows, created resources) are still present

Example ordering for a "create dataset" feature:
1. Unauthenticated request is rejected — no DB state needed
2. Authenticated user creates a dataset — creates a row, returns an ID
3. Dataset appears in the list — depends on the row from step 2
4. Update the dataset — depends on the row from step 2
5. Delete the dataset — depends on the row from step 2

This avoids per-scenario setup/teardown and allows tests to verify full lifecycle flows.

**Consequence**: Always run the full feature file. Never run scenarios in isolation unless
tagged `@isolated`. Never shuffle scenario order.

---

### 4. UI Test Navigation Shortcut

For `@ui` scenarios, it is acceptable to call the API directly to set up preconditions that:
- Are **not** part of the feature under test, AND
- Cannot be seeded via the fixture file (e.g. require a live multi-step workflow to execute)

Example: a dataset submission feature does not need to navigate through the registration
flow. It can call `POST /api/v1/registrations` directly to create a registered user, then
navigate the browser to the dataset page.

Mark such API setup steps in the step definition:
```go
// ponytail: direct API call to bypass UI nav; registration is not the feature under test
```

---

## File Layout

```
integration/
  features/
    <domain>/
      <slug>.feature         # API integration tests (@api)
      <slug>_ui.feature      # UI E2E tests (@ui)
  steps/
    <domain>_steps.go        # step definitions per domain
    common_steps.go          # shared: auth, HTTP client, browser driver
  fixtures/
    <feature-slug>.sql       # seed data loaded by reset endpoint
  suite_test.go              # Godog suite init + BeforeFeature / AfterSuite hooks
```

---

## Tagging Requirements

Every scenario must have:

| Tag | Required | Example |
|-----|----------|---------|
| Issue key | Yes | `@<issue-key>` (lowercase, hyphenated) |
| Domain area | Yes | `@auth` `@billing` `@search` (a short label for the feature area) |
| Surface | Yes | `@api` or `@ui` |
| Smoke | Optional | `@smoke` — critical path; always run in CI |
| Isolated | Optional | `@isolated` — stateless; can run in any order |

---

## Running Tests

```bash
# All scenarios for an issue key
cd integration && go test ./... -tags integration -run TestSuite \
  -- --godog.tags="@<issue-key>"

# Smoke tests only (CI critical path)
go test ./... -tags integration -run TestSuite -- --godog.tags="@smoke"

# API integration tests for a domain
go test ./... -tags integration -run TestSuite -- --godog.tags="@<domain> and @api"

# UI E2E (requires browser driver running)
go test ./... -tags e2e -run TestSuite -- --godog.tags="@<issue-key> and @ui"
```

**Required environment variables:**

| Variable | Purpose |
|----------|---------|
| `TEST_RESET_ENABLED=true` | Enables reset endpoint — never set in staging/prod |
| `API_BASE_URL` | Base URL for the service under test |
| `TEST_DB_URL` | Direct DB connection for fixture validation |

---

## Step Definition Conventions

```go
func InitializeScenario(ctx *godog.ScenarioContext) {
    ctx.Step(`^an authenticated user with role "([^"]*)"$`, iAmAuthenticatedWithRole)
    ctx.Step(`^I submit the dataset form with title "([^"]*)"$`, iSubmitDatasetForm)
    ctx.Step(`^the dataset "([^"]*)" appears in the list$`, datasetAppearsInList)
}
```

- One step definition file per domain in `integration/steps/`
- Shared HTTP client and auth helpers in `common_steps.go`
- Use concrete values in steps — no `<field>` template placeholders
- Step functions return `error` — return `nil` to pass, return an error to fail
