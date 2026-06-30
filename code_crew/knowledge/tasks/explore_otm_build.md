---
type: CrewAI Task
title: OTM Threat Model Build
description: Security architect generates a complete OpenThreatModel YAML for one project scope
tags: [explore, threat-model, otm, stride, plot4ai, linddun, hipaa]
agent: architect
expected_output: >
  A complete, valid OpenThreatModel v0.2.0 YAML document for the given project.
  Ends with OTM BUILD COMPLETE.
---

You are generating a complete OpenThreatModel (OTM) v0.2.0 YAML for one project. The project scope, component inventory, active stacks, infrastructure modules, and a list of key files are provided in your context.

**CRITICAL: Write the YAML directly in your text response. Do NOT call any function or tool named `generate_otm`, `create_otm`, `write_file`, or similar. There is no such tool — attempting to call one will fail. Your only tools are `workspace_reader` (to read source files) and `knowledge_reader` (to load reference docs). The OTM YAML must appear as plain text in your reply.**

**Manager instructions (enforced before each section):**
- Before Section 1: read all `dependency-manifest` files listed in Key files (go.mod, package.json, requirements.txt). These reveal external library dependencies and cloud SDK usage — the primary signal for external services.
- Before Section 3: read all `entry-point` files listed in Key files (main.go, server.go, etc.) for each component in scope. These show what the component does, what it connects to, and what data it handles.
- Before Section 4: read any `terraform-module` files relevant to this project's components. These reveal databases, queues, ECS tasks, Lambda functions, and network topology.
- After each section: verify it is complete and non-empty before proceeding. If a section has fewer items than expected given the component inventory, direct the agent to read more source files before continuing.
- Do not let the agent skip to the final YAML output before all six sections have been worked through.

Work through each section in order. Do not skip sections.

---

## Section 1 — External service discovery

Before writing anything, read the dependency manifests for every component in scope. Look for:
- Go: `go.mod` — external module paths reveal AWS SDK usage (s3, sqs, ses, bedrock, sts, secretsmanager), Auth0, StreamChat, OpenSearch clients, GCS, etc.
- Node/TypeScript: `package.json` — dependencies reveal frontend auth (Auth0 SDK), chat (Stream), analytics, etc.
- Python: `requirements.txt` / `pyproject.toml` — boto3, anthropic, openai, etc.

List every external service discovered. You will reference these as external components in Section 3.

---

## Section 2 — trustZones

Define the trust boundaries present in this system. Common zones:
- `internet` — public internet, untrusted (rating: 0)
- `customer-network` — customer's private infrastructure (rating: 10) — use if a component runs on customer's systems
- `private` — internal VPC / private subnets (rating: 75)
- `data` — persistent storage layer (rating: 80)
- `management` — CI/CD, admin access, IaC (rating: 85)

Only include zones that apply.

---

## Section 3 — assets

List every data asset this system handles. For each:
- `name` / `id` — human name and kebab-case id
- `risk.confidentiality` / `risk.integrity` / `risk.availability` — HIGH / MEDIUM / LOW
- `description` — one sentence: what is this data and who is it sensitive to?

Healthcare context: PHI (Protected Health Information) is always HIGH/HIGH/HIGH. Credentials and tokens are HIGH/HIGH/MEDIUM.

Typical assets: PHI/clinical data, auth tokens (JWT, mTLS certs), dataset files, audit logs, model outputs, API keys / secrets, PII (emails, names).

---

## Section 4 — components

Read the entry-point files (main.go, server.go, etc.) for each component before writing this section.

For each component in the project scope:
- Set `type` correctly: `service`, `database`, `queue`, `external-service`, `actor`, `lambda`, `ecs-task`
- Set `parent.trustZone` to the correct zone id from Section 2
- List `assets.processed` and `assets.stored` using asset ids from Section 3
- Write a clear `description` — one sentence saying what this component does

For external services discovered in Section 1 (Auth0, S3, SQS, StreamChat, etc.): add each as a component with `type: external-service` and `parent.trustZone: internet`.

For databases: read the relevant Terraform module (`terraform-module` files) to confirm what database engine, storage type, and encryption settings are used.

Include actors: `End User (Data Buyer)`, `End User (Data Seller)`, `Admin/Operator`, and any system actors.

Do NOT invent components not in the provided inventory or discovered via file reading.

---

## Section 5 — dataflows

List the significant data flows between components. For each:
- `name` / `id` — short label and kebab-case id
- `source` / `destination` — component ids from Section 4
- `protocol` — HTTPS, mTLS, SQS, S3, PostgreSQL, gRPC, etc.
- `assets` — asset ids that travel in this flow
- `authentication` — JWT, mTLS, IAM Role, API Key, None

Focus on flows that carry sensitive assets. Cover:
- User → frontend → backend
- Backend → database
- Backend → external services (Auth0, S3, SQS, StreamChat, Bedrock)
- Any cross-trust-zone flows (highest risk)
- Customer-side components → Loopora-side endpoints (if in scope)

---

## Section 6 — threats

Apply the appropriate framework(s) per component type. A single OTM file can mix framework categories — use the `categories` array on each threat to identify the framework.

**Framework selection rules**:
- **STRIDE** (always): Apply to all API endpoints, services, data stores, auth flows, and trust boundaries.
  Categories: `Spoofing`, `Tampering`, `Repudiation`, `Information Disclosure`, `Denial of Service`, `Elevation of Privilege`
- **PLOT4ai** (AI/ML components): Apply if any component in scope is an LLM inference endpoint, embedding store, RAG pipeline, training/fine-tuning pipeline, data curation pipeline, data guide service, model registry, or agent/tool-calling system. Detect these by looking for `anthropic`, `openai`, `bedrock`, `langchain`, `transformers`, `llama` imports in `go.mod`/`requirements.txt`, or AI processing logic in entry-point files read in earlier sections.
  Categories: `Output Control`, `Privacy Violation`, `Linkability`, `Transparency`, `Security Breach`, `Availability`, `Fairness`, `Accountability`
- **LINDDUN** (personal-data flows): Apply if the system processes PII or PHI and GDPR, CCPA, or HIPAA stacks are active.
  Categories: `Linking`, `Identifying`, `Non-repudiation`, `Detecting`, `Data Disclosure`, `Unawareness`, `Non-compliance`
- **DIE** (cloud-native services): Apply if any component runs as an ECS task, Lambda, or container. Evaluate blast radius, artifact immutability, and credential lifetime.
  Categories: `Distributed`, `Immutable`, `Ephemeral`

For each threat:
- `id` — T-<three-digit-number>
- `name` / `description` — what could go wrong and what impact it has
- `categories` — one or more category names from the applicable framework(s) above
- `risk.likelihood` / `risk.impact` — HIGH / MEDIUM / LOW
- `targetedComponents` / `targetedAssets` — ids from Sections 3–4

**Minimum coverage per component type** (see `threat-dragon` knowledge for full table):
- Public API endpoint: Spoofing, Tampering, Information Disclosure, Denial of Service (STRIDE)
- Data store: Tampering, Information Disclosure, Repudiation (STRIDE)
- ECS task / Lambda: Distributed (blast radius), Immutable (signed image), Ephemeral (credential TTL) (DIE)
- LLM / inference endpoint: Output Control, Security Breach, Privacy Violation, Accountability (PLOT4ai)
- Data curation pipeline: Security Breach (data poisoning), Fairness (dataset bias), Accountability (PLOT4ai)
- Container attestation service: Security Breach (forged attestation), Immutable (result integrity), Accountability (PLOT4ai + DIE)
- Embedding store: Privacy Violation, Linkability, Security Breach (PLOT4ai)
- Agent / tool-calling: Output Control, Accountability, Availability (PLOT4ai)

If HIPAA/GDPR stacks are active, include LINDDUN threats:
- Unlawful PHI retention (data not deleted on request)
- Inadequate audit logging for PHI access
- Cross-border PHI transfer without safeguards
- Re-identification from quasi-identifiers in health data

Focus on HIGH-impact threats. Aim for 8–15 threats for a typical service.

---

## Section 7 — mitigations

For each threat from Section 6:
- `id` — M-<three-digit-number>
- `name` / `description` — control that addresses the threat
- `risk.likelihood` / `risk.impact` — residual risk AFTER mitigation
- `state` — `implemented`, `planned`, or `not-applicable`
- `mitigatedThreats` — threat ids this mitigation addresses

Check entry-point files for evidence of existing controls (TLS, JWT validation, mTLS, IAM policies, audit logging, input validation) before marking `state: implemented`. If you cannot confirm in code, use `planned`.

---

## Output format

Write the complete OTM as plain YAML text in your response. Do not call any function or tool to produce it. End with:
```
OTM BUILD COMPLETE
```

Follow this structure exactly:

```yaml
otmVersion: 0.2.0

project:
  name: <project name>
  id: <project-id>
  description: '<description>'
  owner: Security Lead
  attributes:
    stacks: [<stack list>]

representations:
  - name: Architecture Diagram
    id: arch-diagram
    type: diagram

trustZones:
  - ...

assets:
  - ...

components:
  - ...

dataflows:
  - ...

threats:
  - ...

mitigations:
  - ...
```
