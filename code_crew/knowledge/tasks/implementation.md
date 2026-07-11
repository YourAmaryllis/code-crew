---
type: CrewAI Task
title: Implementation
description: Implement the feature across all required surfaces (backend, frontend, API spec, DB migrations) per the ADD and BDD spec
tags: [implementation, phase-17, phase-18, bdd-first]
timestamp: 2026-06-20T00:00:00Z
agent: engineer
context_agents:
  - architect
  - qa_lead
expected_output: >
  Concrete evidence that code was written and verified — NOT a plan. Required:
  1. FILES CHANGED block listing every file path created or modified (see format below).
  2. Build/typecheck output confirming 0 errors (use commands.build / commands.typecheck from structure.md).
  3. Test output confirming tests pass (use commands.test from structure.md).
  4. Final line: IMPLEMENTATION COMPLETE

  FILES CHANGED format (mandatory — manager will reject output without this):
  ```
  FILES CHANGED:
  - <relative/path/to/source-file>  (created|modified)
  - <relative/path/to/test-file>    (created|modified)
  - <integration/features/scenario-steps-file>  (created|modified)
  ```
  Manager verifies: (a) at least one non-test production file listed, (b) BDD step
  definition files listed if BDD scenarios exist, (c) all paths relative to repo root.
---

Implement the feature described in the sprint input, following the BDD scenarios as the contract.

**Step 1 — Load context.**
- Load the ADD identified in the architecture review via `knowledge_reader`
- For each ADD: read its `stacks` frontmatter field, then load each named stack document via `knowledge_reader` — the stack documents define the exact conventions, commands, and file naming for this technology
- Read `.code-crew/structure.md` via `workspace_reader` — the `## Project commands` section lists the exact build, test, lint, typecheck, and audit commands for this project; use those commands, do not assume any particular tool

Do not begin implementation without understanding the ADD. No ADD = flag as blocker.

**Step 2 — Review BDD scenarios.**
Read the qa_lead's finalized scenarios from context. Identify unit-level test cases implied by each scenario. Write test stubs before writing production code (follow the `bdd-implementation` function).

**Step 3 — Survey existing code.**
Use `code_index search` first to find comparable patterns by meaning — faster than listing directories:
- Search for the concept of what you're building (e.g. "handler validation middleware", "form component error state", "repository pattern")
- Use `search_ast` to confirm structural patterns in the codebase
- Only `read_file` files identified by these searches; match established patterns exactly

**Step 4 — Branch.**
Follow the `development-workflow` function for branching and commit format.
Use the issue key from the sprint input (e.g. `feature/<issue-key>-<slug>`):
- If the branch exists: check it out, review what was already done, continue from there
- If not: create it from the default branch

**Step 5 — Backend implementation (if in scope).**
- Write test stubs first (naming convention from the loaded stack document), then implement
- Follow the directory conventions from the architecture guide and the stack documents loaded in Step 1
- Follow the `coding-standards` function for language conventions, error handling, and interface design
- Run `commands.build` after every new file — fix errors before continuing
- Run `commands.test` — all tests must pass before committing
- **Wiring check (mandatory):** for every new production function, confirm at least one call site exists outside its own test file — a function only called from tests is dead code; add the call in the appropriate entry point before proceeding

**Step 6 — Frontend implementation (if in scope).**
Decide whether a design artifact is needed:
- Purely behavioural change (validation error, disabled state, existing component rewired): implement directly from BDD scenarios
- New visual layout or component: look for a design artifact in the ticket or repository (any format: attachment, link, mockup, designs/ doc) — if found, implement from it following the frontend stack document; if not found, note "Frontend skipped: no design artifact found" and continue to Step 7
- Run `commands.typecheck` (from structure.md) — no type errors before committing
- Verify ARIA labels, keyboard navigation, and colour contrast (WCAG 2.1 AA)

**Step 7 — Update API spec (if HTTP routes changed).**
Follow the `api-standards` function and run `commands.api_spec` from structure.md. If no routes changed, state "No API spec changes."

**Step 8 — DB migration (if schema changed).**
Follow the `db-schema` function. Use `DB_MIGRATION_TOOL` env (or detect from the migration directory) to create the migration stub. **Do NOT apply the migration** — that is a human + CI step. If no schema changes, state "No DB schema changes."

**Step 9 — Rebase.**
`git fetch origin && git rebase origin/<default-branch>`.

**Step 10 — List new infrastructure requirements.**
Any new environment variables, secrets, IAM permissions, or external service calls must be listed explicitly. The DevOps Lead uses this list. Format:
```
New infrastructure requirements:
- Env var: <VAR_NAME> (non-sensitive)
- Secret: /<service>/<env>/<name> (via the project's secret store)
- IAM: <action> on <resource-pattern>
```
If none: state "No new infrastructure requirements."

**Step 11 — Output FILES CHANGED block** (see expected output format above).

**On tool failure** — log the error, try once with an alternative, then skip and continue. Never use absolute paths in shell commands. Include unresolved failures in the output.

**Completion signal — mandatory.**
Final line must be exactly:
- `IMPLEMENTATION COMPLETE` — code written and verified
- `INCOMPLETE: <reason>` — could not finish; describe what remains
