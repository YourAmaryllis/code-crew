---
name: SDLC-DevOps-EnvironmentManagement
description: Dev, staging, and prod environment configuration, parity requirements, access control, and infrastructure-as-code governance
metadata:
  type: process
  role: devops
  phase: "12, 16, 20"
---

# Environment Management

---

## Three-Environment Model

| Environment | Purpose | Deployment Trigger | Access |
|------------|---------|-------------------|--------|
| `dev` | Integration, developer testing | Auto on merge to `main` | All engineers |
| `staging` | Pre-release validation, QA acceptance | Manual `workflow_dispatch` | Engineers + QA |
| `prod` | Live customer traffic | Manual `workflow_dispatch` + human approval | Release Manager only |

All environments run the same container images — binary promotion, not rebuild.

---

## Infrastructure as Code

All infrastructure is Terraform-managed. No manual resource creation in any environment.

```
infra/
  modules/
    data-seller/    # Data seller service infrastructure
    core-infra/     # Shared: VPC, ECS cluster, RDS, KMS
    app-infra/      # Per-service: task definitions, ALB, IAM
  environments/
    dev/
    staging/
    prod/
```

Apply order (respects dependencies):
1. `data-seller`
2. `core-infra`
3. `app-infra`

---

## Environment Parity

Environments must be identical except for:
- Container image tag (`latest` vs `0.N-rc1` vs `0.N`)
- Scale (prod has more ECS tasks; dev runs minimal)
- External integrations (dev uses sandbox credentials)

Infra drift between environments is treated as a bug. Regular diff checks:
```bash
terraform plan  # run in staging and prod to verify no drift
```

---

## ECS Configuration

All ECS task definitions enforce:
- `ReadOnlyRootFilesystem: true` — write to explicitly mounted volumes only
- Writable paths listed explicitly (`/tmp`, app-specific log dirs)
- KMS-encrypted secrets via Secrets Manager integration
- Least-privilege IAM task role (no `*` actions)
- CPU and memory limits set per service (not unbounded)
- Sidecar containers (logging, monitoring) consistent across all environments

---

## Networking

- VPC with private subnets for all service containers
- ECS services not publicly accessible — ALB fronts all HTTP traffic
- ALB: HTTPS only, HTTP → HTTPS redirect
- Security groups: least-privilege (only required ports open)
- No public IP assignment on ECS tasks

---

## Secrets and Config

| Type | Storage | Access |
|------|---------|--------|
| Secrets (DB passwords, API keys) | AWS Secrets Manager | ECS task role + explicit grant |
| Config (URLs, feature flags) | SSM Parameter Store | ECS task role |
| Container image tags | ECS task definition | Updated by deploy workflow |

Config hierarchy: `/platform/<env>/<service>/<key>`

Engineers do not have direct read access to production secrets — only the ECS task role does.

---

## Access Control

| Role | Dev access | Staging access | Prod access |
|------|-----------|---------------|-------------|
| Engineer | Full (dev tools) | Read-only logs | None |
| DevOps Lead | Full | Full | Read-only (JIT for operations) |
| Release Manager | — | — | Deploy only (via workflow) |
| Security Lead | Audit read | Audit read | Audit read + JIT |
| Ops Engineer | Full | Full | JIT (8-hour limit) |

Production access is just-in-time (JIT):
1. Submit access request (ticket + justification)
2. Security Lead approves
3. Access granted for ≤ 8 hours with audit logging
4. Auto-revoked after time limit

---

## Environment Provisioning (New Environment)

1. Create Terraform workspace for the new environment
2. Copy variable set from closest existing environment
3. Apply in order: `data-seller` → `core-infra` → `app-infra`
4. Verify health checks pass
5. Configure CI/CD secrets and environment-specific GitHub Actions secrets
6. Update `promote-and-release.yml` to include new environment target

---

## Monitoring (per Environment)

All environments have CloudWatch alarms for:
- ECS task health (desired vs running count)
- ALB error rate (4xx, 5xx)
- RDS connection pool utilization
- Lambda error rate (if applicable)
- ECS CPU and memory utilization

Prod alarms page the on-call engineer via PagerDuty. Dev/staging alarms notify Slack only.
