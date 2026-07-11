---
id: ADD-013
title: /explore Command — Full Design
status: accepted
date: 2026-07-10
supersedes: ADD-002 (explore section), ADD-012
---

## Purpose

`/explore` surveys an unfamiliar codebase and produces a persistent context layer —
`structure.md` plus a set of pre-computed diagrams — that all other commands read.
It must work on any repo regardless of language, layout, or naming conventions.
Nothing may be hardcoded.

---

## Phases

### Phase 1 — Python scan *(no LLM)*

Pure signal detection from file presence and content.

| What | How |
|------|-----|
| Stacks | Manifest files: `go.mod`, `package.json`, `Cargo.toml`, `pom.xml`, `*.tf`, etc. |
| Architecture style | Directory name heuristics: `ports/`+`adapters/` → hexagonal, `usecases/` → clean, etc. |
| CI/CD | `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, `*.tf` with ECS resources |
| Test frameworks | `pytest.ini`, `jest.config.*`, `*.feature` (BDD) |
| Migration tool | `alembic.ini`, `atlas.hcl`, `-- +goose` in SQL files |
| API docs | `openapi.yaml/json`, `docs/swagger.*` |
| Commands | Makefiles, `package.json` scripts, `pyproject.toml` tool sections |
| Compliance | Keyword scan of design docs (HIPAA, GDPR, PCI-DSS, SOC2, CCPA, FIPS) |
| Terraform | Root path, `modules/` path, backend config, environment dirs |
| Sub-executables | Stack-specific detectors in `shared/stacks/` — Go `cmd/*/`, Python `__main__.py`, Node workspaces/bin, Rust `[[bin]]`, Java multi-module; **also detects TypeScript/React web-app sub-dirs** (`frontend/`, `ui/`, `web/`, `mock/`) by presence of `package.json` even when the parent service has no root `package.json` |
| External services | Infra module names + design doc keyword scan |
| Git submodules | `.gitmodules` |
| Infra modules | Listing of the Terraform modules directory |

**Output**: initial `structure.md` with all Phase 1 findings; config persisted to
`.code-crew/config.yaml`; inventory dict held in memory for later phases.

---

### Phase 2 — Repository breakdown *(1 LLM call, no tools)*

Python builds a filtered directory tree (full depth, noise excluded) and sends it
to the LLM. The LLM identifies every area and classifies it:

```
AREA: <path> | <type> | <one-line description>
```

Types: `service | library | tool | demo | docs | infra | test-harness`

The 8b model wraps type values in bold markers (`**service**`). The parser strips
these before storing, so downstream code always sees bare type strings.

No tools in this call — the tree is all the LLM needs.

---

### Phase 3 — Per-unit deep-dive *(N LLM calls, with tools)*

One LLM call per area from Phase 2. The agent has `workspace_reader` and `code_index`.

**For `service` areas**, the agent explores with tools and writes:

```
UNIT_SUMMARY: <path>
PURPOSE: <2-3 sentences: what it does, who uses it, key integrations>
TYPE: deployable-service | worker | lambda | frontend | library | cli
SENSITIVITY: phi | pii | financial | public | none
ENTRY_POINTS: <separately runnable executables, or "none">
DECOMPOSE: yes | no
SUB_UNITS: <comma-separated relative sub-paths if DECOMPOSE=yes>
CONNECTS_TO: <comma-separated connection descriptors — see format below>
UNIT_SUMMARY COMPLETE
```

`CONNECTS_TO` format: `<target> (<mechanism>)` — e.g.
`postgresql (sql), redis (cache), sqs/dataset-conversion (queue-write), attestation/cmd/server (http)`

The agent writes what it can confirm from code; omits connections it cannot find.
**Do not hallucinate connections** — an incomplete list is better than a wrong one.

`SUB_UNITS` values that contain `:` or `--` are rejected by the parser (Makefile
targets, not file paths). UNIT_SUMMARY blocks inside ` ``` ` code fences are ignored
(the 8b model sometimes writes a "correction" block after the real one).

If `DECOMPOSE: yes`, the orchestrator spawns a recursive Phase 3 call per sub-unit.

**For `docs` areas**, one paragraph per file:

```
DOC_SUMMARY: <relative-path>
<summary paragraph>
DOC_SUMMARY COMPLETE
```

**For `tool`, `demo`, `test-harness`, `infra` areas**, a brief one-liner:

```
AREA_SUMMARY: <path> | <type> | <one sentence>
```

All output is appended to `structure.md` as it completes.

---

### Phase 4 — Decomposition *(pure Python, no LLM)*

**Input**: `structure.md` with all Phase 3 UNIT_SUMMARY blocks.

**Steps**:

1. `_filter_structure_top_level(structure_md, top_level_paths)` — keeps only
   UNIT_SUMMARY blocks whose path is a Phase 2 area. Skips content inside
   ` ``` ` code fences to prevent spurious duplicate block parsing.

2. `classify_units_from_structure(filtered_md)` — deterministic parse of
   UNIT_SUMMARY fields:
   - `TYPE` in `{deployable-service, worker, lambda, frontend}` → `real_services`
   - `ENTRY_POINTS` non-empty → `real_services`
   - Otherwise → `not_services` (with reason)
   - `DECOMPOSE: yes` + valid `SUB_UNITS` → `decomposed` dict
   - Deduplicates `real_services` (sub-executables can appear from both their own
     UNIT_SUMMARY block and a parent's SUB_UNITS list)

3. `build_diagram_from_services(real_services, not_services, decomposed, ext_svcs)` —
   generates Mermaid `graph TD`:
   - One node per real service (labelled `(deployable)`)
   - One node per decomposed sub-unit not already in real_services (labelled `(sub-service)`)
   - External service nodes (labelled `(external)`)
   - Parent→child edges using **nearest-ancestor** detection (not just immediate parent),
     so `portal/backend/cmd/server` correctly links to `portal` even though
     `portal/backend/cmd` is not itself a node

**Output**: `decomposition.md` (wrapped in ` ```mermaid ``` ` fence).

---

### Phase 5 — Diagram synthesis *(3 LLM calls, with targeted tool access)*

Generates three additional diagrams from the already-collected `structure.md` context.
These diagrams feed into `/threat` and other commands without re-reading the codebase.

#### 5a — Deployment diagram (`deployment.md`)

**Input**: `structure.md` (stacks, ECS/Lambda/static hosting infra modules, external
services, service summaries with TYPE fields).

**Output** (`deployment.md`): Mermaid `graph TD` grouping services by compute platform
(ECS Fargate cluster, Lambda, S3/CloudFront static hosting, etc.) and showing
environment tiers (dev / staging / prod) where detectable.

No tool access needed — `structure.md` already has infra module names and service types.

#### 5b — Network diagram (`network.md`)

**Input**: `structure.md` (Terraform info: root path, modules, environments) +
targeted reads of the infra networking directory (VPC module, subnet configs,
security group definitions, load balancer config).

The agent reads Terraform HCL files in the infra dir with `workspace_reader`.
It produces a Mermaid `graph TD` showing network topology: internet → CDN/WAF →
load balancers → public subnets → private subnets → isolated data-tier subnets,
with services placed in their correct segment.

Tool access: `workspace_reader` (infra dir only).

#### 5c — Architectural data flow diagram (`dataflow.md`)

**Input**: `structure.md` with all UNIT_SUMMARY `CONNECTS_TO` fields populated by
Phase 3, plus external services list.

Python assembles a connection inventory from all `CONNECTS_TO` lines in structure.md,
then makes one LLM call to render it as a Mermaid DFD showing:
- Service-to-service calls (labelled with mechanism: HTTP, gRPC, SQS, etc.)
- Data stores (DB, cache, queue) as distinct node shapes
- External service connections

This is an **architectural DFD** — no trust boundaries, no threat annotations.
Those are added by `/threat` (see ADD-014).

No new code reading — the `CONNECTS_TO` data was collected in Phase 3.

---

## Output files

All written to `<repo>/.code-crew/`:

| File | Phase | Consumer |
|------|-------|----------|
| `structure.md` | 1, 2, 3 | All commands |
| `decomposition.md` | 4 | All commands; `/threat` |
| `deployment.md` | 5a | `/threat`, `/verify` |
| `network.md` | 5b | `/threat`, `/verify` |
| `dataflow.md` | 5c | `/threat` |
| `inventory.json` | 1 | `/threat`, `/domain` |
| `config.yaml` | 1 | All commands |

---

## structure.md layout

```
# <repo-name> — codebase survey

## Detected stacks
## Detected architecture
## CI/CD tooling
## Terraform infrastructure
## Project commands
## External services
## Repository areas         ← Phase 2 AREA lines (table form)
## Unit summaries           ← Phase 3 UNIT_SUMMARY blocks
## Decomposition            ← Phase 4 mermaid block (appended)
```

---

## Parser robustness rules

These rules exist because the 8b LLM (fast tier) has well-documented formatting quirks:

| Quirk | Fix |
|-------|-----|
| Bold markers on type fields (`**service**`) | Strip `**` before string comparison |
| Heading prefix on UNIT_SUMMARY lines (`## UNIT_SUMMARY:`) | Strip `#` and leading spaces |
| "Correction" UNIT_SUMMARY inside ` ``` ` fences | Skip all content inside code fences |
| Makefile targets in SUB_UNITS (`demo:all`) | Reject values containing `:` or `--` |
| Duplicate real_services (sub-executables in two places) | Deduplicate preserving order |
| CONNECTS_TO hallucinations | Best-effort only; omission preferred over invention |

---

## Tool availability

| Tool | Phase |
|------|-------|
| `workspace_reader` | 3 (service deep-dive), 5b (infra networking read) |
| `code_index` | 3 (if index built) |

`/explore` does not require `/index`. If the index exists it is used; if not,
`workspace_reader` alone suffices.

---

## Failure handling

Every phase is wrapped in try/except. A Phase 3 failure writes:
`AREA_SUMMARY: <path> | unknown | summarisation failed`

Phase 4 (Python) falls back to treating all Phase 2 `service` areas as real services
if the UNIT_SUMMARY parse yields nothing.

Phase 5 failures write a warning to the console and continue — missing diagram files
are tolerated by downstream commands (they degrade gracefully).

---

## Key constraints (must never be violated)

- No hardcoded directory names (`ops/`, `portal/`, `designs/`) in Python or task files
- No hardcoded file paths in knowledge files
- No project-specific names in knowledge files
- The filtered tree approach means explore works equally on a single-service repo,
  a monorepo, a docs-only repo, or a polyglot monorepo
- Infra directory is always from `terraform_info["root"]` — never assumed
- Designs path is always from config or auto-detection — never hardcoded

---

## Changes from ADD-002 / ADD-012

| Old step | Replacement |
|----------|-------------|
| Top-8 candidate dirs heuristic | Phase 2 full-tree LLM breakdown |
| Pre-reading Python helpers | Phase 3 agent reads with tools |
| Domain dir heuristic | Phase 3 agent decides what to explore |
| Separate domain summarisation loop | Folded into Phase 3 per-unit deep-dive |
| OTM scope LLM call | Moved to `/threat` (Phase 0 of ADD-014) |
| Phase 4 LLM-based decomposition | Phase 4 deterministic Python |
| No diagram synthesis | Phase 5 generates deployment, network, DFD |
