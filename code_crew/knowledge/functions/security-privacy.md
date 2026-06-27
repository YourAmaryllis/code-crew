---
name: SDLC-Architect-SecurityPrivacy
description: Threat modeling, security controls, vulnerability scanning, OWASP compliance, platform constraint checks, and security review process
metadata:
  type: process
  role: architect
  phase: "6, 9, 19"
---

# Security & Privacy

Security analysis is integrated at Phase 6 (architecture stage) and enforced at Phase 19 (code review). The architect owns security design; the security lead owns ongoing vulnerability management.

---

## Threat Modeling (Phase 6)

For each significant feature or service, create a threat model:

1. Identify assets (data, credentials, infrastructure)
2. Enumerate threat scenarios using MITRE ATT&CK framework
3. Assess severity (Critical/High/Medium/Low) and likelihood
4. Define security controls to mitigate each threat
5. Document as `THREAT-YYYY-NNN` entries

Threat scenario format:
```markdown
THREAT-YYYY-NNN: <short title>
Asset: <what is at risk>
Vector: <how attacker reaches it>
MITRE: <ATT&CK technique>
Severity: Critical | High | Medium | Low
Likelihood: High | Medium | Low
Control: <mitigation>
```

---

## Security Controls

Security controls are documented as `SEC-YYYY-NNN` entries, categorized:

| Category | Examples |
|----------|---------|
| Authentication | IAM, MFA, session tokens |
| Authorization | RBAC, resource-level permissions, scope enforcement |
| Encryption | TLS in transit, KMS at rest, field-level encryption for PII |
| Logging | Audit log for access, mutations, admin actions |
| Monitoring | CloudWatch alarms, GuardDuty, anomaly detection |
| Input Validation | Schema validation, parameterized queries, output encoding |

Every SEC control has a verification criterion — how to confirm it is implemented.

---

## OWASP Top 10 Checklist (per PR)

Code review includes a security check against OWASP Top 10. Reject PRs that introduce:

| Risk | Check |
|------|-------|
| A01 Broken Access Control | Auth checks on all new endpoints; no IDOR |
| A02 Cryptographic Failures | No plaintext secrets; PII encrypted at rest |
| A03 Injection | Parameterized queries; no string concatenation into SQL/shell |
| A04 Insecure Design | Architecture review for new attack surface |
| A05 Security Misconfiguration | No default credentials; no open S3 buckets |
| A06 Vulnerable Components | No known-CVE dependencies (SBOM scan) |
| A07 Auth & Session Mgmt | Short-lived tokens; secure cookie flags |
| A08 Integrity Failures | Signed commits; image digest verification |
| A09 Logging Failures | No PII in logs; audit trail for sensitive ops |
| A10 SSRF | Allowlist for outbound HTTP; no user-controlled URLs |

---

## Vulnerability Scanning (Ongoing)

Three scan types run in CI:

| Scan | Tool | Trigger |
|------|------|---------|
| Dependency scan (Go) | `govulncheck` | Every PR + nightly |
| Dependency scan (Node/Python) | `npm audit`, `pip-audit` | Every PR + nightly |
| Infrastructure scan | `tfsec` / `checkov` | Every Terraform PR |
| Container scan | Trivy | Every image build |
| Cloud posture | AWS Security Hub | Continuous |

Vulnerability reports are documented as `VS-YYYY-NNN`. Critical and High vulnerabilities must be remediated before the next sprint starts.

---

## SOC 2 Type II Alignment

Security controls map to SOC 2 Trust Service Criteria:

| Control | TSC |
|---------|-----|
| Logical access control (IAM + MFA) | CC6.1 |
| Attributable identity (signed commits, audit logs) | CC6.2 |
| System operations monitoring | CC7.1 |
| Anomaly detection and alerting | CC7.2 |
| Change management (PRs, Terraform plan review) | CC6.2 |
| Backup and recovery | CC9.1 |

Evidence is collected and maintained by the compliance officer for annual SOC 2 audits.

---

## Access Control

**Production access — least privilege:**
- No standing access to production
- Just-in-time elevation via access request workflow
- All production access logged and time-limited (max 8 hours)
- Access revoked immediately on role change or departure

**Developer access — per SOP-14:**
- Multi-factor authentication required
- Signed commit enforcement
- Secrets via AWS Secrets Manager / SSM only (no `.env` files with real secrets)
- Pre-commit hooks: secret scanning, lint, type check

See: [development-workflow.md`](development-workflow.md)

---

## Privacy Requirements

- PII fields identified and documented in the domain model
- PII encrypted at field level where column-level encryption is insufficient
- PII not logged — log sanitization checked in code review
- Data retention periods defined per CRD; automated deletion enforced
- GDPR: right-to-erasure implemented for all PII stores
- Customer data separated by tenant — no cross-tenant data access possible
