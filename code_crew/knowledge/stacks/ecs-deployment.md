---
name: Stack-ECSDeployment
description: AWS ECS Fargate deployment architecture, GitHub Actions CI/CD with OIDC, ECR image lifecycle, and Dev/DevOps coordination cycle
metadata:
  type: stack
  platform: aws
  services: [ecs, ecr, github-actions, terraform, secrets-manager, ssm]
  tags: [deployment, cicd, ecs, github-actions, oidc, terraform, fargate]
  detect-files:
    - "infra/**/*.tf"
    - ".github/workflows/deploy*.yml"
---

# Stack: ECS Deployment

## Architecture Overview

All platform services run as ECS Fargate services. GitHub Actions handles CI/CD with OIDC
authentication to AWS — no long-lived access keys stored in GitHub.

```
PR opened
  └── ci.yml
        ├── lint + type check
        ├── unit tests
        ├── BDD integration tests (against dev env)
        ├── security scans
        └── build image → ECR (tag: pr-<number>)

Merge to main
  └── deploy-dev.yml
        ├── build + push :latest → ECR
        └── ECS update-service (rolling deploy to dev)

Manual promote (workflow_dispatch)
  └── promote-and-release.yml
        ├── env: staging → retag :latest → :0.N-rcN, ECS deploy staging
        └── env: prod    → retag RC → :0.N, ECS deploy prod, GitHub Release
```

Production promotion is **human-triggered only**. Agents do not push images, apply
Terraform, or promote to production autonomously.

---

## GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | PR | Lint, tests, security scans, build PR image |
| `deploy-dev.yml` | Push to `main` | Build + push :latest; ECS deploy to dev |
| `promote-and-release.yml` | `workflow_dispatch` | Human-triggered staging or prod promotion |
| `terraform-plan.yml` | PR touching `infra/` | `terraform plan` as PR artifact |
| `terraform-apply.yml` | `workflow_dispatch` | Human applies a specific plan artifact |
| `vulnerability-scan.yml` | Nightly schedule | Deep dependency scan |

---

## OIDC Authentication (No Long-Lived Keys)

Terraform creates the OIDC provider and scoped IAM roles per environment:

```hcl
# infra/modules/github-oidc/main.tf
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["..."]
}

resource "aws_iam_role" "cicd" {
  name = "${var.env}-github-actions-cicd"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_assume.json
}
```

IAM roles are scoped per environment:
- `dev-github-actions-cicd` — ECR push + ECS deploy to dev
- `staging-github-actions-cicd` — ECS deploy to staging only
- `prod-github-actions-cicd` — ECS deploy to prod; `workflow_dispatch` only

In GitHub Actions:
```yaml
permissions:
  id-token: write
  contents: read

- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::${{ vars.AWS_ACCOUNT_ID }}:role/${{ vars.ENV }}-github-actions-cicd
    aws-region: ${{ vars.AWS_REGION }}
```

---

## ECR Image Tagging

| Tag | When created | Purpose |
|-----|-------------|---------|
| `pr-<number>` | CI on every PR | Test artifact; not deployed |
| `sha-<7chars>` | Every push to main | Immutable; rollback reference |
| `latest` | Every push to main | Dev auto-deploy |
| `0.N-rcN` | Staging promotion | Staging deploy |
| `0.N` | Production promotion | Prod deploy + GitHub Release |

---

## ECS Task Definition Conventions

```hcl
resource "aws_ecs_task_definition" "service" {
  family                   = "${var.env}-${var.service_name}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_exec.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name                   = var.service_name
    image                  = "${var.ecr_repo}:${var.image_tag}"
    readonlyRootFilesystem = true

    # Non-sensitive config as environment variables
    environment = [
      { name = "ENV",          value = var.env },
      { name = "SERVICE_NAME", value = var.service_name },
    ]

    # Secrets from Secrets Manager only — no plaintext secrets in task defs
    secrets = [
      { name = "DB_PASSWORD", valueFrom = aws_secretsmanager_secret.db.arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"  = "/ecs/${var.env}/${var.service_name}"
        "awslogs-region" = var.aws_region
      }
    }
  }])
}
```

---

## Adding Config for a New Feature

When a feature requires new environment variables, secrets, or permissions:

**New env var (non-sensitive)**
- Add to `environment` block in the ECS task definition module
- Terraform plan + apply for dev, then staging/prod on promotion

**New secret**
- Create in AWS Secrets Manager: `/platform/<env>/<service>/<key>`
- Add to `secrets` block in task definition
- Grant the task IAM role `secretsmanager:GetSecretValue` for the new ARN
- Terraform plan + apply

**New IAM permission for the service**
- Add statement to the service task IAM role policy in the Terraform module
- Terraform plan + apply

**New SSM parameter (non-secret config)**
- Create at `/platform/<env>/<service>/<key>`
- Ensure the task IAM role has `ssm:GetParameter` permission for that path

After any Terraform apply to dev, the engineer re-runs integration BDD tests to verify
the new config is correctly wired.

---

## Dev/DevOps Coordination Cycle

Feature delivery requires coordination between the engineer and DevOps lead. This cycle
typically runs 1–3 times per story:

```
1. Engineer implements feature code
        ↓
2. DevOps reviews implementation for new infra needs:
   - New env vars → update ECS task definition in TF
   - New secrets → create in Secrets Manager, wire in TF
   - New IAM permissions → update task IAM role policy in TF
   - New GitHub Actions steps → update workflow file
   Applies TF changes to dev environment
        ↓
3. Engineer re-runs BDD integration tests against dev
   → Tests pass → proceed to code review
   → Tests fail (infra reason) → loop back to DevOps
   → Tests fail (code reason) → fix code, loop back to step 1
```

The DevOps coordination task outputs a change summary or `NO CHANGES NEEDED` if the
feature requires no new infrastructure.

---

## Testing Strategy

| Phase | Environment | Who triggers | Gate |
|-------|-------------|-------------|------|
| Unit tests | local / CI | PR | Must pass |
| BDD integration | dev ECS | CI (post-merge) or engineer | Must pass before code review |
| Security scan | CI | PR | No Critical/High findings |
| Staging acceptance | staging ECS | QA Lead (manual) | Must pass before prod promotion |
| Production smoke | prod ECS | Automated post-deploy | Pages on failure |

The dev ECS environment is the integration test target. Tests run with
`TEST_RESET_ENABLED=true` in the dev GitHub Actions environment. Never run integration
tests against staging or production.

---

## Composite Actions

Shared pipeline logic in `.github/actions/`:
```
.github/actions/
  setup-go/     # Go toolchain + cache
  setup-node/   # Node + npm cache
  ecr-login/    # ECR authentication via OIDC
  ecs-deploy/   # Register new task definition + update service
```

Each workflow composes these rather than duplicating steps.
