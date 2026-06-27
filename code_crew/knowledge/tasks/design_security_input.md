---
type: CrewAI Task
title: Security Design Review
description: Security Lead reviews the draft ADD for new threat surfaces, data classification, and required security controls before the ADD is finalised
tags: [design, security, threat-model, pre-implementation]
agent: security_lead
expected_output: >
  A security design review covering: new threat surfaces introduced by this design,
  data classification for any new data types, required security controls (as ADD addendum),
  and a starter OTM threat model path. Concludes with SECURITY APPROVED or
  SECURITY CONCERNS: [list of blocking issues that must be addressed in the ADD].
---

Review the draft ADD for security implications and provide input before it is finalised.

**Step 1 — Load security context.**

Use `knowledge_reader` to load:
- `threat-dragon` — OTM format and framework selection guide
- `ai-ml` stack doc if the ADD introduces AI/ML components

**Step 2 — Review the draft ADD.**

Your context includes the draft ADD from the previous task. For each component and data flow:

1. **Data classification** — what data is handled? PII? Health data? Credentials? Classify each.
2. **New trust boundaries** — does this ADD introduce a new trust boundary? What crosses it?
3. **New attack surfaces** — new API endpoints, new data stores, new external integrations?
4. **AI/ML risks** — if AI/ML components: which PLOT4ai categories apply?
5. **Existing threat model** — does `designs/TMD/` have an existing model for this service? If so, which components will change?

**Step 3 — Identify required security controls.**

For each new component or data flow, specify:
- Minimum authentication/authorization requirement
- Data in transit protection requirement
- Data at rest protection requirement
- Input validation requirements
- Logging requirements (what must be auditable)

**Step 4 — Draft OTM threat model path.**

Specify:
- Which OTM file will cover this feature: `designs/TMD/<service>.yaml`
- Which frameworks apply: STRIDE (always) + PLOT4ai (if AI/ML) + LINDDUN (if personal data + GDPR/CCPA)
- Note any existing OTM file that needs to be updated vs. a new file to be created

Do NOT write the full OTM file here — just identify the path and frameworks. The engineer will generate it during implementation.

**Step 5 — Output.**

Produce a **Security Addendum** section to add to the ADD:
```
## Security Requirements (added by Security Review)

Data classification:
  - <data element>: <classification>

Required controls:
  - <component/flow>: <control>

Threat model: designs/TMD/<service>.yaml
Frameworks: STRIDE [+ PLOT4ai] [+ LINDDUN]
```

Conclude with:
- **SECURITY APPROVED** — no blocking security concerns; ADD may be finalised
- **SECURITY CONCERNS** — list each blocking issue; the ADD must address these before finalisation
