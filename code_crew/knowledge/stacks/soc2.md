---
name: Compliance-SOC2
description: SOC 2 Trust Service Criteria checklist — Security, Availability, Confidentiality controls for code and infrastructure review
metadata:
  type: compliance
  framework: SOC2
  version: "2017 Trust Service Criteria"
  activate: explicitly — set in CODE_CREW_STACKS or stacks: in .code-crew/config.yaml
---

# Compliance: SOC 2

SOC 2 applies to any SaaS or cloud service that stores or processes customer data. The five Trust Service Criteria are: **Security** (CC), **Availability** (A), **Processing Integrity** (PI), **Confidentiality** (C), and **Privacy** (P). Most implementations require Security at minimum; scope additional criteria based on customer contracts and audit scope.

Add `soc2` to `stacks:` in `.code-crew/config.yaml` for any project undergoing or maintaining SOC 2 certification.

---

## CC6 — Logical and Physical Access

- [ ] Access to production systems is role-based; least-privilege enforced
- [ ] All privileged access (admin, production DB, infra changes) is logged
- [ ] Access is provisioned through a formal process and de-provisioned promptly on role change
- [ ] Multi-factor authentication required for all production system access
- [ ] No shared service accounts; individual identities for all users
- [ ] API keys and service credentials are rotated on schedule and on personnel change
- [ ] SSH / bastion access is JIT (just-in-time) — no standing access to production

## CC7 — System Operations

- [ ] Security events (auth failures, access denials, config changes) are logged to a centralized, tamper-resistant store
- [ ] Anomaly detection or alerting is in place for unusual access patterns
- [ ] Vulnerability scans run on merge (SAST, dependency scan, container scan)
- [ ] Critical/High CVEs in dependencies block deployment
- [ ] Infrastructure drift detected (automated plan vs. actual comparison)
- [ ] Incident response runbook exists and is referenced in infrastructure docs

## CC8 — Change Management

- [ ] All production changes go through version-controlled code (no manual infra changes)
- [ ] Every change has a ticket reference and was reviewed before merge
- [ ] Deployments are automated and reproducible — no snowflake deploys
- [ ] Rollback procedure documented and tested for this service
- [ ] Feature flags or canary deployments used for high-risk changes

## CC9 — Risk Mitigation

- [ ] New third-party integrations have been assessed for data exposure risk
- [ ] Vendor risk review documented for any new SaaS dependency that touches customer data
- [ ] Data classification applied to all new data stores (see `terraform` data classification)

## A1 — Availability

- [ ] Service has defined RTO and RPO; this feature does not degrade them
- [ ] Health checks and readiness probes configured for all new services
- [ ] Backups cover all new data stores; restoration tested at least once
- [ ] No single points of failure introduced by this change
- [ ] Load testing or capacity analysis performed if change affects peak load paths

## PI1 — Processing Integrity

- [ ] All data transformations are idempotent or guarded against double-processing
- [ ] Input validation at every system boundary (API, event consumer, file ingestion)
- [ ] Processing errors are logged with enough context to replay or investigate
- [ ] Reconciliation mechanism exists for any financial or regulated data pipeline

## C1 — Confidentiality

- [ ] Customer data is not accessible across tenant boundaries (multi-tenant isolation verified)
- [ ] Data classification tracked for all new stores (confidential data identified)
- [ ] Confidential data not included in logs, error messages, or debugging output
- [ ] Data shared with sub-processors is scoped to minimum necessary

## P Series — Privacy (if in scope)

- [ ] Privacy notice updated if new data types are collected
- [ ] Data retention policy applied to new data stores
- [ ] Data subject rights requests (access, deletion, correction) supported for new data
- [ ] Consent recorded and auditable for new data collection points

---

## Evidence Artifacts

SOC 2 auditors require evidence. Flag if missing:
- [ ] Change management: every production change has a linked ticket and PR
- [ ] Access review: access list for production systems is reviewable and current
- [ ] Vulnerability management: scan results stored per PR/release
- [ ] Incident log: incidents documented with timeline, impact, resolution
- [ ] Vendor inventory: list of sub-processors with data types shared

---

## Common Violations (flag as HIGH)

- Manual production change with no ticket or PR
- Shared service account or shared credentials
- Customer data accessible across tenant boundary
- No log of privileged access to production
- New third-party integration with no vendor risk assessment
- Dependency with Critical/High CVE shipped to production

---

## Review Output Format

```
SOC 2 REVIEW
Criteria in scope: [Security / Availability / PI / Confidentiality / Privacy]

CC6 Logical Access:    PASS / FAIL — [detail]
CC7 System Ops:        PASS / FAIL — [detail]
CC8 Change Mgmt:       PASS / FAIL — [detail]
A1  Availability:      PASS / FAIL / N/A
PI1 Processing Int.:   PASS / FAIL / N/A
C1  Confidentiality:   PASS / FAIL — [detail]

SOC2: COMPLIANT or NON-COMPLIANT — [list of blocking findings]
```
