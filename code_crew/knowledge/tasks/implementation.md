---
type: CrewAI Task
title: Implementation
description: Full-stack implementation of backend (Go) and frontend (React/TypeScript) per ADD and BDD spec
tags: [implementation, backend, frontend, go, react, typescript, phase-17, phase-18, bdd-first]
timestamp: 2026-06-20T00:00:00Z
agent: engineer
context_agents:
  - architect
  - qa_lead
expected_output: >
  Concrete evidence that code was written and verified — NOT a plan. Required:
  1. FILES CHANGED block listing every file path created or modified (see format below).
  2. Build/typecheck output confirming 0 errors (use the project's `commands.build` or `commands.typecheck` from structure.md).
  3. Test output confirming tests pass (use the project's `commands.test` from structure.md).
  4. Final line: IMPLEMENTATION COMPLETE
  If frontend is skipped due to no Figma link, state that explicitly and still provide (1)-(4) for backend.

  FILES CHANGED format (mandatory — manager will reject output without this):
  ```
  FILES CHANGED:
  - <relative/path/to/file.go>  (created|modified)
  - <relative/path/to/file_test.go>  (created|modified)
  - <integration/features/scenario_steps_test.go>  (created|modified)
  ```
  The manager will verify: (a) at least one non-test production file is listed, (b) BDD step
  definition files are listed if BDD scenarios exist for this ticket, (c) all paths are relative
  to the repo root.
---

Implement the feature described in the sprint input, covering both backend and frontend
surfaces as required by the story and ADD.

**Step 1 — Load context.** Use `knowledge_reader` to load:
- The ADD identified by the architect in the architecture review
- For each ADD: read its `stacks` frontmatter field, then load each named stack document via `knowledge_reader`. The `stacks` field is authoritative — it tells you exactly which conventions to follow for this component (e.g. `stacks: [go-backend, ecs-deployment]` means follow Go and ECS conventions; `stacks: [typescript-react]` means follow React/TS conventions). Do not assume stack from the Jira title alone.
- Use `workspace_reader` to read `.code-crew/structure.md`. The `## Project commands` section lists the exact commands for this project's build, test, lint, typecheck, and audit steps. Use those commands — do not assume `go test`, `npm test`, or any other tool unless the structure.md says to use it.

Do not begin implementation without understanding the ADD. No ADD = flag as blocker.

**Step 2 — Review BDD scenarios.**
The QA Lead's finalized Gherkin scenarios define the contract. Identify unit-level test cases
implied by each BDD scenario. Write test stubs before writing production code.

**Step 3 — Survey existing code.**
Use `code_index search` first to find comparable patterns by meaning — this is faster than listing directories:
- `code_index search "HTTP handler validation middleware"` → find how existing handlers are structured
- `code_index search "React form component error state"` → find UI patterns to match
- `code_index search "database query repository pattern"` → find data access conventions
- `code_index search "unit test table-driven"` → find test patterns for this language

Then use `search_ast` to confirm structural patterns (e.g. `search_ast pattern="$ROUTER.HandleFunc($PATH, $HANDLER)" language="go"` to see all registered routes). Only `read_file` specific files identified by these searches. Match established patterns exactly.

**Step 4 — Branch.**
Check whether a branch for this ticket already exists: `git branch -a | grep <JIRA-KEY>`.
- **Exists** → `git checkout feature/<JIRA-KEY>-<slug>`, then run `git log --oneline -10` and `git diff origin/main --name-only` to understand what was already done. Do not redo completed work — continue from where it left off.
- **Does not exist** → `git checkout -b feature/<JIRA-KEY>-<slug>` from `main`.

**Step 5 — Backend implementation (if in scope).**
- Write test stubs first (naming convention from the stack guide), then implement
- Follow the directory conventions from the architecture guide and stack guide loaded in Step 1
- Run the `commands.build` command after every new file — fix errors before continuing
- Run the `commands.test` command — all tests must pass before committing
- **Wiring check (mandatory):** For every new production function (validation gate, helper, middleware), run
  `grep -rn "<FunctionName>" .` and confirm at least one call site exists outside the test file.
  A function defined but never called from production code is dead code — the feature is not actually
  active. If any new function is unwired, add the call in the appropriate entry point (handler,
  validation chain, middleware) before proceeding.

**Step 6 — Frontend implementation (if in scope).**
First decide whether a design artifact is needed:
- **Purely behavioural change** (validation error, disabled state, existing component wired differently): no design needed — implement directly from BDD scenarios.
- **New visual layout, new page, or new component**: look for a design artifact anywhere in the ticket or repository: Jira attachment, link to any tool (Figma, Sketch, Zeplin, HTML mockup, wireframe image, designs/ directory doc). The tool does not matter — use whatever is available.
  - Found one → implement from it. Write `types.ts` first, then `<Component>.test.tsx`, then `index.tsx`.
  - Not found → skip frontend only, note "Frontend skipped: no design artifact found", continue to Step 7. Do NOT stop the entire task.
- Run `commands.typecheck` from structure.md — no type errors before committing
- Verify ARIA labels, keyboard nav, WCAG 2.1 AA colour contrast

**Step 7 — Update API spec (if the feature adds or changes HTTP routes).**
- Load `functions/api-standards.md` via `knowledge_reader` for the spec conventions
- Run `commands.api_spec` from structure.md to regenerate the spec and commit the output files
- If `commands.api_spec` is not set, check the stack guide for the correct generation command
- Use `api_spec` tool to verify no spec drift before committing
- If no HTTP routes changed: skip this step and state "No API spec changes."

**Step 8 — DB migration (if the feature adds, alters, or drops schema objects).**
- Load `functions/db-schema.md` via `knowledge_reader` for naming conventions and rules
- The migration tool is in `DB_MIGRATION_TOOL` env (set by /explore from `alembic.ini`, goose headers, or `atlas.hcl`). If unset, inspect the migrations directory to identify the tool in use.
- Use `commands.db_migrate` from structure.md (or the tool's standard command) to create the migration stub — review the generated file before committing
- Commit the migration file in the same branch as the model/handler change
- **Do NOT apply the migration** (`upgrade head`, `goose up`, `atlas migrate apply`, etc.) — applying is a human + CI step
- If no schema changes: state "No DB schema changes."

**Step 9 — Rebase.**
`git fetch origin && git rebase origin/main`.

**Step 10 — List new infrastructure requirements.**
Any new environment variables, secrets, IAM permissions, or AWS service calls introduced
must be explicitly listed. The DevOps Lead uses this list to update Terraform before integration
tests can run.

Format:
```
New infrastructure requirements:
- Env var: SECONDARY_DB_URL (non-sensitive)
- Secret: /<service>/<env>/api-key (via Secrets Manager)
- IAM: s3:GetObject on <bucket-prefix>/*
```
If none: state "No new infrastructure requirements."

**Step 11 — Output FILES CHANGED block.**
Before the completion signal, list every file you created or modified:
```
FILES CHANGED:
- <service>/internal/api/handler.go  (created)
- <service>/internal/api/handler_test.go  (created)
- integration/features/<feature>_steps_test.go  (created)
```
This is consumed by the manager to verify completeness, and by the code reviewer to know
which files to read. Include BDD step definition files. Do not list vendor/, node_modules/,
or auto-generated files (swagger, migration stubs before edits).

**Step 11 — Verify API spec** (if Step 7 ran).
Run `api_spec` tool with `operation: check_drift`. If it reports drift, fix before declaring IMPLEMENTATION COMPLETE.

**On tool failure** — log the error, try once with an alternative (list parent dir, use `find_files` before `read_file`), then skip and continue. Never use absolute paths in shell commands. Include any unresolved failures in your completion output.

**Completion signal — mandatory.**
Your final line MUST be exactly one of:
- `IMPLEMENTATION COMPLETE` — you wrote and verified all required code and unit tests
- `INCOMPLETE: <reason>` — you could not finish (e.g. missing design, tool failure, iteration limit)

Do NOT end with a planning statement. If you hit the iteration limit before finishing,
output `INCOMPLETE: hit iteration limit — <what remains>`.
