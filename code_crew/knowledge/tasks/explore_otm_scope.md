---
type: CrewAI Task
title: OTM Scope Decision
description: Security architect uses SAD decomposition to identify architectural components and decide what OTM files to produce
tags: [explore, threat-model, otm, scoping]
agent: architect
expected_output: >
  One PROJECT block per OTM file, each listing id, description, and assigned components.
  Ends with OTM SCOPE COMPLETE.
---

You are deciding which OpenThreatModel (OTM) YAML files to produce for this project.

The goal is **one OTM per architectural component** as defined by the SAD decomposition view —
not one per source directory, not one per terraform module, and not one for test suites or tools.

## Step 0 — Identify git submodules and read every candidate README.

**Do this before any other step.**

Use `workspace_reader` to read `.gitmodules` (if it exists). Every path listed under `[submodule]`
is a git submodule. Submodules are **excluded by default** — they are external dependencies,
client-specific directories, or separately-versioned repos that own their own threat model.

A submodule is **only included** if ALL of the following are true:
1. It is a deployable service owned by this project (not a client data or pilot directory)
2. Its infrastructure is managed in this repo's own ops directory (not by an external team)
3. Its README does not say "pilot", "client", "submodule of X", "data registration", or "manual operation"

For any directory that might be in scope, read its README (top-level `README.md`) before deciding.
The README is the most reliable signal: "pilot", "scripts", "tooling", "data registration",
"manual", "one-time" → exclude. "service", "API", "deployed to ECS/Lambda" → include.

## Step 1 — Load the SAD decomposition view.

Use `workspace_reader` to find and read the decomposition view in the SAD directory. This is the
primary authority on what the architectural components are. Read the Element Catalog section carefully.

If no SAD exists: fall back to Step 2 using the project inventory only.

## Step 2 — Read the architectural components from the project structure.

The task context includes `## Architectural components` from `.code-crew/structure.md` (produced
by `/explore`). This section maps SAD component names to code directories and descriptions.
Use this to understand which code directories implement which SAD component.

## Step 3 — Decide scope: one OTM per architectural component.

**Include** — deployable runtime services that are:
- Owned by this project (infrastructure managed in this repo)
- Long-running (ECS task, Lambda, background worker, API server)
- Have their own trust boundary and data flows

**Exclude** — all of the following:
- Git submodules (identified in Step 0) unless they pass all three inclusion tests above
- Test suites (BDD test runners, E2E scripts, integration test directories)
- Demo/playground directories
- CI/CD tooling and scripts
- Pure infrastructure with no runtime (networking, DNS, routing, container registry)
- Security scanning tools
- **Client-specific or pilot directories**: data registration scripts, one-time pipelines,
  manual operation tools, data factsheets, questionnaire files, analytics notebooks
- **Directories whose README says**: "pilot", "client", "submodule", "data registration",
  "manual", "scripts only", "one-time"

If a component maps to multiple code directories (e.g. a worker and server under the same
service root), they belong in **one OTM** — same trust boundary, same codebase.

Infrastructure-only components (databases, queues) are **not** separate OTMs — they appear
as components _inside_ the relevant service OTM.

## Step 4 — Assign every included component to exactly one OTM.

Each PROJECT block represents one OTM file. Include:
- The primary code directory for that component
- Any sub-executables (`cmd/` entries) from that directory
- Infrastructure modules specific to this component (not shared infrastructure)
- External services this component talks to

Do NOT create a PROJECT for:
- `integration` directory (BDD test suite)
- `demo` directory (E2E playwright scripts)
- Terraform modules that are shared infra (VPC, ECR, DNS, CICD)
- Git submodule directories (unless they pass the inclusion test in Step 0)

## Step 5 — Output one block per OTM in this exact format.

```
PROJECT: <id>
DESCRIPTION: <1-2 sentence plain-English scope for a security auditor>
COMPONENTS: <comma-separated list of component names from the inventory>
```

**id rules** (strictly enforced):
- Use the **primary code directory name** exactly as it appears on disk.
- Lowercase, hyphens or underscores only — no spaces, no camelCase, no run-together words.
- If the SAD names the component differently from the directory, use the **directory name** — that is what the file system and coverage report depend on.

Each deployable component appears in exactly one PROJECT block.
End your output with exactly:
```
OTM SCOPE COMPLETE
```
