---
type: CrewAI Task
title: Project Exploration — Tests, CI/CD, and Compliance
description: Discover test suites, document CI/CD workflow purposes, and confirm compliance standards.
tags: [explore, testing, cicd, compliance]
agent: architect
expected_output: >
  Three DISCOVERY_BEGIN/END blocks: test_structure, cicd_workflows, compliance_standards.
  Ends with TESTS COMPLETE.
---

You are documenting test suites, CI/CD workflows, and compliance standards.

Use `workspace_reader` throughout. **IMPORTANT: Limit tool calls aggressively — read at most
8 files total across the entire task. Prioritise: Makefile (test targets), one workflow file,
one feature file, one compliance doc.**

---

## Step 1 — Test structure discovery

**Goal**: Document every test suite so an engineer knows where tests live and how to run them.

1. If a `Makefile` was detected, read it and list targets containing `test`, `bdd`,
   `integration`, `smoke`, or `e2e`. *(1 tool call)*
2. Use `find_files` to locate one `*.feature` file (BDD) and one `*_test.go` or `*.test.ts`
   file (unit). Note their directories — do not read them. *(2 tool calls)*
3. Look for test config files (`jest.config.*`, `vitest.config.*`, `pytest.ini`,
   `playwright.config.*`) using `find_files`. Note their presence — do not read them. *(1 tool call)*

Use the BDD feature dirs and test dirs from context as starting points.

Output:
```
DISCOVERY_BEGIN: test_structure
## Test structure

### <Suite name> — <type>

- **Location**: `<discovered path>`
- **Framework**: `<framework>`
- **Run all**: `<command from Makefile or standard command>`
- **Run single**: `<command>`
- **Config**: `<config file if found>`

[one section per distinct test suite]
DISCOVERY_END: test_structure
```

---

## Step 2 — CI/CD workflow analysis

If GitHub Actions was detected, read **at most 2** workflow files (prioritise deploy/release
workflows). *(2 tool calls)*

Output:
```
DISCOVERY_BEGIN: cicd_workflows
## CI/CD workflows

### GitHub Actions (`.github/workflows/`)

| Workflow file | Trigger | Purpose | Environment |
|--------------|---------|---------|-------------|
| `<filename>` | <trigger> | <purpose> | <env> |

**Notes**:
- <any important patterns>
DISCOVERY_END: cicd_workflows
```

---

## Step 3 — Compliance standards

The context includes **Phase 1 compliance standards** detected by keyword scan.
Read at most **1 document** to confirm the primary standard. *(1 tool call)*

Output:
```
DISCOVERY_BEGIN: compliance_standards
## Compliance standards

**Detected and confirmed**:
- <STANDARD> — confirmed in `<file>`

**Not detected** (no mentions found):
- <list remaining>

**Files scanned**: `<file>`
DISCOVERY_END: compliance_standards
```

---

## On tool failure

Log the error and continue. Stop using tools once you reach the 8-call limit —
synthesise from what you have and the context provided.

---

## Final step

Output exactly:
```
TESTS COMPLETE
```
