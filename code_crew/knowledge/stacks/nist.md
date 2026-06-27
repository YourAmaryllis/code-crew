---
name: Compliance-NIST
description: NIST CSF 2.0 and NIST SP 800-53 Rev 5 controls checklist — Govern, Identify, Protect, Detect, Respond, Recover for code and infrastructure review
metadata:
  type: compliance
  framework: NIST
  references:
    - "NIST CSF 2.0 (2024)"
    - "NIST SP 800-53 Rev 5"
    - "NIST SP 800-171 Rev 3 (CUI)"
  activate: explicitly — set in CODE_CREW_STACKS or stacks: in .code-crew/config.yaml
---

# Compliance: NIST Cybersecurity Framework + SP 800-53

NIST CSF 2.0 and SP 800-53 are used as the foundation for FedRAMP, FISMA, DoD CMMC, and many enterprise security programs. The CSF organizes controls into six Functions: **Govern (GV)**, **Identify (ID)**, **Protect (PR)**, **Detect (DE)**, **Respond (RS)**, **Recover (RC)**.

Add `nist` to `stacks:` for systems subject to FedRAMP, FISMA, CMMC, or enterprise security programs built on NIST.

For CUI (Controlled Unclassified Information) handling under NIST 800-171, enable `nist` and document the CUI scope.

---

## GV — Govern

- [ ] Security and privacy policies documented and accessible to the team
- [ ] Roles and responsibilities for security defined (who owns what control)
- [ ] Risk management strategy documented; acceptable risk levels defined
- [ ] Cybersecurity supply chain risk assessed for new third-party components
- [ ] Legal and regulatory requirements identified and tracked (privacy laws, export controls)

---

## ID — Identify

### Asset Management (ID.AM)
- [ ] New assets (services, data stores, APIs) added to the asset inventory
- [ ] Data classification applied to all new data stores
- [ ] Software inventory updated (new dependencies, runtimes, container images)
- [ ] API contracts documented (new endpoints added to API inventory)

### Risk Assessment (ID.RA)
- [ ] Threat modeling performed for new features that introduce a new attack surface
- [ ] Vulnerabilities in new dependencies assessed before inclusion
- [ ] Impact of a compromise of this feature assessed (data exposure, availability, integrity)

---

## PR — Protect

### Identity and Access Management (PR.AA / AC in SP 800-53)
- [ ] Least-privilege enforced: access rights granted only as needed for the role
- [ ] Separation of duties: no single user can perform conflicting actions (e.g. create + approve)
- [ ] Multi-factor authentication enforced for privileged access
- [ ] Service accounts have no interactive login; permissions scoped to minimum needed
- [ ] Access reviewed on personnel change; de-provisioned within one business day

### Awareness and Training (PR.AT)
- [ ] Security-relevant changes documented so the team can maintain awareness

### Data Security (PR.DS / SC in SP 800-53)
- [ ] Data classified and handled per classification policy
- [ ] Sensitive data encrypted at rest and in transit (see `fips-140-3` if FIPS required)
- [ ] Data integrity maintained and verified (checksums, signatures where applicable)
- [ ] Sensitive data not retained beyond operational need; deletion procedure documented
- [ ] Backups encrypted and integrity-checked; restoration tested

### Information Protection Processes (PR.IP / CM, SI in SP 800-53)
- [ ] Baseline configurations maintained in version control; no undocumented config changes
- [ ] Change management: all production changes via reviewed PR and ticket
- [ ] Input validation at all trust boundaries
- [ ] Error handling does not expose system internals or sensitive data
- [ ] Memory is cleared for sensitive data after use where applicable (key material, credentials)

### Protective Technology (PR.PT / SC)
- [ ] Network communications segmented appropriately (internal services not exposed externally)
- [ ] Communications protected (TLS 1.2+, mutual TLS for internal service-to-service)
- [ ] Audit logging enabled for all components that access sensitive data

---

## DE — Detect

### Security Continuous Monitoring (DE.CM / AU, SI in SP 800-53)
- [ ] Security-relevant events logged: auth events, access denials, privilege escalations, configuration changes
- [ ] Log aggregation in place; logs shipped to a centralized, tamper-evident store
- [ ] Monitoring coverage includes new services and data paths introduced by this feature
- [ ] Dependency and container vulnerability scanning runs on every build
- [ ] Anomaly detection or alerting configured for unusual access or error rates

### Adverse Event Analysis (DE.AE)
- [ ] Audit logs include enough context to reconstruct events (user, resource, action, outcome, timestamp)
- [ ] Correlation of events possible (e.g. same user, multiple failures across services)

---

## RS — Respond

### Incident Management (RS.MA)
- [ ] New feature's failure modes documented in the runbook
- [ ] Incident response process covers this feature's failure scenarios
- [ ] Security incident contacts and escalation path defined

### Incident Analysis (RS.AN)
- [ ] Forensic evidence (logs, audit trails) available and retention covers at least 90 days
- [ ] Root cause analysis process defined for security incidents

---

## RC — Recover

### Recovery Planning (RC.RP)
- [ ] Backup and recovery procedure documented for new data stores
- [ ] Recovery time and point objectives (RTO/RPO) defined and met by backup strategy
- [ ] Recovery tested at least once; results documented

---

## SP 800-53 High-Baseline Controls Commonly Triggered by New Features

| Control | When triggered |
|---------|---------------|
| AC-2 Account Management | New user roles or service accounts |
| AC-3 Access Enforcement | New access control logic |
| AU-2 Audit Events | New auditable actions |
| AU-9 Audit Record Protection | New log output |
| CM-8 System Component Inventory | New service or dependency |
| IA-2 Identification and Authentication | New auth path |
| SC-8 Transmission Integrity | New network communication |
| SC-28 Protection at Rest | New data store |
| SI-2 Flaw Remediation | New dependency with known CVE |
| SI-10 Information Input Validation | New API input |

---

## CUI Handling (NIST 800-171, if applicable)

If the feature handles Controlled Unclassified Information:
- [ ] CUI identified and marked according to the CUI Registry category
- [ ] CUI stored only in authorized systems (documented in System Security Plan)
- [ ] CUI not transmitted over systems not covered by the SSP
- [ ] CUI access logged and limited to personnel with need-to-know

---

## Common Violations (flag as HIGH)

- New service or data store not added to asset inventory
- Privileged access granted beyond minimum necessary
- Sensitive data transmitted without encryption
- Audit events not captured for new security-relevant actions
- Manual production change with no change record
- New dependency with known CVE included without assessment

---

## Review Output Format

```
NIST REVIEW
Framework: [CSF 2.0 / SP 800-53 Rev 5 / SP 800-171 / other]
CUI in scope: [YES / NO]

GV Govern:        PASS / FAIL / N/A
ID Identify:      PASS / FAIL — [detail]
PR Protect:       PASS / FAIL — [detail]
DE Detect:        PASS / FAIL — [detail]
RS Respond:       PASS / FAIL / N/A
RC Recover:       PASS / FAIL / N/A
800-53 controls triggered: [list]

NIST: COMPLIANT or NON-COMPLIANT — [list of blocking findings]
```
