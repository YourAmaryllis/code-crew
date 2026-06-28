---
type: CrewAI Task
title: OTM Scope Decision
description: Security architect decides how many OTM threat model files to produce and what goes in each
tags: [explore, threat-model, otm, scoping]
agent: architect
expected_output: >
  One PROJECT block per OTM file, each listing id, description, and assigned components.
  Ends with OTM SCOPE COMPLETE.
---

You are deciding how to partition this project's threat model into one or more OpenThreatModel (OTM) YAML files.

The goal is one OTM per independently deployable system — not one per source directory. Systems that share infrastructure, trust boundaries, or deployment pipelines usually belong in the same OTM. Unrelated tools or demo apps are their own OTM.

## Context

The project inventory is provided below. It includes:
- **Source services** — top-level directories containing application code
- **Sub-executables** — binaries found under `cmd/` within each service (each is a distinct runtime component)
- **Infrastructure modules** — Terraform modules in `ops/modules/` that reveal databases, queues, ECS tasks, Lambda functions, etc.
- **External services** — third-party APIs and SaaS detected in source code

Read this inventory carefully before deciding.

## Step 1 — Identify logical systems.

Group components into cohesive systems. Criteria for a separate OTM:
- Deployed independently with its own lifecycle
- Has a meaningfully different threat surface (e.g. customer-side vs. Loopora-side)
- Used by a different class of actors
- A standalone tool with no shared trust boundary with the rest

## Step 2 — Assign every component to exactly one OTM.

Include in each PROJECT block:
- All source service directories relevant to that system
- All sub-executables (cmd/ entries) from those services
- All infrastructure modules that support that system (databases, queues, ECS tasks, Lambda, etc.)
- All external services used by that system

## Step 3 — Output one block per OTM in this exact format.

```
PROJECT: <kebab-case-id>
DESCRIPTION: <1-2 sentence plain-English scope for a security auditor>
COMPONENTS: <comma-separated list of component names from the inventory>
```

Each component name must appear in exactly one PROJECT block.
End your output with exactly:
```
OTM SCOPE COMPLETE
```
