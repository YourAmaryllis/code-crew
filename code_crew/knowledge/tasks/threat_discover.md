---
type: CrewAI Task
title: Threat Model Discovery — Phase 1 (Architect)
description: Architect reads project source and infrastructure files then outputs trustZones and components YAML sections. Stops after Phase 1 — no threats, no mitigations.
tags: [threat, threat-model, otm, discovery]
agent: architect
expected_output: >
  A trustZones: YAML section followed by a components: YAML section covering every
  component in the project. Ends with exactly: DISCOVERY COMPLETE
---

You are performing **Phase 1 threat model discovery** for the project described above.

Your task is to read the project source and infrastructure files, then output:
1. The `trustZones:` YAML section
2. The `components:` YAML section

**CRITICAL: Stop after the components section. Do NOT output threats, mitigations, or a full OTM YAML. Do NOT write any files.**

---

## Step 1 — Analyse the pre-scanned context

**DO NOT call any tools.** The pre-scanned context above already contains everything you need:
- Dependency manifest (libraries, frameworks, AWS SDK usage)
- Service entry point
- Terraform/infra resource names and types
- Architecture docs (SAD, ADD)

Work entirely from the pre-scanned content. Calling `knowledge_reader`, `workspace_reader`,
or any other tool will waste time and produce no new information — those tools read internal
code-crew documentation, not this project's source files.

---

## Step 2 — Output `trustZones:` YAML

After reading, output the `trustZones:` section. Use this format exactly:

```yaml
trustZones:
  - name: "<entity-based name>"
    id: <kebab-case-id>
    description: "<one sentence — who controls it and what credential is required>"
    rating: <0|10|25|50|75|85|90>
```

**Trust zone rules:**

Name a zone after the **principal entity** that owns or controls its components — the organisation, team, or role. Test: "This is _____'s zone" should sound natural. Names like `data-tier`, `platform-services`, `perimeter-infrastructure` describe resource types or network topology, not owners — reject them.

For each component, ask before creating a new zone:
1. Who operates this component?
2. Could an attacker who breaches the outer boundary of the current zone also reach this component?
3. Is there already a zone that shares the same operator, same network environment, and same external attack surface?
   - **Yes → assign the component to that existing zone. Do NOT create a new zone.**
   - **No → create a new zone named after the controlling entity.**

Components belong in the same trust zone when they share **all three** of these:
- **Same owner/operator** — the same team or organisation controls them
- **Same environment** — they run in the same network, cloud account, or cluster
- **Same external attack surface** — if an attacker breaches the perimeter, they can reach all of them

**Sub-zones:** You may define a trust zone *inside* another trust zone when there is a meaningful internal boundary (e.g., a public-facing subnet inside a private VPC, or a data tier with stricter access controls within the same org's platform). Use the `parent` field on the inner zone to reference the outer zone. Sub-zones let you model internal segmentation without claiming those components are independently controlled or externally separated.

Additional rules:
- Different external actor categories → different zones (consumer ≠ admin ≠ partner)
- Third-party cloud services operated by another organisation (external SaaS, third-party APIs) → own zone
- Operators/admins → own zone, separate from end users

**Ratings:** 0=fully public/no auth, 25=authenticated external (different org), 50=authenticated partner/mTLS,
75=internal platform (same org, IAM or internal auth — covers ALB, app services, and data stores sharing the same operator), 85=privileged/admin operators

Output ONLY the `trustZones:` YAML block — no prose before or after it.

---

## Step 3 — Output `components:` YAML

Immediately after the trust zones, output the `components:` section. Use this format exactly:

```yaml
components:
  - name: "<Proper Name (Deployment Type)>"
    id: <kebab-case-id>
    type: service|database|queue|lambda|ecs-task|external-service|actor
    parent:
      trustZone: <zone-id-from-step-2>
    attributes:
      deployment: "<specific technology, e.g. AWS ECS Fargate, AWS RDS PostgreSQL>"
      encrypted_in_transit: true|false
      encrypted_at_rest: true|false
      phi_involved: true|false
      phi_categories: []
    connects_to: [<component-id>, ...]
    receives_from: [<component-id>, ...]
    description: "<one sentence — what it does and who uses it>"
```

**Naming rule:**
- Bad: `KMS Key`, `ECS Service`, `RDS Instance`, `Lambda Function`
- Good: `User Data Encryption Key (AWS KMS)`, `Data Processing Worker (AWS ECS Fargate)`
- The name must say WHAT it IS and WHO owns or uses it; `deployment` says HOW it runs.

**Important:**
- `connects_to` and `receives_from` are at the component top level (not inside `attributes`)
- These fields record direct dataflows from component to component
- Every component in an internal-platform zone must have at least one connection
- If a component has neither, add `standalone_reason: <explanation>` inside `attributes`
- Include external actors (e.g. human users, external systems) as components of type `actor`
  or `external-service` in their appropriate zone
- If `### External services detected in source` is present in your context, include each
  listed service as a component with `type: external-service` in an appropriate external
  trust zone. Add a trust zone for third-party services if one doesn't already exist.

Output ONLY the `components:` YAML block — no prose before or after it.

---

## Step 4 — Stop

After outputting both YAML sections, output exactly:

```
DISCOVERY COMPLETE
```

Do NOT output anything else. Do NOT generate threats, mitigations, or a full OTM YAML.
Python will handle those phases separately.
