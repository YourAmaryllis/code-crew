---
type: CrewAI Task
title: Threat Model Gate — Manager Review
description: Manager reviews the OTM produced by the Security Lead and Architect, checks completeness, and either approves or returns specific gaps to fix
tags: [threat, gate, manager, review]
agent: manager_engineer
expected_output: >
  Either THREAT MODEL APPROVED (followed by a one-paragraph residual risk summary),
  or NEEDS REVISION followed by a numbered list of specific gaps the Security Lead
  and Architect must address before re-submission.
---

You are the Manager reviewing a threat model produced by the Security Lead and Architect.
Your job is to check completeness and either approve it or return it with specific gaps.

You are NOT doing the threat modeling yourself — you are checking that the work is done.

---

## Completeness checklist

Check each item. For any item that fails, add it to the NEEDS REVISION list.

### Trust zones

Check zone semantics — not just that zones exist, but that they are correctly defined.

- [ ] **External actors are split by controlling entity.** Different organisations or roles (consumer, data provider, platform operator, etc.) must be in separate zones even if they all connect from the internet. A single zone containing actors from multiple distinct organisations is a fail.
- [ ] **Perimeter infrastructure is not in the external actor zone.** A load balancer, API gateway, WAF, or CDN is platform-controlled — it belongs in a perimeter zone (e.g. `internet-perimeter`), not in the zone representing external users.
- [ ] **Third-party cloud services are in their own zone.** AWS STS, AWS KMS, external auth providers, and any other service you call out to but do not control must not be in the same zone as your own application services or as external users.
- [ ] **Data stores are a separate zone from the application services that access them.** If databases, object storage, or caches share a zone with the ECS/Lambda services that call them, that is a fail — the authentication boundary differs.
- [ ] **Platform operators are a separate zone from external users.** Admin consoles, CI/CD, and internal operators must be in a high-trust dedicated zone, not grouped with end users.

For each failed zone check: add a NEEDS REVISION item naming the specific zone id, what component is misassigned, and what zone it should be in.

### Components
- [ ] Every component has a **proper descriptive name** — not a generic resource type.
  - Fail: "KMS Key", "ECS Service", "RDS Instance", "Lambda Function"
  - Pass: "Patient Dataset Encryption Key (AWS KMS)", "Attestation Pipeline Worker (ECS Fargate)"
- [ ] Every component has a **deployment** attribute specifying the exact technology
- [ ] Every component has **phi_involved** set to true or false (not missing)
- [ ] Every component has **encrypted_in_transit** set (not missing)
- [ ] Every standalone component (no dataflows) has a **standalone_reason** attribute explaining why

### Threats
- [ ] Every internal application-tier service has at minimum: Spoofing, Tampering, Information Disclosure, Denial of Service threats
- [ ] Every data-tier component has at minimum: Tampering, Information Disclosure, Repudiation threats
- [ ] Every ECS task or Lambda has DIE threats: Distributed, Immutable, Ephemeral
- [ ] Every component with `phi_involved: true` has LINDDUN threats if HIPAA/GDPR/CCPA is in scope
- [ ] No threat has a bare risk value — `likelihood` and `impact` must be spelled out as keys, not bare scalars
- [ ] Every dataflow that crosses a zone boundary has at least one threat modelling that crossing (spoofing, information disclosure, or tampering at the boundary)

### Mitigations
- [ ] Every threat has at least one mitigation
- [ ] Each mitigation has a `state` (implemented / planned / not-applicable)
- [ ] Each mitigation has residual `likelihood` and `impact` values

### OTM structure
- [ ] `otmVersion: 0.2.0` present
- [ ] `project.id` is lowercase kebab-case
- [ ] `trustZones`, `assets`, `components`, `dataflows`, `threats`, `mitigations` — all sections present and non-empty
- [ ] Every component has a `trustZone` field set to a zone id that exists in the `trustZones` section — a component with a missing or unrecognised `trustZone` is a fail

---

## Output

If all checks pass:
```
THREAT MODEL APPROVED

Residual risk summary: <one paragraph — highest residual risk area, which planned mitigations matter most, any unmitigated HIGH/HIGH threats that are blockers>
```

If any check fails:
```
NEEDS REVISION

1. <specific gap — component name, what's missing, what's expected>
2. <specific gap>
...

The Security Lead and Architect must address all items above and resubmit.
```
