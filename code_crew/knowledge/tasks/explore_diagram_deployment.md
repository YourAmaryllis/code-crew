---
type: CrewAI Task
title: Deployment Diagram Generation
description: >
  Generate a Mermaid deployment diagram from the codebase survey context.
  Shows where each service runs (compute platform, hosting tier) and how
  services are grouped by environment and infrastructure type.
tags: [explore, diagram, deployment]
agent: architect
expected_output: >
  A valid Mermaid graph TD block showing services grouped by compute platform.
  Output only the diagram — no explanation, no markdown prose.
---

You are generating a **deployment diagram** from a codebase survey.
The context below contains: detected stacks, CI/CD tooling, Terraform infrastructure
modules, and service summaries with their TYPE and SENSITIVITY fields.

**Your task**: produce a Mermaid `graph TD` diagram that shows where each deployable
service runs. Group nodes by compute platform using `subgraph` blocks.

**What to show:**
- Each `deployable-service`, `worker`, `lambda`, `frontend` from the service summaries
- Grouped by compute platform — infer from stacks + infra modules:
  - ECS Fargate → `subgraph ECS["ECS Cluster"]`
  - Lambda functions → `subgraph Lambda["Lambda"]`
  - Static sites (React/Next.js + CDN/static infra module) → `subgraph Static["Static / CDN"]`
  - Container registry → show as ECR node if detected
- Environment tiers (dev / staging / prod) as outer subgraphs if infra has environment dirs
- External services (CDN, identity providers, third-party APIs) outside the cloud boundary
- Sensitivity labels in node labels when PHI or PII: `portal-backend["portal/backend\n(ECS · PII)"]`

**What NOT to show:**
- Libraries, tools, test harnesses, infra-only units
- Internal implementation details
- Exact port numbers, IP addresses, ARNs

**Node naming**: use the service path as the node label, e.g. `portal-backend["portal/backend"]`.
Node IDs must be valid Mermaid identifiers (replace `/` with `-`).

**Output format** — output ONLY the Mermaid diagram, starting with `graph TD`:

```
graph TD
    subgraph Cloud["Cloud (provider / region)"]
        subgraph ECS["ECS Cluster"]
            ...
        end
        subgraph Lambda["Lambda"]
            ...
        end
    end
    subgraph Static["Static / CDN"]
        ...
    end
    ExternalService["External Service\n(external)"]:::external
    classDef external fill:#f5f5f5,stroke:#999,stroke-dasharray:4 4
```

If a compute platform cannot be determined for a service, place it in a generic
`subgraph Compute["Compute"]` block rather than omitting it.

Output only the `graph TD` block — no title, no explanation.
