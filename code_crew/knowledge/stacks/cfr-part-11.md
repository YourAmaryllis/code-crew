---
name: Compliance-CFR-Part-11
description: FDA 21 CFR Part 11 checklist — electronic records, electronic signatures, audit trails, and system validation for regulated life science systems
metadata:
  type: compliance
  framework: "21 CFR Part 11"
  issuer: FDA
  activate: explicitly — set in CODE_CREW_STACKS or stacks: in .code-crew/config.yaml
---

# Compliance: FDA 21 CFR Part 11

21 CFR Part 11 applies to any electronic records and electronic signatures used in place of paper records required by FDA regulations. Scope includes: clinical trial data, laboratory records, manufacturing batch records, QC/QA records, deviation reports, change control records, validation documentation.

Add `cfr-part-11` to `stacks:` for any system that creates or manages FDA-regulated electronic records.

---

## Scope Assessment

Before reviewing, determine:
- Does this feature create, modify, maintain, archive, retrieve, or transmit FDA-required records?
- Are electronic signatures applied to any records (approval, review, authorization)?
- Does this feature modify any previously validated system component?

State: **PART 11 IN SCOPE** (list record types) or **NOT IN SCOPE** (explain basis).

---

## §11.10 — Electronic Records: System Controls

### Access Controls
- [ ] System access limited to authorized individuals; unique user IDs enforced (no shared accounts)
- [ ] User IDs linked to a named individual; account sharing blocked at application level
- [ ] Inactive sessions automatically terminate after a defined timeout (typically ≤15 min)
- [ ] Account lockout after a defined number of failed login attempts
- [ ] Access privileges granted by role and reviewed periodically; least-privilege enforced

### Audit Trail (§11.10(e))
- [ ] Audit trail captures: record creation, modification, and deletion with operator ID, date/time, and description of change
- [ ] Previous values are preserved — audit trail shows what changed, not just that a change occurred
- [ ] Audit trail is computer-generated (not manually entered) and tamper-evident
- [ ] Audit trail cannot be disabled by any operator; only administrator can view (not edit) it
- [ ] Audit trail retained as long as the records themselves; available for FDA inspection
- [ ] Date/time stamps use a controlled, synchronized clock (NTP); timezone documented

### Record Integrity
- [ ] Electronic records protected against unauthorized alteration (database-level or application-level constraint)
- [ ] Original records and all subsequent changes preserved; no overwrite without audit record
- [ ] Deleted records are logically deleted and retained in audit trail (true deletion blocked)
- [ ] Records include sufficient metadata: record type, system ID, creation/modification dates, operator

### Operational Checks (§11.10(f))
- [ ] Sequence checks enforce correct order of events where required by SOP
- [ ] Authority checks verify operator has permission for the action before executing
- [ ] Input checks validate data against specification before acceptance

### Archiving and Retrieval
- [ ] Records retrievable in human-readable form for the duration of their retention period
- [ ] Archived records include software version or export format needed to read them
- [ ] Archival medium is validated; retrieval tested periodically

---

## §11.50 / §11.70 — Electronic Signatures

- [ ] Electronic signatures are unique to one individual; cannot be reused or reassigned
- [ ] Signature requires at minimum: two distinct identification components (e.g. user ID + password/token)
- [ ] Re-authentication required for a signature applied in a session that has been idle
- [ ] Signature manifestation includes: printed name, date/time, and meaning of signature (review, approval, author)
- [ ] Signature linked to the record in a way that cannot be excised, copied, or otherwise transferred
- [ ] Attempted signature falsification detected and logged
- [ ] If biometric signatures used: unique to individual; cannot be used by anyone else

---

## §11.30 — Open Systems

If records are transmitted over open networks (internet):
- [ ] Encryption used for transmission to prevent unauthorized access
- [ ] Digital signatures or equivalent used to ensure authenticity and detect tampering

---

## Validation (§11.10(a))

- [ ] System validation documentation (IQ/OQ/PQ or equivalent) exists for all system components used for regulated records
- [ ] This change has been assessed for validation impact:
  - Minor config change: update validation documents
  - New feature or significant change: revalidation required before use for regulated records
- [ ] Change control record exists for this modification
- [ ] Validation plan and validation summary report are under version control

---

## Common Violations (flag as CRITICAL)

- Audit trail can be disabled or edited by an operator
- Shared user accounts (no unique ID per user)
- Audit trail does not record previous values before modification
- Electronic signature not linked cryptographically to the record
- Signature applied without re-authentication after session idle
- System modification deployed to regulated environment without validation assessment
- Date/time stamps from an unsynchronized or operator-adjustable clock

---

## Review Output Format

```
21 CFR PART 11 REVIEW
Record types in scope: [list / NOT IN SCOPE]
Electronic signatures in scope: [YES / NO]
Validation impact: [NONE / DOCUMENT UPDATE / REVALIDATION REQUIRED]

Access Controls:     PASS / FAIL — [detail]
Audit Trail:         PASS / FAIL — [detail]
Record Integrity:    PASS / FAIL — [detail]
E-Signatures:        PASS / FAIL / N/A
Validation Status:   PASS / FAIL / N/A — [detail]

CFR PART 11: COMPLIANT or NON-COMPLIANT — [list of blocking findings]
```
