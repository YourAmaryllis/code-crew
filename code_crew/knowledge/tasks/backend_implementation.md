---
type: CrewAI Task
title: Backend Implementation
description: Implement backend feature per ADD, with unit tests, following trunk-based conventions
tags: [backend, implementation, phase-18, go, python, bdd-first]
timestamp: 2026-06-17T00:00:00Z
agent: backend_developer
context_agents:
  - tech_lead
  - qa_engineer
expected_output: >
  Implementation plan with: proposed file paths and structure, key function/method
  signatures, unit test stubs (from the QA engineer's BDD spec), branch name, and
  commit message template. If code generation is in scope, the full implementation
  with passing unit tests.
---

Implement the backend feature described in the sprint input.

**Step 1 — Read the ADD.** Use the `sop_reader` tool to load the technical design
document (ADD) identified by the tech lead in the architecture review. Do not begin
implementation without understanding the design. If no ADD exists for this surface,
flag it — the tech lead must create one or confirm the existing ADD covers it.

**Step 2 — Confirm unit test spec.** Review the QA engineer's BDD scenarios and
identify the unit-level test cases implied by them. List the unit test stubs you will
implement before writing production code.

**Step 3 — Plan the implementation.** Propose:
- File paths following the ADD's recommended structure
- Key function signatures and interfaces
- Database schema changes (if any) as migration stubs
- Environment variable names for any new configuration

**Step 4 — Produce implementation.** Write production code and unit tests. Follow:
- Idiomatic Go or Python depending on the component (check the ADD)
- No comments except where the WHY is non-obvious
- Error handling only at system boundaries (validate user input, external API responses)
- No hardcoded values; all configuration via env vars
- No secrets in code

**Step 5 — Confirm branch and commit format.**
- Branch: `feature/<JIRA-KEY>-<slug>` (short-lived, off `main`)
- Commit subject: `<type>(<scope>): <description> [REQ:<REQ-ID>] <JIRA-KEY>`
- Rebase from `main` before every push

Output the implementation plan and, if producing code, the full implementation with
unit tests. Flag any open questions for human review before merge.
