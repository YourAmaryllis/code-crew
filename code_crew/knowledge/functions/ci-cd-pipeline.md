---
name: SDLC-DevOps-CICDPipeline
description: CI/CD pipeline structure, GitHub Actions workflows, OIDC authentication, and pipeline governance
metadata:
  type: process
  role: devops
  phase: "12, 16, 20, 21"
---

# CI/CD Pipeline

---

## Pipeline Overview

```
PR opened
  └── ci.yml
        ├── lint + type check
        ├── unit tests
        ├── integration BDD tests
        ├── security scans (govulncheck, npm audit, tfsec)
        └── container build + push (PR tag)

Merge to main
  └── deploy-dev.yml
        ├── Build container image → ECR (tag: latest)
        └── Deploy to dev ECS

Manual: promote-and-release.yml (workflow_dispatch)
  ├── env: staging
  │     ├── Retag latest → 0.N-rcN
  │     └── Deploy to staging ECS
  └── env: prod
        ├── Retag RC → 0.N
        ├── Update ECS task definition
        ├── Deploy to prod ECS
        └── Create GitHub Release
```

---

## GitHub Actions Workflows

| File | Trigger | Purpose |
|------|---------|---------|
| `ci.yml` | PR | Lint, test, build, security scan |
| `deploy-dev.yml` | Push to `main` | Deploy to dev |
| `promote-and-release.yml` | `workflow_dispatch` | Promote to staging or prod |
| `terraform-plan.yml` | PR with `infra/` changes | Run `terraform plan` |
| `vulnerability-scan.yml` | Nightly schedule | Deep dependency scan |

---

## OIDC Authentication (No Long-Lived Keys)

GitHub Actions authenticates to AWS via OIDC — no stored access keys.

```yaml
permissions:
  id-token: write
  contents: read

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::ACCOUNT:role/github-actions-deploy
      aws-region: us-east-1
```

IAM roles are scoped per environment:
- `github-actions-ci` — ECR push, read-only resource access
- `github-actions-deploy-staging` — ECS deploy to staging only
- `github-actions-deploy-prod` — ECS deploy to prod (requires `workflow_dispatch`)

---

## Container Build and Push

```yaml
- name: Build and push
  run: |
    docker build -t $ECR_REGISTRY/$SERVICE:$TAG .
    docker push $ECR_REGISTRY/$SERVICE:$TAG
```

Tags:
- `latest` — built from every `main` merge (deployed to dev)
- `sha-XXXXXXX` — short commit SHA (immutable, used for rollback reference)
- `0.N-rcN` — staging pre-release
- `0.N` — production release

---

## Composite Actions

Shared pipeline logic lives in `.github/actions/`:
```
.github/actions/
  setup-go/        # Go toolchain + cache
  setup-node/      # Node + npm cache
  ecr-login/       # ECR authentication
  ecs-deploy/      # ECS task definition + service update
```

Each workflow composes these actions rather than duplicating steps.

---

## Terraform Pipeline

```yaml
# terraform-plan.yml — runs on PRs touching infra/
- terraform init
- terraform validate
- terraform plan -out=tfplan
- upload tfplan as artifact
```

Apply is **never automated** — a human runs `terraform apply` via the `terraform-apply.yml` `workflow_dispatch` workflow, which requires the uploaded plan artifact.

---

## SBOM and License Validation

CI generates a Software Bill of Materials (SBOM) on every build:
```bash
syft packages . -o spdx-json > sbom.json
```

License validator runs against the SBOM to flag non-approved licenses:
- Approved: MIT, Apache 2.0, BSD variants
- Review required: LGPL, MPL
- Rejected: GPL, AGPL, SSPL

---

## Environment-Specific Config

Config differences between environments are managed via:
- ECS task definition environment variables
- AWS SSM Parameter Store (one hierarchy per environment: `/platform/<env>/...`)
- No environment-specific code branches

---

## Pipeline Governance

- Pipeline definitions live in `main` — no environment-specific pipeline branches
- Pipeline changes go through PR + code review
- Secrets in GitHub Actions: stored as repository/environment secrets; no plaintext values
- Pipeline failures notify the DevOps Lead via Slack
