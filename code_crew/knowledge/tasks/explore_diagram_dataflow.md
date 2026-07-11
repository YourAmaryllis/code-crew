---
type: CrewAI Task
title: Architectural Data Flow Diagram Generation
description: >
  Generate a Mermaid architectural data flow diagram from pre-extracted service
  connections. Shows how data moves between services, data stores, queues, and
  external services — without security annotations (no trust boundaries, no
  sensitivity labels). Those are added by /threat.
tags: [explore, diagram, dataflow]
agent: architect
expected_output: >
  A valid Mermaid graph TD block showing service-to-service data flows.
  Output only the diagram — no explanation, no markdown prose.
---

You are generating an **architectural data flow diagram** from a set of pre-extracted
inter-service connections. The context below contains:
- A list of `FROM → CONNECTS_TO` pairs gathered from service code analysis
- The list of external services detected in the codebase

**Your task**: produce a Mermaid `graph TD` diagram showing data flows between
all services, data stores, message queues, and external services.

**Node shapes** — use these Mermaid shapes to distinguish node types:
- Deployable services: `svc["service name"]` (rectangle)
- Databases / data stores: `db[("database name")]` (cylinder)
- Message queues: `q[/"queue name"/]` (parallelogram)
- External services / APIs: `ext["External Service"]:::external` (dashed border)
- End users / browsers: `user(["User"])` (rounded rectangle)

**Edge labels** — label each arrow with the mechanism:
- `-->|"HTTP"|` for REST/gRPC calls
- `-->|"SQL"|` for database reads/writes
- `-->|"cache"|` for Redis/Memcached
- `-->|"SQS"|` for queue writes
- `-->|"consume"|` for queue reads (consumer ← queue direction)
- `-->|"SDK"|` for third-party API calls

**What to show:**
- Every connection from the CONNECTS_TO inventory below
- External services from the external services list (even if no CONNECTS_TO line points to them — they were detected from infra)
- A generic `User(["User"])` node → entry-point service if the service has TYPE=deployable-service or frontend

**What NOT to show:**
- Trust boundaries (added by /threat)
- Sensitivity labels on data (added by /threat)
- Internal implementation details (goroutines, internal method calls)
- Test harnesses or developer tooling

**Output format** — output ONLY the Mermaid diagram, starting with `graph TD`.
Use the classDef for external nodes:

```
graph TD
    User(["User"])
    frontend["<frontend service>"]
    backend["<backend service>"]
    db[("PostgreSQL")]
    cache[("Redis")]
    queue[/"dataset-conversion queue"/]
    worker["<worker service>"]
    ExtAuth["Auth0"]:::external

    User -->|"HTTPS"| frontend
    frontend -->|"HTTP"| backend
    backend -->|"SQL"| db
    backend -->|"cache"| cache
    backend -->|"SQS"| queue
    queue -->|"consume"| worker
    backend -->|"SDK"| ExtAuth

    classDef external fill:#f5f5f5,stroke:#999,stroke-dasharray:4 4
```

If a CONNECTS_TO target cannot be matched to a known service or data store, add it
as a plain rectangle node with a `?` suffix: `unknown["<target-name> (?)"]`.

Output only the `graph TD` block — no title, no explanation.
