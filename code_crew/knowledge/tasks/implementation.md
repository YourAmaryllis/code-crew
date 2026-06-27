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
  Implementation plan with proposed file paths, key function/method signatures, and unit
  test stubs. If code generation is in scope: full implementation with passing unit tests
  for both backend and frontend surfaces in scope.
---

Implement the feature described in the sprint input, covering both backend and frontend
surfaces as required by the story and ADD.

**Step 1 — Load context.** Use `knowledge_reader` to load:
- The ADD identified by the architect in the architecture review
- For each ADD: read its `stacks` frontmatter field, then load each named stack document via `knowledge_reader`. The `stacks` field is authoritative — it tells you exactly which conventions to follow for this component (e.g. `stacks: [go-backend, ecs-deployment]` means follow Go and ECS conventions; `stacks: [typescript-react]` means follow React/TS conventions). Do not assume stack from the Jira title alone.

Do not begin implementation without understanding the ADD. No ADD = flag as blocker.

**Step 2 — Review BDD scenarios.**
The QA Lead's finalized Gherkin scenarios define the contract. Identify unit-level test cases
implied by each BDD scenario. Write test stubs before writing production code.

**Step 3 — Survey existing code** (`workspace_reader`).
Read comparable handlers, service functions, and React components. Match established patterns exactly.

**Step 4 — Branch.**
`git checkout -b feature/<JIRA-KEY>-<slug>` from `main`.

**Step 5 — Backend implementation (if in scope).**
- Write `*_test.go` stubs first, then implement
- HTTP parsing → `internal/api/`; business logic → `internal/ard/`
- `go build ./...` after every new file — fix errors before continuing
- `go test ./... -count=1` — all tests pass before committing

**Step 6 — Frontend implementation (if in scope).**
- If no Figma link in the Jira ticket: flag as blocker and stop
- Write `types.ts` first, then `<Component>.test.tsx`, then `index.tsx`
- Handle all four states: loading, error, empty, loaded
- `npx tsc --noEmit` — no type errors before committing
- Verify ARIA labels, keyboard nav, WCAG 2.1 AA colour contrast

**Step 7 — Update API spec (if the feature adds or changes HTTP routes).**
- Load `functions/api-standards.md` via `knowledge_reader` for the spec conventions
- **Go:** run `swag init -g cmd/server/main.go -o docs/` and commit `docs/swagger.json` + `docs/swagger.yaml`
- **Python:** run `python -m scripts.export_openapi` and commit `docs/openapi.json`
- **TypeScript client:** if the frontend consumes the updated spec, run `npm run gen:api` and commit `src/api/schema.d.ts`
- Use `api_spec` tool to verify no spec drift before committing
- If no HTTP routes changed: skip this step and state "No API spec changes."

**Step 8 — DB migration (if the feature adds, alters, or drops schema objects).**
- Load `functions/db-schema.md` via `knowledge_reader` for naming conventions and rules
- Detect the migration tool from `DB_MIGRATION_TOOL` env, or from files (`alembic.ini` → alembic; `migrations/*.sql` with goose header → goose; `atlas.hcl` → atlas)
- **alembic:** `alembic revision --autogenerate -m "<description>"` — review the generated file before committing
- **goose:** `goose -dir migrations create <description> sql` — fill both Up and Down sections
- **atlas:** `atlas migrate diff <name> --dir file://migrations --to "postgres://$DB_URL" --dev-url "docker://postgres/15"`
- Commit the migration file in the same branch as the model/handler change
- **Do NOT run `upgrade head` / `goose up` / `atlas migrate apply`** — applying migrations is a human + CI step
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
- Secret: /platform/<env>/portal/api-key (via Secrets Manager)
- IAM: s3:GetObject on dev-platform-datasets/*
```
If none: state "No new infrastructure requirements."

**Step 11 — Verify API spec** (if Step 7 ran).
Run `api_spec` tool with `operation: check_drift`. If it reports drift, fix before declaring IMPLEMENTATION COMPLETE.

**Completion signal — mandatory.**
Your final line MUST be exactly one of:
- `IMPLEMENTATION COMPLETE` — you wrote and verified all required code and unit tests
- `INCOMPLETE: <reason>` — you could not finish (e.g. missing design, tool failure, iteration limit)

Do NOT end with a planning statement. If you hit the iteration limit before finishing,
output `INCOMPLETE: hit iteration limit — <what remains>`.
