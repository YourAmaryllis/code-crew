---
name: Function-AuditingEvidence
description: How to collect, organise, and maintain audit evidence from the dev process — what artefacts exist, where they live, and how long to retain them
metadata:
  type: function
  roles: [compliance-officer, security-lead, devops-lead, architect]
  phase: "ongoing"
---

# Auditing Evidence

This document describes the auditing artefacts produced by the development and deployment process, where they are stored, and how to retrieve them for compliance audits or incident investigations.

---

## Evidence Taxonomy

Artefacts are categorised by the type of audit they support:

| Category | Artefact | What it proves |
|----------|---------|---------------|
| **Identity & Access** | CloudTrail API calls | Who did what, when, from where |
| **Identity & Access** | IAM access review records | Who had access at a given point in time |
| **Identity & Access** | JIT access request log | Who was granted temporary production access |
| **Code Changes** | GitHub PR history | Who proposed, reviewed, and approved each change |
| **Code Changes** | GPG-signed commit log | Commit attributed to a verified identity |
| **Code Changes** | Branch protection logs | No direct pushes to main; all changes reviewed |
| **Testing** | BDD runner output | Acceptance criteria verified by automated test |
| **Testing** | CI test run URLs | Test results at point of merge |
| **Security** | Vulnerability scan reports | Known CVEs scanned and addressed |
| **Security** | SBOM files | Dependency inventory at release time |
| **Security** | Secret scan results | No secrets committed to code |
| **Infrastructure** | Terraform plan logs | Infrastructure change reviewed before apply |
| **Infrastructure** | Terraform state | Point-in-time infrastructure configuration |
| **Deployments** | ECS task definition revisions | What was deployed, when, and by whom |
| **Deployments** | Deployment metadata records | Version, timestamp, deployer identity, run ID |
| **Deployments** | GitHub Release notes | What changed in each production release |

---

## Artefact Storage

| Artefact | Storage Location | Retention |
|---------|-----------------|-----------|
| CloudTrail logs | S3 (CloudTrail bucket) | 7 years (encrypted) |
| IAM access reviews | `designs/PLAN/access-reviews/` | 3 years |
| JIT access request log | `designs/PLAN/access-log.md` or ticketing system | 3 years |
| PR history | GitHub (permanent) | Permanent |
| Commit log | GitHub (permanent) | Permanent |
| CI test run artefacts | GitHub Actions artefacts | 90 days (download and archive before expiry for audits) |
| Vulnerability scan reports | GitHub Actions artefacts + S3 archive | 1 year |
| SBOM files | S3 (release bucket) per release tag | Per release, 3 years |
| Terraform plan logs | GitHub Actions artefacts | 90 days |
| Terraform state | S3 (state bucket) | Versioned, permanent |
| ECS task definition history | AWS (permanent, via API) | Permanent |
| Deployment metadata | SSM Parameter Store + S3 deploy log | 3 years |
| GitHub Releases | GitHub | Permanent |

---

## Evidence Retrieval

### For a specific code change
```bash
# PR history: GitHub UI or API
gh pr list --state merged --search "PROJ-NNN"

# Commit: verified signature
git log --show-signature --oneline <commit-sha>

# CI test run
gh run list --workflow ci.yml --branch feature/PROJ-NNN-slug
```

### For a production deployment
```bash
# Deployment metadata from SSM
aws ssm get-parameter --name /platform/prod/last-deploy --with-decryption

# ECS task definition history
aws ecs describe-task-definition --task-definition <service>:<revision>

# GitHub Release
gh release view v0.N
```

### For access to production
```bash
# CloudTrail — who accessed prod in a time range
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventSource,AttributeValue=ecs.amazonaws.com \
  --start-time <ISO8601> --end-time <ISO8601>
```

### For vulnerability evidence
```bash
# Latest SBOM from S3
aws s3 cp s3://<release-bucket>/sbom-v0.N.json .

# CI scan report (if within 90-day window)
gh run download <run-id> --name vulnerability-scan-report
```

---

## Pre-Audit Checklist

Before an audit, the Compliance Officer verifies:

- [ ] CloudTrail is enabled in all regions and logs are flowing to S3
- [ ] CI artefacts from the audit period are downloaded and archived (before 90-day expiry)
- [ ] SBOM files are present in S3 for all production releases in scope
- [ ] IAM access review records cover the audit period
- [ ] JIT access request log is complete and matches CloudTrail entries
- [ ] Deployment metadata records exist for all production deployments in scope
- [ ] GitHub PRs for all changes in scope are visible and show review/approval

---

## Incident Investigation

For a security incident or anomaly:

1. **Identify time window** — when did the anomaly occur?
2. **CloudTrail query** — which API calls were made in that window from which principals?
3. **Cross-reference access log** — was any JIT access granted around that time?
4. **Code change history** — were any deployments made in that window? What changed?
5. **Vulnerability scan** — were any known CVEs present in the deployed version?
6. **Test evidence** — did all BDD scenarios pass for the deployed version?

Document findings in an incident record linked to the relevant Jira ticket.

---

## Evidence for Code-Crew Runs

When the code-crew generates implementation and test artefacts:

- Crew output is saved to `~/code-crew/outputs/<sprint>/<PROJ-NNN>.md`
- This is an AI-generated evidence draft, not authoritative — human review and actual CI run are the authoritative artefacts
- The BDD runner output in the Jira comment is the DoD evidence, not the crew output

See: `compliance-evidence` for the compliance framework mapping.
