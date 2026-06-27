---
type: Function Guide
title: Test Scaffolding
description: How to create BDD feature file stubs and step definition stubs
tags: [scaffold, bdd, gherkin, godog]
---

## Purpose

Scaffold creates *empty* feature file structure and step definition stubs so QA can fill in Gherkin steps before implementation begins. Steps must NOT be implemented yet — they will fail until the backend/frontend is built.

## Step 1 — Check what already exists

Use `workspace_reader` (`list_dir` or `find_files`) on `integration/features/` to see what feature files already exist. Do not recreate existing files.

## Step 2 — Create the feature file stub

Read `bdd-authoring` function guide for naming and tagging conventions.

File: `integration/features/<feature-slug>.feature`

```gherkin
Feature: <title from story>
  As a <role from story>
  I want <want from story>
  So that <benefit from story>

  @<jira-key-lowercase> @<domain> @api
  Scenario: <AC-1 happy path>
    # TODO: QA to write Gherkin steps

  @<jira-key-lowercase> @<domain> @api
  Scenario: <AC-1 error case>
    # TODO: QA to write Gherkin steps
```

One scenario stub per AC + one negative/error stub per AC.

## Step 3 — Create step definition stub

File: `integration/features/<feature-slug>_steps_test.go`

```go
package features

import (
    "github.com/cucumber/godog"
)

func init<Feature>Steps(ctx *godog.ScenarioContext) {
    // TODO: register step definitions for <Feature>
    // Scenarios to implement:
    //   - <AC-1 happy path>
    //   - <AC-1 error case>
}
```

Register in `main_test.go` InitializeScenario function if needed.

## Output

Report:
- Path of `.feature` file created
- Path of `_steps_test.go` file created
- Count of scenario stubs created (N per AC + N negatives)
- Reminder: QA fills in Gherkin steps; engineer implements step definitions alongside backend code
