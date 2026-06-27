---
name: Compliance-HIPAA
description: HIPAA Security Rule controls checklist — PHI handling, encryption, access control, audit logging, and breach notification requirements for code and infrastructure review
metadata:
  type: compliance
  framework: HIPAA
  rule: Security Rule (45 CFR Part 164)
  activate: explicitly — set in CODE_CREW_STACKS or stacks: in .code-crew/config.yaml
---

# Compliance: HIPAA Security Rule

HIPAA applies to any system that creates, receives, maintains, or transmits **Protected Health Information (PHI)**. PHI is any individually identifiable health information: diagnosis, treatment, payment records, device identifiers, dates of service, or any 18 HIPAA identifiers combined with health data.

Add `hipaa` to `stacks:` in `.code-crew/config.yaml` for any project that handles PHI.

---

## What to Load First

Before performing a HIPAA compliance check, load with `knowledge_reader`:
- The relevant ADD for the feature (PHI data flows, storage components)
- `security-privacy` function guide
- Any ADR covering data classification or zero-custody decisions

---

## PHI Identification

Identify all PHI in scope for this story:
- What health data does the feature create, read, update, or delete?
- Which 18 HIPAA identifiers are present? (names, dates except year, phone, address, SSN, medical record numbers, account numbers, device identifiers, biometric identifiers, full-face photos, geographic subdivisions smaller than state)
- Is this feature acting as a **covered entity** function or a **business associate** function?

State: **PHI IN SCOPE** (list fields) or **NO PHI IN SCOPE** (explain why).

---

## Checklist

### Access Controls (§164.312(a)(1))
- [ ] PHI endpoints require authentication — no anonymous access to any PHI field
- [ ] Authorization is role-based and checked server-side on every request
- [ ] Minimum necessary rule: API responses include only the PHI fields required for the use case — no full record dumps unless explicitly needed
- [ ] No PHI accessible via URL parameters (IDs only — the ID is not itself PHI, but the response must be access-controlled)
- [ ] Session management follows secure patterns (short expiry, rotation on privilege change)

### Audit Controls (§164.312(b))
- [ ] Every PHI read, write, update, and delete is logged with: user ID, timestamp, resource identifier, action, outcome
- [ ] Audit logs are append-only (no application-level delete or update path)
- [ ] Audit log entries do not themselves contain PHI (log the record ID and action, not the record contents)
- [ ] Logs are shipped to a tamper-evident store (not just application logs that rotate)

### Integrity (§164.312(c)(1))
- [ ] PHI is not alterable in transit without detection (HTTPS only; no HTTP fallback)
- [ ] Database writes include optimistic locking or equivalent where concurrent modification is possible
- [ ] No PHI stored in browser localStorage, sessionStorage, or URL fragments

### Transmission Security (§164.312(e)(1))
- [ ] All PHI transmission uses TLS 1.2+ — no plaintext paths
- [ ] No PHI in HTTP headers, query strings, or log lines (even in dev mode)
- [ ] Internal service-to-service calls carrying PHI also use mutual TLS or equivalent

### Encryption at Rest (§164.312(a)(2)(iv))
- [ ] PHI fields encrypted at rest (column-level encryption or encrypted storage layer)
- [ ] Encryption keys are NOT stored alongside the encrypted data
- [ ] Backup copies of PHI are also encrypted

### Person Authentication (§164.312(d))
- [ ] MFA enforced for any user with PHI access
- [ ] Password/credential requirements meet or exceed NIST 800-63B guidance

### Automatic Logoff
- [ ] UI sessions expire after inactivity (≤ 15 minutes for PHI-facing screens)
- [ ] Backend tokens have short expiry and are not refreshable indefinitely

### Business Associate Requirements
- [ ] If this feature shares PHI with a third-party service, confirm a BAA is in place (flag as blocker if not)
- [ ] No PHI sent to analytics, error tracking, or observability tools without explicit data scrubbing

### Breach Notification Readiness
- [ ] PHI data flows are documented (which service holds what, where it's transmitted)
- [ ] There is a mechanism to enumerate "which records did user X access between T1 and T2" (required for breach notification)

---

## Common Violations (flag as CRITICAL)

- PHI field values in application logs or error messages
- PHI returned in API responses beyond what the use case requires (over-fetching)
- PHI stored unencrypted in any cache, queue, or temp store
- PHI in error responses sent to the browser
- Missing audit log on a PHI write path
- PHI shared with a third-party service without BAA documentation
- HTTP (non-TLS) path to a PHI endpoint

---

## Review Output Format

```
HIPAA REVIEW
PHI in scope: [list fields / NO PHI IN SCOPE]

Access Controls:    PASS / FAIL — [detail]
Audit Controls:     PASS / FAIL — [detail]
Transmission:       PASS / FAIL — [detail]
Encryption at rest: PASS / FAIL — [detail]
Minimum necessary:  PASS / FAIL — [detail]
BAA check:          PASS / N/A / FLAG — [detail]

HIPAA: COMPLIANT or NON-COMPLIANT — [list of blocking findings]
```
