---
id: ADD-013
title: /explore Command — Full Design
status: accepted
date: 2026-07-09
supersedes: ADD-002 (explore section), ADD-012
---

## Purpose

`/explore` surveys an unfamiliar codebase and writes `structure.md` — the persistent
context file that all other agents read. It must work on any repo regardless of language,
layout, or naming conventions. Nothing may be hardcoded.

---

## Phases

### Phase 1 — Python scan *(no LLM)*

Pure signal detection from file presence and content — fast, deterministic, no model needed.

| What | How |
|------|-----|
| Stacks | Manifest files: `go.mod`, `package.json`, `Cargo.toml`, `pom.xml`, `*.tf`, etc. |
| Architecture style | Directory name heuristics: `ports/`+`adapters/` → hexagonal, `usecases/` → clean, etc. |
| CI/CD methods | `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, `*.tf` with ECS resources |
| Test frameworks | `pytest.ini`, `jest.config.*`, `*.feature` (BDD), `go.mod` default |
| Migration tool | `alembic.ini`, `atlas.hcl`, `-- +goose` in SQL files |
| API docs | `openapi.yaml/json`, `docs/swagger.*` |
| Commands | Makefiles, `package.json` scripts, `pyproject.toml` tool sections |
| Compliance | Keyword scan of `designs/` docs (HIPAA, GDPR, PCI-DSS, SOC2) |
| Terraform info | `*.tf` root path, `modules/` path, backend config, environment dirs |
| Sub-executables | Stack-specific modules in `shared/stacks/` — Go `cmd/*/main.go`, Python `__main__.py`, Node `bin`, Rust `[[bin]]`, Java multi-module |
| Git submodules | `.gitmodules` |
| Infra modules | `terraform_info.modules_path` dir listing |

**Output**: initial `structure.md` with all Phase 1 findings. Config persisted to
`.code-crew/config.yaml`.

---

### Phase 2 — Repository breakdown *(1 LLM call, minimal tools)*

**Goal**: understand the shape of the repo without assumptions.

Python builds a **filtered directory tree** — full depth, but excluding noise:
- `.git`, `vendor`, `node_modules`, `__pycache__`, `.terraform`, `dist`, `build`,
  `.venv`, `coverage`, `.next`, `*.log`, `*.out`, `*.tmp`, `*.lock` (file patterns)
- Directories matching those names at any depth

The filtered tree is sent to the LLM in one call. The LLM identifies every top-level
area and classifies it:

```
AREA: <path> | <type: service | library | tool | demo | docs | infra | test-harness> | <one-line description>
```

Types:
- **service** — runs as a long-lived process; will be explored in depth in Phase 3
- **library** — shared code, no standalone runtime
- **tool** — one-off CLI, script, or utility; brief summary only
- **demo** — demo or showcase; not part of the platform
- **docs** — documentation directory; each doc summarised
- **infra** — infrastructure-only (Terraform, Docker, CI/CD); no application runtime
- **test-harness** — integration test suite, BDD runner, or e2e suite

No tools in this call — the filtered tree is all the LLM needs.

---

### Phase 3 — Per-unit deep-dive *(N LLM calls, with tools)*

One LLM call per area identified in Phase 2. The agent has access to:
- `workspace_reader` — file search, content read, pattern search
- `code_index` — semantic search over the codebase (Chroma, local embeddings)

**For `service` and `library` areas:**

The agent explores the unit using tools, may further decompose if warranted (e.g. a
service directory containing multiple independently deployable sub-services), and writes:

```
UNIT_SUMMARY: <path>
PURPOSE: <2-3 sentences: what it does, who uses it, key integrations>
TYPE: deployable-service | worker | lambda | frontend | library | cli
SENSITIVITY: phi | pii | financial | public | none
ENTRY_POINTS: <separately compiled/runnable executables, or "none">
DECOMPOSE: yes | no
SUB_UNITS: <comma-separated sub-paths if DECOMPOSE=yes>
UNIT_SUMMARY COMPLETE
```

If `DECOMPOSE: yes`, the orchestrator spawns a recursive Phase 3 call for each sub-unit.

**For `docs` areas:**

The agent reads each document and writes a one-paragraph summary per file:

```
DOC_SUMMARY: <relative-path>
<summary paragraph>
DOC_SUMMARY COMPLETE
```

**For `tool`, `demo`, `test-harness`, `infra` areas:**

Single brief summary — no deep exploration:

```
AREA_SUMMARY: <path> | <type> | <one sentence>
```

All output appended to `structure.md` as it completes.

---

### Phase 4 — Decomposition *(1 LLM call, with tools)*

**Input**: `structure.md` (already rich with Phase 3 summaries).

**Goal**: produce the decomposition diagram and the service list for OTM scope.

The agent can use `workspace_reader` and `code_index` to verify anything unclear, but
`structure.md` should already contain enough context that most calls require no tools.

Output:

```
REAL_SERVICE: <path> | <reason>
NOT_SERVICE: <path> | <reason: tool | demo | infra | test-harness | library>
DECOMPOSE: <path> → <sub-service-name>, ... | <reason>
PROJECT: <id> | COMPONENTS: <comma-separated paths> | DESCRIPTION: <one sentence>
```

Followed by:

```
DECOMPOSITION_BEGIN
```mermaid
graph TD
    ...
```
DECOMPOSITION_END
```

`PROJECT` blocks drive OTM file generation — one OTM file per PROJECT. This folds the
old OTM scope step (Phase 3a) directly into decomposition.

Written to `decomposition.md` and appended to `structure.md`.

---

### Phase 5 — OTM build *(N LLM calls per project)*

For each PROJECT block: run the existing OTM build crew → `designs/TMD/<id>.yaml`.

Unchanged from current design.

---

## structure.md layout

```
# <repo-name> — codebase survey

## Detected configuration
<stacks, CI/CD, commands, compliance — Phase 1>

## Repository areas
<AREA lines — Phase 2>

## Unit summaries
<UNIT_SUMMARY blocks — Phase 3>

## Document summaries
<DOC_SUMMARY blocks — Phase 3>

## Architecture
<ARCHITECTURE_STYLE, PROJECT_SUMMARY, code_structure — synthesis>

## Compliance
<confirmed compliance standards — synthesis>

## Decomposition
<Mermaid diagram — Phase 4>
```

---

## What was removed vs. ADD-002 / ADD-012

| Old step | Replacement |
|----------|-------------|
| Top-8 candidate dirs heuristic | Phase 2 full-tree LLM breakdown — no cap, no hardcoded names |
| Pre-reading Python helpers (README, manifest, entry snippets) | Phase 3 agent reads with tools |
| Domain dir heuristic (`internal/`, `src/pages/` ≥5 files) | Phase 3 agent decides what to explore |
| Separate domain summarisation loop | Folded into Phase 3 per-unit deep-dive |
| OTM scope LLM call (Phase 3a) | Folded into Phase 4 decomposition (PROJECT blocks) |
| Pre-read infra dir listing | Phase 4 agent reads with tools |
| Pre-read SAD excerpts | Phase 4 agent reads with tools |

---

## Tool availability

| Tool | When available | Used in |
|------|---------------|---------|
| `workspace_reader` | Always | Phase 3, Phase 4 |
| `code_index` | After `/index` has been run | Phase 3, Phase 4 |

`/explore` does not require `/index` to have been run first. If the index exists it is
used; if not, `workspace_reader` alone is sufficient.

---

## Failure modes

Every phase is wrapped in try/except. A failure in one unit's Phase 3 call produces a
`AREA_SUMMARY: <path> | unknown | summarisation failed` line and continues.
Phase 4 (decomposition) may fall back to a Python heuristic scope if it fails:
one PROJECT per REAL_SERVICE from Phase 2.

---

## Key constraints (must never be violated)

- No hardcoded directory names (`ops/`, `portal/`, `designs/`) anywhere in Python or task files
- No hardcoded file paths (no `designs/SAD/`, `designs/TMD/platform.json`)
- No project-specific names in knowledge files
- The filtered tree approach means the tool works equally on a single-service repo,
  a monorepo, a docs-only repo, or a polyglot monorepo
