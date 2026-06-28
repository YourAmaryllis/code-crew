# Scan Design — `/init`, `/explore`, `/verify`

**Status:** Current
**Last updated:** 2026-06-27

---

## Purpose of each command

| Command | Lifecycle | Question it answers |
|---------|-----------|---------------------|
| `/init` | Once per project | "How do I configure code-crew for this repo?" |
| `/explore` | After major codebase changes | "What is this codebase and how is it structured?" |
| `/verify` | Before release or on demand | "Is this codebase correct, secure, and compliant?" |

They are separate commands with different lifecycles, not three views of the same thing. `/verify` works better when `/explore` has already run (agents read `structure.md`), but neither depends on the other being up to date.

---

## Complete functionality inventory

### `/init` — project bootstrap (pure Python)

1. `git init` if not already a repo
2. Interactive prompts: project name, issue tracker (`jira` / `linear` / `github`), project key
3. Writes `.code-crew/config.yaml`
4. Writes minimal `.gitignore`
5. Calls `_scan_project()` and appends auto-detected values to config under `# Auto-detected` block

`_scan_project()` signal table:

| Signal file / pattern | Config key set |
|----------------------|----------------|
| `alembic.ini` | `db.migration_tool: alembic` |
| `atlas.hcl` or `atlas.sum` | `db.migration_tool: atlas` |
| `-- +goose` in `*.sql` files | `db.migration_tool: goose` |
| `migrations/`, `alembic/versions/`, `db/migrations/` | `db.schema_path: <dir>` |
| `pytest.ini`, `setup.cfg`, `[tool.pytest]` in pyproject | `testing.framework: pytest` |
| `jest.config.*` | `testing.framework: jest` |
| `go.mod` (no other framework match) | `testing.framework: go-test` |
| `*.feature` files exist | `testing.bdd: true` |
| `docs/swagger.json/yaml`, `openapi.yaml/json` | `api.doc_standard: openapi` |
| `ports/` + `driving/` or `driven/` dirs | `architecture.style: hexagonal` |
| `domain/` + `application/` + `domain/model\|services\|repos` | `architecture.style: onion` |
| `usecases/` or `domain/` + `adapters/` | `architecture.style: clean` |

`/init` is idempotent — the auto-detected block is appended once and never overwritten on re-run.

### `/explore` — codebase survey (Python Phase 1 + LLM Phase 2)

**Phase 1 — pure Python (always runs):**
1. Directory tree walk, 4 levels deep, skip `vendor`, `node_modules`, `.terraform`, etc.
2. Stack detection from file signals (see table below)
3. Call `_scan_project()` for arch style, migration tool, schema path
4. Write `.code-crew/structure.md` with tree + detected config — this is what agents read as project context
5. Generate OTM skeleton at `designs/TMD/<name>.yaml` if `designs/` exists and file doesn't already exist

Stack detection signals:

| Signal | Stack tag |
|--------|-----------|
| `go.mod` | `go-backend` |
| `package.json` with `react`, `next`, `@types/react` deps, or `*.tsx` | `typescript-react` |
| `requirements*.txt` or `pyproject.toml` | `python` |
| `*.java` files | `java` |
| `*.rb` files or `Gemfile` | `ruby` |
| `*.rs` files or `Cargo.toml` | `rust` |
| `*.tf` files | `terraform`; if content contains `"aws"` → also `terraform-aws` |
| `*task-definition*.json` or `*ecs*.tf` | `ecs-deployment` |
| `*.ipynb`, or AI/ML keywords in requirements | `ai-ml` |
| `*.feature` files | `bdd-testing` |

**Phase 2 — LLM (runs if a model is configured; skips gracefully if not):**

An Architect agent reads the tree and up to 5 key files (README, main entrypoints) and produces:
- `ARCHITECTURE_STYLE` — with reasoning; overrides Phase 1 if Phase 1 found nothing
- `PROJECT_SUMMARY` — 1-2 sentence description of what the project does
- `COMPONENT` lines — `<dir_name>: <description>` used to fill OTM component descriptions

Phase 2 output augments `structure.md` and replaces the empty component descriptions in the OTM file.

**Why Phase 2 needs LLM:**

| Detection | Why pure Python fails |
|-----------|----------------------|
| Architecture style | Dir-name sniffing has high false-positive rate. Many projects have a `ports/` dir (network ports), a `domain/` dir (DNS domain), or `usecases/` for something unrelated. The agent reads actual file contents and layer dependencies. |
| DB migration tool (non-standard) | `alembic.ini` etc. cover the common tools. Flyway, Liquibase, `golang-migrate`, custom scripts have no single distinctive file. An agent can read a migrations directory and identify the tool from SQL header comments or file naming. |
| OTM component descriptions | The skeleton has empty `description: ''` fields. Top-level dirs named `cmd/`, `internal/`, `api/` tell you nothing about what the component does. The agent reads README + entrypoints and writes meaningful descriptions. |
| Project summary | Not possible from files alone without reading them. Useful for OTM `project.description` and for the structure.md header that agents read. |

**What pure Python is good enough for:**

File extension and manifest detection is fast, accurate, and has no ambiguity — no LLM needed:
- Language presence (`*.go`, `*.py`, `*.java`, `*.rb`, `*.rs`)
- Build tool (`go.mod`, `pom.xml`, `build.gradle`, `package.json`, `Cargo.toml`)
- Framework (reading `package.json` deps, `pyproject.toml` tool sections)
- CI system (`.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`)
- BDD (`*.feature` exists)
- Migration tool when a unique marker file is present

### `/verify` — correctness and compliance audit (LLM only)

Six sequential LLM tasks — a different category of work entirely:

| Task | Agent | What it checks |
|------|-------|----------------|
| `verify_arch_scan` | architect | Layer violations, dependency rule breaches, missing ADRs — reads source files against ADR/ADD knowledge |
| `verify_security_scan` | security_lead | Hardcoded secrets, OWASP violations, OTM coverage gaps, dependency vulnerabilities |
| `verify_compliance_scan` | compliance_officer | Data retention, consent flows, audit trails, active compliance stacks (GDPR, HIPAA, SOC2…) |
| `verify_domain_scan` | architect | Entity name drift between `designs/DMD/` and actual code |
| `verify_chief_review` | architect | Consolidates findings; marks each REQUIRED / EXEMPT / PASS |
| `verify_report` | scrum_master | Writes `.code-crew/audit-YYYYMMDD-HHMMSS.md` |

`/verify` reads `structure.md` (from `/explore`) as context, but re-examines source files directly — it cannot rely on `/explore` having been run recently.

REQUIRED findings trigger a REPL prompt to open Jira/Linear/GitHub Issues tickets for each.

---

## Overlap and shared implementation

**Problem before this refactor:** Architecture detection and migration tool detection were copy-pasted in three places — `_detect_project()` (used by `/init`), the inline code in `_run_explore()`, and partially in `verify_arch_scan.md` (the task does its own dir-name check if `ARCHITECTURE_STYLE` is unset).

**Fix:** Single `_scan_project(root)` function (renamed from `_detect_project`) called by both `/init` and the Phase 1 of `/explore`. The verify task still does its own check at runtime, but by the time `/verify` runs, `ARCHITECTURE_STYLE` will typically already be set in the environment from `/explore`.

---

## Decision: keep separate, not merged

Merging all three into one command was considered and rejected:

- `/init` is a one-time interactive setup command. It should be fast and not need a model configured.
- `/explore` is a re-runnable survey. The Python phase should work without a model; the LLM phase is an enhancement.
- `/verify` is a compliance gate. Its LLM calls are mandatory — there is no pure-Python fallback for "does this code have layer violations?"

Combining them would force a model to be configured for project setup, or produce a confusing command that sometimes runs LLM calls and sometimes doesn't depending on what flags you pass.

**Shared implementation strategy:**
- `_scan_project(root)` — shared pure Python detection, called by both `/init` and `/explore` Phase 1
- `/explore` Phase 1 output (`structure.md`) feeds into `/verify` as context
- No other coupling
