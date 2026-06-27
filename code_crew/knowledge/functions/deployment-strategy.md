---
name: SDLC-Architect-DeploymentStrategy
description: Environment promotion model, blue/green deployment, binary promotion (not rebuild), and production deploy governance
metadata:
  type: process
  role: architect
  phase: "12, 20, 21"
---

# Deployment Strategy

---

## Environment Model

Three environments: `dev`, `staging`, `prod`. All environments use the same container images — **binary promotion**, never rebuild.

```
dev  ──► staging ──► prod
         (RC tag)    (release tag)
```

- `dev` — continuous deployment on every merge to `main`
- `staging` — promotion is manual; requires a release manager decision
- `prod` — promotion is **human-triggered only** via GitHub Actions `workflow_dispatch`

Agents, automation, and CI pipelines do **not** promote to production autonomously.

---

## Binary Promotion (Immutable Images)

Container images are built once in `dev` and promoted (never rebuilt) through environments.

Image tag lifecycle:
```
ghcr.io/org/service:latest   (dev — built from main)
ghcr.io/org/service:0.1-rc1  (staging pre-release)
ghcr.io/org/service:0.1      (production release)
```

Promotion workflow (GitHub Actions):
- `promote-and-release.yml` — triggered via `workflow_dispatch` with `env: staging` or `env: prod`
- For staging: retags `latest` → `0.N-rcN`, deploys to staging ECS
- For prod: retags RC → full version, creates GitHub Release, deploys to prod ECS

No Terraform plan differences between environments except image tags — infra parity is enforced.

---

## Blue/Green Deployment

Production uses blue/green deployment on ECS:

1. New task definition registered with updated image tag
2. ECS service updated to new task definition
3. ALB target group health checks run
4. Traffic cut over to new task group on health check pass
5. Old task group drained and terminated

Rollback: previous task definition is kept; rollback = redeploy previous task definition.

---

## Terraform Apply Order

Infrastructure changes are applied in a fixed order to respect dependency chains:

1. `data-seller` module
2. `core-infra` module
3. `app-infra` module

Each apply requires:
- Human review of `terraform plan` output
- Explicit `terraform apply` — no auto-apply
- Approval from architect or release manager

Agents may **generate** Terraform but **never apply** it autonomously.

---

## Health Checks & Smoke Testing

After every deployment (staging and prod):

1. ECS container health check must pass (HTTP `/health` endpoint)
2. Automated smoke test suite runs (critical paths only)
3. Alerts checked — no elevated error rates in the 10 minutes post-deploy
4. Deployment metadata (image tag, deploy timestamp, deployer) written to deployment log

---

## Rollback Procedures

**ECS service rollback:**
```bash
aws ecs update-service \
  --cluster <cluster> \
  --service <service> \
  --task-definition <previous-task-def-arn>
```

**Terraform rollback:**
- Revert Terraform config change in `main`
- Apply previous config via the standard promote workflow
- Document in change control log

**Feature flag rollback:**
- Disable flag in configuration — no deploy required

---

## ECS Configuration Parity

All environments must have the same:
- Task definition structure (CPU, memory, sidecar resources)
- `ReadOnlyRootFilesystem: true` with explicit writable path mounts
- KMS key usage for secrets at rest
- IAM task roles (environment-scoped permissions)
- Container image (different tag, same image)

Drift between environments is a blocker for production promotion.

---

## HTTPS and DNS

- Vercel manages the portal SPA (static hosting + CDN)
- Backend services run on ECS behind an ALB
- All traffic HTTPS only — HTTP redirects to HTTPS at ALB level
- Certificates managed by ACM — auto-renewed
- DNS via Route 53
