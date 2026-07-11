---
type: CrewAI Task
title: Repository Breakdown
description: >
  Given a filtered directory tree of the repository, classify every top-level area
  into its purpose. No tools — the tree is all you need.
tags: [explore, breakdown]
agent: architect
expected_output: >
  One AREA line per directory area. Ends with BREAKDOWN COMPLETE.
---

**DO NOT USE ANY TOOLS. The filtered directory tree above is all you need.**

Classify every meaningful directory in the repository. A directory is "meaningful" if
it represents a coherent area of the codebase — a service, library, tool, documentation
set, test suite, or infrastructure area.

For each area output exactly:

```
AREA: <relative-path> | <type> | <one-line description>
```

Types:
- **service** — runs as a long-lived process (API server, background worker, ECS task, Lambda)
- **library** — shared code imported by other services; not independently deployable
- **tool** — one-off CLI, migration script, admin utility; run on-demand
- **demo** — showcase, pilot, or proof-of-concept; not part of the production platform
- **docs** — documentation directory; no runnable code
- **infra** — infrastructure-only: Terraform, Docker, CI/CD configuration; no application runtime
- **test-harness** — integration test suite, BDD runner, e2e test suite

**Rules:**
- Classify at the shallowest level that makes sense. If `backend/` is a service, do not
  also emit lines for `backend/internal/`, `backend/cmd/` etc.
- If a top-level directory contains multiple distinct services (different binaries, different
  infra modules), classify it as **service** and note "contains sub-services" in the description
  — Phase 3 will drill into it.
- `infra` beats everything else: if a directory is pure Terraform/Docker/CI with no
  application runtime, it is `infra` even if it has shell scripts.
- Err toward **service** for ambiguous directories that have entry points or matching infra modules.

End with exactly:
```
BREAKDOWN COMPLETE
```
