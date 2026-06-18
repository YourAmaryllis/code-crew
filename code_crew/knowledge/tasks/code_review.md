---
type: CrewAI Task
title: Code Review
description: Post-implementation code review — clean architecture, no hardcoding, branch/commit/PR format, and overall correctness
tags: [code-review, architecture, quality, phase-18]
timestamp: 2026-06-17T00:00:00Z
agent: tech_lead
context_agents:
  - backend_developer
  - frontend_developer
expected_output: >
  A Code Review Report with: per-finding entries (severity, file/line, description, fix),
  branch/commit/PR format check (PASS or FAIL with corrections needed), overall verdict
  (APPROVED / CHANGES REQUESTED), and specific action items for each finding.
---

Review the implementation outputs from the backend and frontend developers.
Use `platform_shell` to inspect actual code where needed (grep, cat, git log).

**Step 1 — Clean architecture.**
Check that the implementation follows the platform's layered structure:

- HTTP handlers contain no business logic — they parse input, call a service/handler
  function, and write the response. Business logic lives in service or domain layers.
- No cross-package imports that violate the dependency direction (check the ADD for the
  component's intended structure).
- No duplicated logic that should be a shared utility — but do not introduce premature
  abstractions for one-off cases. Three similar lines beat a premature helper.
- Functions and methods have a single clear responsibility.

**Step 2 — No hardcoding.**
Check that the implementation contains no:

- Hardcoded URLs, hostnames, or port numbers (must be env vars or config)
- Hardcoded credentials, tokens, API keys, or secrets of any kind
- Hardcoded timeouts or limits that should be configurable
- Hardcoded environment names (e.g. `"production"`, `"staging"` as string literals in logic)
- Magic numbers or strings without a named constant or clear comment explaining the value

Use `platform_shell` to grep: `grep -rn "localhost\|127\.0\.0\|hardcode\|TODO.*secret"` etc.

**Step 3 — Branch, commit, and PR format.**
Verify the proposed branch name and commit subject follow SOP-DoD Section 3:

- Branch: `feature/<JIRA-KEY>-<slug>` or `fix/<JIRA-KEY>-<slug>`
- Commit: `<type>(<scope>): <description> [REQ:<REQ-ID>] <JIRA-KEY>`
- PR title matches commit subject format
- If the backend or frontend developer proposed a non-conforming name, provide the corrected version.

**Step 4 — Error handling and observability.**
- Errors are handled at system boundaries only (user input, external APIs). Internal functions
  return errors but do not log them — the boundary caller decides whether to log.
- Security-relevant events (auth failures, permission denials, data writes) are logged.
- No `fmt.Println`, `console.log`, or debug output left in production paths.

**Step 5 — Overall verdict.**
- **APPROVED**: no Critical or High findings; Minor findings listed as non-blocking suggestions.
- **CHANGES REQUESTED**: one or more Critical/High findings that must be resolved before merge.

List every finding with: severity (Critical / High / Medium / Minor), file path (if applicable),
description, and required fix.
