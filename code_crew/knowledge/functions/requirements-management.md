---
name: SDLC-Product-RequirementsManagement
description: BRD and TRD creation, compliance requirements, requirement traceability, and change control for requirements
metadata:
  type: process
  role: product
  phase: "1, 2, 4, 8"
---

# Requirements Management

Requirements flow from business intelligence through to technical specifications and user stories. This document covers how requirements are captured, managed, and updated.

---

## Phases

| Phase | Deliverable | Owner |
|-------|------------|-------|
| 1 | Business intelligence (market research, user interviews) | Product Owner |
| 2 | Business Requirements Document (BRD) | Business Analyst / PO |
| 3b | Compliance Requirements Document (CRD) | Compliance Officer |
| 4 | Technical Requirements Document (TRD) | Tech Lead |
| 8 | TRD update (post-architecture alignment) | Tech Lead |

---

## Business Requirements Document (BRD)

The BRD captures what the business needs — in business language, not technical language.

**Structure:**
```markdown
# BRD: <Feature/Initiative Name>

## Business Context
## Objectives and Success Metrics
## User Personas Affected
## Business Requirements

| ID | Description | Priority | Source |
|----|-------------|----------|--------|
| BR-2026-001 | ... | High | CEO |

## Out of Scope
## Assumptions and Constraints
## Stakeholder Sign-off
```

- BRDs are stored in `designs/PLAN/` as OKF Markdown files
- Each requirement has a unique ID: `BR-YYYY-NNN`
- Priority: High / Medium / Low (MoSCoW: Must/Should/Could/Won't)
- Source: who requested it (CEO, customer, compliance, engineering)

---

## Compliance Requirements Document (CRD)

Compliance requirements are captured separately because they have different governance:

- CRD is written by the Compliance Officer, reviewed by Legal
- Each requirement maps to a regulation: GDPR, HIPAA, SOC 2, etc.
- CRD IDs: `CR-YYYY-NNN`
- Verification criteria defined for each control

Stored in `designs/CRD/`.

---

## Technical Requirements Document (TRD)

The TRD translates business requirements into technical specifications.

**Structure:**
```markdown
# TRD: <Feature Name>

## Source Requirements (BR/CR IDs)
## Technical Requirements

| ID | Description | Type | Trace |
|----|-------------|------|-------|
| TR-2026-042 | System shall send verification email on registration | Functional | BR-2026-015 |
| TR-2026-043 | Email verification link expires after 24 hours | Non-Functional | BR-2026-015, CR-2026-008 |

## Non-Functional Requirements
(Performance, reliability, scalability, security targets)

## Technical Constraints
## Open Questions
```

- TRD IDs: `TR-YYYY-NNN`
- Type: Functional / Non-Functional / Security / Performance / Compliance
- Trace: links back to BR or CR that generated this TR

---

## Requirement Traceability

Every artifact links back to requirements:

```
BR-2026-001 (BRD)
  └── TR-2026-042 (TRD)
        └── PROJ-92 (Jira user story)
              └── feat(auth-svc): add email verification [REQ:TR-2026-042] PROJ-92 (commit)
                    └── BDD scenario @PROJ-92 (test)
```

The `[REQ:TR-2026-042]` in commit messages enables automated traceability analysis.

---

## Change Control for Requirements

Requirements changes after sprint commitment go through change control:

1. Submit change request (describe: what changed, why, impact)
2. Impact analysis: which TRs, stories, and code are affected?
3. Review and approval:
   - Business change → PO approves
   - Technical change → Tech Lead approves
   - Compliance change → Compliance Officer + Legal approve
4. Update BRD/TRD; update affected Jira stories
5. Log in change control record

See: [change-control.md`](change-control.md)

---

## AI Assistance for Requirements

AI can assist with:
- Drafting BRD sections from meeting notes or interview transcripts
- Translating BRD items into TR-level specifications
- Identifying gaps in AC coverage
- Generating compliance requirement mappings

Prompt pattern for BRD drafting:
```
Here are notes from our customer discovery interviews. 
Generate a Business Requirements Document with objectives, 
user personas, and requirement table using BR-YYYY-NNN IDs.
Identify any compliance concerns to flag for the compliance officer.
```

All AI-generated requirements are reviewed and approved by the Product Owner before use.
