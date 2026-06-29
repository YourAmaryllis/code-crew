---
type: CrewAI Task
title: Code Review
description: Post-implementation code review — clean architecture, no hardcoding, branch/commit/PR format, and overall correctness
tags: [code-review, architecture, quality, phase-18]
timestamp: 2026-06-17T00:00:00Z
agent: tech_lead
context_agents:
  - engineer
  - devops_lead
expected_output: >
  A Code Review Report with: per-finding entries (severity, file/line, description, fix),
  branch/commit/PR format check (PASS or FAIL with corrections needed), overall verdict
  (APPROVED / CHANGES REQUESTED), and specific action items for each finding.
---

Review the implementation from the engineer. The engineer's output includes a `FILES CHANGED:` block listing every file they created or modified.

**Step 0 — Read the implementation output and load every changed file.**
1. Find the `FILES CHANGED:` block in the engineer's output. If it is missing or empty, that is a Critical finding — output `INCOMPLETE: engineer did not provide FILES CHANGED block` and stop.
2. Use `workspace_reader` to read each file listed. Do not rely solely on the text summary — read the actual code.
3. Verify BDD step definition files are present in the list. If BDD scenarios exist for this ticket but no step definition file was listed or created, that is a Critical finding.

**Step 0.5 — Run BDD tests (if step definitions exist).**
Use the `bdd_runner` tool to execute the BDD feature files for this story. Include results:
- All pass → mark "BDD: PASS" and proceed.
- Failures → distinguish logic bugs (implementation) vs. missing step definitions. A failing BDD test is a Critical finding that blocks APPROVED.

**Step 1 — Clean architecture.**
Check that the implementation follows the platform's layered structure:

- HTTP handlers contain no business logic — they parse input, call a service/handler
  function, and write the response. Business logic lives in service or domain layers.
- No cross-package imports that violate the dependency direction (check the ADD for the
  component's intended structure).
- No duplicated logic that should be a shared utility — but do not introduce premature
  abstractions for one-off cases. Three similar lines beat a premature helper.
- Functions and methods have a single clear responsibility.
- **Dead production code (Critical):** For each new production function in the `FILES CHANGED`
  list, run `grep -rn "<FunctionName>" .` and verify at least one call site exists outside
  that function's own file and test file. A new validation gate, helper, or integration
  function that is only referenced by its tests is dead code — the feature is not active at
  runtime. This is a Critical finding: list every unwired function and the entry point where
  the call must be added.

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

**On tool failure** — log the error, try once with an alternative (list parent dir, use `find_files` before `read_file`), then skip and continue. Never use absolute paths in shell commands. If critical context is unavailable, output `INCOMPLETE: <reason>` instead of a verdict.

**Step 4b — Update structure.md**

After reading FILES CHANGED, check if the implementation introduced structure not yet in
`.code-crew/structure.md`. Use what you can see in the changed files — do not guess.

What to check:
- A new directory was created under a service → may need an entry in `## Code structure`
- A test file appeared in a location not previously documented → update `## Test structure`
- A new script was added under `scripts/` that runs tests → update the relevant test suite's
  "Scripts available" line in `## Test structure`
- A new top-level component or service directory was created → add to `## Components`
- A new command is needed to build/test the new code → add to `## Project commands`

How to update:
1. Read `.code-crew/structure.md` using `workspace_reader`
2. Make the smallest correct addition using `platform_shell` —
   append only the new lines to the relevant section
3. Do NOT rewrite the whole file. `/explore` is responsible for full regeneration.

Skip this step if FILES CHANGED contains no structure that is absent from structure.md.

**Step 5 — Overall verdict.**
- **APPROVED**: no Critical or High findings; Minor findings listed as non-blocking suggestions.
- **CHANGES REQUESTED**: one or more Critical/High findings that must be resolved before merge.

List every finding with: severity (Critical / High / Medium / Minor), file path (if applicable),
description, and required fix.

If you cannot complete the review (tools unavailable, missing context, etc.), output `INCOMPLETE: <reason>` instead of APPROVED/BLOCKED.
