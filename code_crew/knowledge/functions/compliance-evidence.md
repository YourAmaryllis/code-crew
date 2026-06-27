---
name: SDLC-Compliance-Evidence
description: Compliance controls embedded in the dev process — SOC 2 Trust Service Criteria, security scanning, audit trails, evidence collection from CI
metadata:
  type: function
  roles: [compliance-officer, security-lead, devops-lead]
  phase: "ongoing"
---

# Compliance Evidence

Regulatory compliance (SOC 2, GDPR, HIPAA, PCI-DSS, etc.) is specific to each project. This document covers the controls and evidence the dev process provides — not the regulatory requirements themselves.

For requirements specific to your project, maintain a Compliance Requirements Document (CRD) in `designs/CRD/` and reference it from relevant Jira tickets.

---

## SOC 2 Trust Service Criteria

The dev process satisfies the following SOC 2 Trust Service Criteria through built-in controls:

| Criteria | Control | Evidence Source |
|----------|---------|----------------|
| **CC6.1** Logical access control | IAM with MFA; JIT production access (≤ 8 hr); access request workflow | CloudTrail, IAM access logs, access request records |
| **CC6.2** Attributable identity | GPG-signed commits; named PR approvals; CloudTrail API attribution | GitHub commit log (Verified badge), CloudTrail |
| **CC7.1** System operations | IaC-managed infrastructure; no manual resource creation; change management via PRs | Terraform state, PR history, pipeline run logs |
| **CC7.2** System monitoring | CloudWatch alarms; GuardDuty; anomaly detection alerts | CloudWatch alarm history, GuardDuty findings |
| **CC9.1** Risk management | Vulnerability scans per PR; SBOM per release; dependency audits | CI scan artefacts, SBOM files, vuln reports |
| **A1.2** System availability | Health checks; blue/green deployment; rollback procedures | ECS health logs, deployment records |

---

## What the Dev Process Provides as Compliance Evidence

| Evidence | Source | Cadence |
|---------|--------|---------|
| Access control audit trail | CloudTrail + IAM access logs | Continuous |
| Code change history | GitHub PR history (who changed what, reviewed by whom) | Per PR |
| Signed commits (attributable identity) | GPG-signed commit log | Per commit |
| Vulnerability scans | CI scan artefacts (`govulncheck`, `npm audit`, `pip-audit`, Trivy, `tfsec`) | Per PR + nightly |
| Software Bill of Materials (SBOM) | CI build artefacts | Per release |
| Test evidence | BDD runner output, GitHub Actions run URLs | Per story |
| Infrastructure change history | Terraform plan/apply logs | Per infra change |
| Deployment records | Task definition history, deploy metadata, release notes | Per release |
| Access request records | JIT access request log, approval audit | Per production access event |

---

## Security Scanning in CI (CC9.1 evidence)

Every PR runs:
- Dependency vulnerability scan (language-specific: `govulncheck`, `npm audit`, `pip-audit`)
- Container image scan (`Trivy`) on every build
- Infrastructure scan (`tfsec` / `checkov`) on Terraform PRs
- Secret detection (pre-commit hook + CI)

Critical/High findings block the PR. Scan reports are stored as CI artefacts.

See: `ci-cd-pipeline`, `security-privacy`

---

## Traceability Chain (CC6.2 / change management evidence)

The dev process maintains an unbroken traceability chain from requirement to deployed code:

```
Requirement ID (BR/TR/CR)
  → Jira ticket (PROJ-NNN)
    → branch name (feature/PROJ-NNN-slug)
      → signed commit ([REQ:TR-YYYY-NNN] PROJ-NNN)
        → BDD test (@PROJ-NNN tag)
          → CI test report
            → PR (reviewed + approved)
              → deployed release
```

This chain satisfies change management evidence requirements for most compliance frameworks.

---

## Access Governance (CC6.1 evidence)

- No standing production access — all access JIT with 8-hour limit
- All access requests logged: who requested, who approved, time granted, time revoked
- Quarterly access reviews: all active permissions audited and recertified
- Leaver process: access revoked within 24 hours of departure notification

---

## Evidence Collection Cadence

| Frequency | Activity |
|-----------|---------|
| Per PR | Vulnerability scan report, test evidence, commit signature |
| Per release | SBOM, deployment record, release notes |
| Monthly | IAM access review, CloudTrail anomaly summary |
| Quarterly | Full compliance evidence package, access recertification |
| Annual | SOC 2 audit preparation (for projects under SOC 2) |

For detailed audit evidence organisation, see `auditing-evidence`.
