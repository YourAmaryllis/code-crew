---
name: SDLC-QA-TestCoverage
description: Coverage requirements, test pyramid, what must be tested, and what tools are used
metadata:
  type: process
  role: qa
  phase: "14, 15, 20"
---

# Test Coverage Requirements

---

## Coverage Policy

Per ADR-010:

> **100% of acceptance criteria must be covered by BDD scenarios.**

This is a hard requirement, not a guideline. The Scrum Master's DoD check verifies coverage by running the BDD suite. "Scenarios exist" is not sufficient — the runner must execute and pass.

Additional coverage requirements:
- All domain-layer business logic must have unit test coverage
- Error paths must be tested (not just happy paths)
- Security-critical paths (auth, data access, input validation) must have explicit test cases

---

## Test Pyramid

```
         ┌─────────────────┐
         │   E2E (BDD)     │  ← Small number, high confidence
         ├─────────────────┤
         │ Integration BDD │  ← Service + DB scenarios
         ├─────────────────┤
         │   Unit Tests    │  ← Large number, fast, cheap
         └─────────────────┘
```

- Unit tests: fast, isolated, cover domain logic edge cases
- Integration tests: test service + database interactions; run with real DB in CI
- E2E tests: test full user flow through UI + backend; run in staging environment

---

## Testing Tools

| Layer | Language | Tool |
|-------|---------|------|
| Unit | Go | `go test` + `testify` |
| Unit | TypeScript | Jest + React Testing Library |
| Integration BDD | Go | Godog |
| E2E BDD | TypeScript | Playwright + Cucumber |
| API contract | Any | Hurl / httpyac |
| Performance | Any | k6 |

---

## CI Test Execution

All tests run in CI on every PR:

```yaml
# GitHub Actions
jobs:
  test:
    steps:
      - go test ./...                        # Unit tests
      - go test ./... --godog.tags="@smoke"  # Smoke BDD
      - npm test -- --coverage               # Portal unit tests

  e2e:
    # Runs against staging after promotion
    steps:
      - npx playwright test --grep @e2e
```

E2E tests run against the deployed staging environment after every staging promotion. They do not run on every PR (too slow, requires full stack).

---

## Test Report Requirements

For DoD verification, the test report must show:
1. Test run timestamp
2. Total scenarios / tests: pass / fail counts
3. Coverage of all `@PROJ-NNN` tagged scenarios for the story
4. Zero failures

Acceptable formats:
- Godog HTML report attached to Jira
- GitHub Actions run URL with visible test step output
- Playwright HTML report artifact in CI

See: [bdd-implementation.md`](bdd-implementation.md) for runner commands.

---

## Non-Functional Testing

| Type | When | Tool |
|------|------|------|
| Load testing | Before major releases | k6 |
| Security scanning | Every PR + nightly | govulncheck, npm audit, Trivy |
| Accessibility | Portal UI PRs | axe-playwright |
| Performance (Lighthouse) | Portal releases | Lighthouse CI |

Non-functional test failures are reported as bugs. Critical/High issues block release.

---

## Test Data Management

- Tests use isolated, reproducible test data (seeded per test run)
- No production data in test environments
- PHI must not appear in any test dataset — use synthetic data only
- Test data cleanup runs after each CI job
