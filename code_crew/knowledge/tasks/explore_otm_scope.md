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

## Step 1 — Load the SAD decomposition view.

Use `workspace_reader` to read `designs/SAD/SAD-3-Decomposition-View.md`. This is the primary
authority on what the architectural components are. Read the Element Catalog section carefully.

If no SAD exists: fall back to Step 2 using the project inventory only.

## Step 2 — Read the architectural components from the project structure.

The task context includes `## Architectural components` from `.code-crew/structure.md` (produced
by `/explore`). This section maps SAD component names to code directories and descriptions.
Use this to understand which code directories implement which SAD component.

## Step 3 — Decide scope: one OTM per architectural component.

Rules:
- **Include**: deployable services, runtime components, and ECS/Lambda/container workloads
  that have their own trust boundary, data flows, or threat surface
- **Exclude**: test suites (`integration/`, BDD test runners), demo/E2E scripts, CI/CD tooling,
  pure terraform modules with no runtime (VPC, DNS, routing), security scanning tools
- If a SAD component maps to multiple code directories (e.g. worker + server both under
  `attestation/`), they belong in **one OTM** — same trust boundary, same codebase
- Infrastructure-only components (databases, queues) are **not** separate OTMs — they appear as
  components _inside_ the relevant service OTM

## Step 4 — Assign every runtime component to exactly one OTM.

Each PROJECT block represents one OTM file. Include:
- The primary code directory for that component
- Any sub-executables (`cmd/` entries) from that directory
- Infrastructure modules that are specific to this component (not shared platform infra)
- External services this component talks to

Do NOT create a PROJECT for:
- `integration` directory (BDD test suite)
- `demo` directory (E2E playwright scripts)
- Terraform modules that are shared infra (VPC, ECR, DNS, CICD) — these belong to the
  platform-level TMD if one exists, or can be documented inside whichever OTM they support

## Step 5 — Output one block per OTM in this exact format.

```
PROJECT: <kebab-case-id matching the primary code directory or SAD component name>
DESCRIPTION: <1-2 sentence plain-English scope for a security auditor>
COMPONENTS: <comma-separated list of component names from the inventory>
```

Each deployable component appears in exactly one PROJECT block.
End your output with exactly:
```
OTM SCOPE COMPLETE
```
