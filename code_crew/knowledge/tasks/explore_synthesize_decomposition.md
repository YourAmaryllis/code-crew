---
type: CrewAI Task
title: Service Decomposition Synthesis
description: >
  Given structure.md (containing unit summaries from the per-unit deep-dive), produce
  the definitive decomposition: which areas are real services, how large ones break down,
  OTM project scope, and a Mermaid diagram.
tags: [explore, synthesis, decomposition]
agent: architect
expected_output: >
  REAL_SERVICE / NOT_SERVICE lines, optional DECOMPOSE lines, PROJECT blocks, and a
  graph TD diagram. Ends with DECOMPOSITION COMPLETE.
---

Read the UNIT_SUMMARY blocks in the context and output the following — in order, no
extra prose, no echoing these instructions.

**REAL_SERVICE** for any unit whose TYPE is deployable-service, worker, lambda, or
frontend, or that has ENTRY_POINTS other than "none".

**NOT_SERVICE** for any unit whose TYPE is library, cli, test-harness, or infra-only.

**DECOMPOSE** only for a REAL_SERVICE that contains 2 or more independently runnable
sub-services (separate long-running processes or containers). A large codebase in one
service is NOT a reason to decompose. Name sub-services by role (server, worker,
frontend) — not by path.

Then one PROJECT block per REAL_SERVICE (use the primary directory name, lowercase
with hyphens, as the id).

Then a graph TD diagram showing REAL_SERVICE nodes and any decomposed sub-services.
If a `## External services` section is present, add each as an external node with
`:::external` styling and draw edges from the internal services that depend on it.

---

Example output (replace with the actual units from the summaries):

REAL_SERVICE: portal | deployable-service with ENTRY_POINTS: cmd/server
NOT_SERVICE: shared | library
DECOMPOSE: attestation → server, worker | has cmd/server and cmd/worker entry points

PROJECT: portal
DESCRIPTION: React + Go web portal serving end-users. Assesses authentication, session handling, and API exposure.
COMPONENTS: portal

PROJECT: attestation-server
DESCRIPTION: Long-running HTTP server for the attestation service. Assesses API endpoints and data validation.
COMPONENTS: attestation/cmd/server

PROJECT: attestation-worker
DESCRIPTION: Queue-driven worker for the attestation service. Assesses job processing and external integrations.
COMPONENTS: attestation/cmd/worker

graph TD
    portal["Portal\n(deployable-service)"]
    attestation["Attestation\n(deployable-service)"]
    attestation --> attestation-server["Attestation Server\n(server)"]
    attestation --> attestation-worker["Attestation Worker\n(worker)"]
    auth0["Auth0\n(external)"]:::external
    portal --> auth0
    classDef external fill:#f5f5f5,stroke:#999,stroke-dasharray:4 4

DECOMPOSITION COMPLETE
