---
type: CrewAI Task
title: Service Summarization
description: Summarize one service directory based on pre-read context. No tools — everything needed is already provided.
tags: [explore, summarize, service]
agent: architect
expected_output: >
  Structured SUMMARY block with PURPOSE, TYPE, SENSITIVITY, and ENTRY_POINTS.
  Ends with SUMMARY COMPLETE.
---

**DO NOT USE ANY TOOLS. All information needed is already in the context above.**

Read the provided service information and produce a concise structured summary.

Output exactly this format:

```
SUMMARY: <service-name>
PURPOSE: <2-3 sentences — what this service does, who uses it, key external integrations>
TYPE: deployable-service | library | cli | test-suite | infra-only
SENSITIVITY: phi | pii | financial | public | none
ENTRY_POINTS: <comma-separated list of executable names, or "none">
SUMMARY COMPLETE
```

**TYPE guidance**:
- `deployable-service` — runs as a long-lived process (API server, background worker, ECS task)
- `library` — shared code imported by other services, not deployed independently
- `cli` — command-line tool run on demand
- `test-suite` — integration, BDD, or e2e test runner
- `infra-only` — no application runtime (pure Terraform, scripts, configuration)

**SENSITIVITY guidance**:
- `phi` — handles Protected Health Information (medical records, diagnoses, prescriptions)
- `pii` — handles Personally Identifiable Information (names, emails, addresses)
- `financial` — handles payment, billing, or financial data
- `public` — serves only public/non-sensitive data
- `none` — infrastructure or tooling with no user data

**ENTRY_POINTS**: list the sub-executable names from the context (e.g. `server`, `worker`, `cli`).
If none are listed, write `none`.
