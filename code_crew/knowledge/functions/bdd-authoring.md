---
type: Function Guide
title: BDD Test Authoring
description: How to write and organize Gherkin BDD feature files for this platform
tags: [bdd, gherkin, godog, testing]
---

## Where BDD tests live

```
integration/                  — separate Go module (integration/go.mod)
  features/
    <feature-slug>.feature              — API-level BDD scenarios
    <feature-slug>_ui.feature          — UI interaction scenarios (ADR-028)
    <feature-slug>_steps_test.go       — step definitions
  go.mod
  main_test.go                          — godog test runner entry point
```

## File naming rules (ADR-028)

- **API tests**: `integration/features/<feature-slug>.feature`
- **UI tests**: `integration/features/<feature-slug>_ui.feature`
- Feature slug derived from the story domain: `<feature-area>_<description>` (e.g. `auth_email_verification`)

Do **not** duplicate coverage between API and UI files. If the API file tests all data matrix outcomes, the UI file tests one representative path plus any shared UI controls.

## Scenario structure

```gherkin
Feature: <feature name from story>
  As a <role>
  I want <capability>
  So that <benefit>

  @<jira-key-lowercase> @<domain-category> @api
  Scenario: <descriptive name>
    Given <precondition>
    When <action>
    Then <expected outcome>

  @<jira-key-lowercase> @<domain-category> @api
  Scenario: <error or boundary case>
    Given <precondition>
    When <invalid action>
    Then <error response>
```

## Required tags on every scenario

1. **Issue key** (lowercase with hyphen): `@<issue-key>` (e.g. `@proj-92`)
2. **Domain category**: a short label for the feature area (e.g. `@auth`, `@billing`, `@search`)
3. **Scope marker**: `@api` for API-level tests, `@ui` for UI interaction tests

## Coverage requirement (ADR-010)

100% AC coverage is mandatory. Every acceptance criterion maps to at least one scenario:

- Happy path
- Alternative paths (e.g. optional field omitted)
- Error cases (invalid input, unauthorized)
- Boundary conditions

## What to write — and what NOT to do

**Write the scenarios only.** Do not run the test suite after writing — implementation has not started yet. The `bdd_runner` is for the DoD check after implementation, not during authoring.

Use concrete values in scenarios, not placeholders:

```gherkin
# Good
Given a user with no verified email address
# Bad  
Given a user with <some configuration>
```

## Coverage matrix output

After writing feature files, produce a table:

| Acceptance Criterion | Scenario(s) | File | Tag |
|---|---|---|---|
| AC-1: Field X is required | Scenario: Missing field X returns 400 | feature-slug.feature | @<issue-key> |

## Running tests (for reference — done at DoD, not authoring)

Use `commands.test` from `.code-crew/structure.md`, filtered by the issue key tag.
The exact command depends on the active BDD stack (see the `bdd-testing` stack document).
