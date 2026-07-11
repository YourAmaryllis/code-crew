---
type: CrewAI Task
title: Unit Deep-Dive Summarization
description: >
  Deeply explore one code unit (service, library, or tool) using workspace tools.
  Produce a structured summary and decide if sub-breakdown is needed.
tags: [explore, summarize, unit]
agent: architect
expected_output: >
  UNIT_SUMMARY block with PURPOSE, TYPE, SENSITIVITY, ENTRY_POINTS, DECOMPOSE,
  CONNECTS_TO, and optionally SUB_UNITS. Ends with UNIT_SUMMARY COMPLETE.
---

You are exploring one directory unit of the codebase. Use `workspace_reader` (and
`code_index` if available) to understand what this unit does, how it is structured,
and what data it handles.

**What to read:**
- The README or top-level documentation file first
- The dependency manifest (`go.mod`, `package.json`, `pyproject.toml`, `Cargo.toml`, etc.)
- The main entry point(s) — look for `main.go`, `main.py`, `index.ts`, `cmd/*/`, `bin/`
- A representative handler or route file to understand the API surface
- Stop when you have enough to write the summary — do not exhaustively read every file

**Output exactly this format** (replace only the field values — do not include the comments):

```
UNIT_SUMMARY: <path>
PURPOSE: <what it does, who uses it, key integrations — 2-4 sentences>
TYPE: <type>
SENSITIVITY: <sensitivity>
ENTRY_POINTS: <executables or "none">
DECOMPOSE: <yes | no>
CONNECTS_TO: <connection list or "none">
UNIT_SUMMARY COMPLETE
```

Example for a service with connections:

```
UNIT_SUMMARY: portal/backend
PURPOSE: The portal backend is a Go API server serving end-users. It handles
  HTTP requests, integrates with the auth service, and stores sessions in Redis.
TYPE: deployable-service
SENSITIVITY: pii
ENTRY_POINTS: cmd/server
DECOMPOSE: no
CONNECTS_TO: postgresql (sql), redis (cache), auth-service (http), sqs/dataset-conversion (queue-write)
UNIT_SUMMARY COMPLETE
```

For a unit with multiple independently deployable sub-services, add SUB_UNITS:

```
UNIT_SUMMARY: attestation
PURPOSE: The attestation service manages compliance workflows for provider onboarding.
TYPE: deployable-service
SENSITIVITY: phi
ENTRY_POINTS: cmd/server, cmd/worker
DECOMPOSE: yes
SUB_UNITS: cmd/server, cmd/worker
CONNECTS_TO: postgresql (sql), sqs/pipeline-jobs (queue-consume), auth0 (http)
UNIT_SUMMARY COMPLETE
```

Replace the field values with the actual content for the unit you are exploring.
- UNIT_SUMMARY: the unit's relative path exactly as given (e.g. `shared` or `code_crew/knowledge`)
- PURPOSE: 2–4 sentences on what it does, who uses it, key integrations
- TYPE: one of deployable-service | worker | lambda | frontend | library | cli | test-harness | infra-only
- SENSITIVITY: one of phi | pii | financial | public | none
- ENTRY_POINTS: separately compiled executables (e.g. cmd/server, cmd/worker) or "none"
- DECOMPOSE: yes or no (yes only if the unit has 2+ independently runnable sub-services)
- SUB_UNITS: only present when DECOMPOSE is yes; list each sub-path (e.g. cmd/server, cmd/worker)
- CONNECTS_TO: comma-separated list of `<target> (<mechanism>)` — only connections you can confirm from code.
  Use "none" if no outbound connections are found. Do NOT guess or hallucinate connections.
  Mechanisms: sql | cache | http | grpc | queue-write | queue-consume | pubsub | file | smtp | sdk

**TYPE guidance:**
- `deployable-service` — long-lived HTTP/gRPC server
- `worker` — event-driven or queue-driven background process
- `lambda` — short-lived function triggered by events
- `frontend` — browser application (React, Next.js, etc.)
- `library` — imported by other units, no standalone runtime
- `cli` — command-line tool, run on demand
- `test-harness` — integration, BDD, or e2e test runner
- `infra-only` — Terraform, Docker, CI/CD; no application code

**SENSITIVITY guidance:**
- `phi` — Protected Health Information (medical records, diagnoses, prescriptions, lab results)
- `pii` — Personally Identifiable Information (names, emails, addresses, IDs)
- `financial` — payment, billing, or financial transactions
- `public` — only public/non-sensitive data
- `none` — infrastructure or tooling with no user data

**DECOMPOSE: yes** only if this unit contains 2 or more independently deployable sub-services
— each with its own entry point or infra module. A large codebase in one service is NOT
a reason to decompose. Only decompose if the sub-parts could plausibly run in separate
processes or containers.

If `DECOMPOSE: yes`, list each sub-path under `SUB_UNITS:`. The orchestrator will call
this task again for each sub-unit.

**CONNECTS_TO guidance** — look for these in code:
- Database connections: ORM imports, `sql.Open`, `pgx.Connect`, `redis.NewClient`, etc.
- HTTP calls: `http.NewRequest`, `grpc.Dial`, SDK client constructors for named services
- Queue operations: SQS `SendMessage` (queue-write), `ReceiveMessage` (queue-consume)
- Named target: use the logical service or resource name, not the hostname (e.g. `postgresql`, `redis`, `auth-service`, `sqs/<queue-name>`)
- If you cannot find connection code, write `CONNECTS_TO: none` — do not guess
