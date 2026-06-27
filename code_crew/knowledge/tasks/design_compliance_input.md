---
type: CrewAI Task
title: Compliance Design Review
description: Compliance Officer reviews the draft ADD for regulatory requirements — data handling, retention, consent, audit trails — before the ADD is finalised
tags: [design, compliance, gdpr, hipaa, soc2, pre-implementation]
agent: compliance_officer
expected_output: >
  A compliance design review covering: applicable regulatory frameworks, data handling
  requirements, retention schedules, consent mechanisms needed, audit trail requirements,
  and any documentation obligations. Concludes with COMPLIANCE APPROVED or
  COMPLIANCE CONCERNS: [list of blocking issues].
---

Review the draft ADD and security input for regulatory compliance implications.

**Step 1 — Load compliance context.**

Use `knowledge_reader` to load the active compliance stack documents. Which frameworks apply depends on the data types in the ADD:
- `hipaa` if the ADD involves health data or PHI
- `gdpr` if the ADD involves EU personal data
- `soc2` always for production systems
- `cfr-part-11` if the ADD involves regulated records or audit trails
- `nist` if applicable

**Step 2 — Identify data handling requirements.**

Based on the draft ADD and security classification:

1. **Data retention** — for each new data type, what is the retention period? Who defines it?
2. **Data minimisation** — is the data truly needed? Could a pseudonym or aggregate suffice?
3. **Consent** — does the ADD introduce a new use of personal data? Is prior consent sufficient or is new consent needed?
4. **Cross-border transfers** — does any data flow cross jurisdictions? What safeguards are needed?
5. **Data subject rights** — does this ADD affect the ability to exercise GDPR right-to-erasure, access, or portability?

**Step 3 — Audit trail requirements.**

For each sensitive action in the ADD:
- What events must be logged for regulatory purposes?
- What data must the audit entry contain (actor, resource, action, timestamp, outcome)?
- What is the required retention period for audit logs?
- Who has access to audit logs?

**Step 4 — Documentation obligations.**

Does this ADD require:
- An updated Data Processing Agreement (DPA)?
- A new entry in the Record of Processing Activities (RoPA)?
- A Data Protection Impact Assessment (DPIA)?
- A new CRD (Compliance Requirements Document) section?

**Step 5 — Output.**

Produce a **Compliance Addendum** section to add to the ADD:
```
## Compliance Requirements (added by Compliance Review)

Active frameworks: <list>

Data handling:
  - Retention: <data type> → <period> (<legal basis>)
  - Consent basis: <basis>
  - Cross-border: <safeguard if applicable>

Audit requirements:
  - <event>: <required log content>

Documentation obligations:
  - <obligation>: <action required>
```

Conclude with:
- **COMPLIANCE APPROVED** — no blocking compliance concerns; ADD may be finalised
- **COMPLIANCE CONCERNS** — list each blocking issue; the ADD must address these before finalisation
