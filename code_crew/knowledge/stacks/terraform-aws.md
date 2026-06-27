---
name: Stack-TerraformAWS
description: AWS-specific Terraform conventions — S3/DynamoDB backend, IAM, ECS, Secrets Manager, OIDC, EC2 patterns (extends terraform.md)
metadata:
  type: stack
  language: hcl
  platform: aws
  tool: terraform
  extends: terraform
  required-cli:
    - terraform
    - tfsec
    - checkov
    - aws
  detect-files:
    - "*.tf"
    - terraform/
---

# Stack: Terraform / AWS

AWS-specific conventions. Read `terraform` first for the generic module structure, design principles, and apply governance that apply here too.

## AWS Toolchain Additions

| Item | AWS-specific detail |
|------|-------------------|
| State backend | S3 bucket + DynamoDB lock table |
| Provider | `hashicorp/aws` (pin to minor version) |
| Auth | `AWS_PROFILE` or instance profile — never access keys in CI |
| Security scan | `tfsec` + `checkov` (both configured for `terraform` framework) |
| Additional CLI | `aws` (for SSO login, ECR auth, ECS describe) |

```hcl
terraform {
  backend "s3" {
    bucket         = "<project>-tf-state-<env>"
    key            = "<service>/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "<project>-tf-locks"
    encrypt        = true
  }
}
```

---

## AWS Naming Conventions

Extends the generic naming pattern with AWS-specific paths:

| Resource | Pattern |
|----------|---------|
| SSM parameters | `/platform/${var.env}/<service>/<key>` |
| Secrets Manager | `/${var.env}/${var.project}/<service>/<key>` |
| S3 buckets | `${var.env}-${var.project}-<purpose>` |
| IAM roles | `${var.env}-${var.service_name}-<role>` |
| ECR repositories | `${var.project}/<service>` |
| ECS clusters | `${var.env}-${var.project}` |
| ECS services | `${var.env}-${var.service_name}` |

---

## Access Policy and Deploy Policy Pattern (AWS)

AWS implementation of the generic pattern using `aws_iam_policy`:

```hcl
# outputs.tf — every module follows this pattern
output "access_policy" {
  description = "IAM policy ARN for other modules to access resources."
  value       = aws_iam_policy.access.arn
}

output "deploy_policy" {
  description = "IAM policy ARN for CI/CD pipelines to manage resources."
  value       = aws_iam_policy.deploy.arn
}
```

```hcl
# Project layer: wire access and deploy policies
module "app_ecs" {
  # ...
  additional_iam_policies = [module.data_bucket.access_policy]
}

resource "aws_iam_role_policy_attachment" "cicd_ecr" {
  role       = aws_iam_role.cicd.name
  policy_arn = module.app_ecr.deploy_policy
}
```

---

## ECS Module Conventions

```hcl
# All ECS task definitions enforce:
resource "aws_ecs_task_definition" "service" {
  container_definitions = jsonencode([{
    name                  = var.service_name
    image                 = "${var.ecr_repo}:${var.image_tag}"
    readonlyRootFilesystem = true
    # secrets from Secrets Manager only — no env var secrets
    secrets = [
      { name = "DB_PASSWORD", valueFrom = aws_secretsmanager_secret.db.arn }
    ]
    environment = [
      # only non-sensitive config
      { name = "LOG_LEVEL", value = "info" }
    ]
  }])
}
```

Security checklist for every ECS task definition:
- `readonlyRootFilesystem = true`
- No plaintext secrets in `environment` — use `secrets` with Secrets Manager ARNs
- No public IP on Fargate tasks (`assign_public_ip = false`)
- CloudWatch log group created by the module (not manually)
- Task role scoped to least privilege via `access_policy` outputs

---

## Secrets Manager Config Pattern

Application configuration and secrets are stored in AWS Secrets Manager, never as plain environment variables.

Secret naming: `/${var.env}/${var.project}/<service>/<key>`

```hcl
# ECS task definition — reference secrets by ARN, never inline values
container_definitions = jsonencode([{
  secrets = [
    { name = "DB_PASSWORD",  valueFrom = "${aws_secretsmanager_secret.db.arn}:password::" },
    { name = "API_KEY",      valueFrom = "${aws_secretsmanager_secret.api.arn}:key::" },
  ]
  environment = [
    { name = "LOG_LEVEL", value = "info" }  # non-sensitive only
  ]
}])
```

The `deploy_policy` for each secret must be attached to the CI/CD role so pipelines can rotate secrets without manual steps.

---

## OIDC Authentication (GitHub Actions / GitLab CI → AWS)

No long-lived access keys for CI — OIDC only.

### GitHub Actions

```hcl
# modules/github-oidc/main.tf
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["<thumbprint>"]
}

resource "aws_iam_role" "github_actions_deploy" {
  name = "${var.env}-github-actions-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_oidc.json
}

data "aws_iam_policy_document" "github_oidc" {
  statement {
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    actions = ["sts:AssumeRoleWithWebIdentity"]
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_org}/${var.github_repo}:*"]
    }
  }
}
```

### GitLab CI

```hcl
resource "aws_iam_openid_connect_provider" "gitlab" {
  url             = "https://gitlab.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["<thumbprint>"]
}

data "aws_iam_policy_document" "gitlab_oidc" {
  statement {
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.gitlab.arn]
    }
    actions = ["sts:AssumeRoleWithWebIdentity"]
    condition {
      test     = "StringLike"
      variable = "gitlab.com:sub"
      values   = ["project_path:${var.gitlab_project_path}:ref_type:branch:ref:*"]
    }
  }
}
```

---

## Unified Instance Configuration (EC2)

When a project runs multiple EC2 instance types (compute nodes, jump hosts, data managers, login nodes), use **one configuration script** that detects its context and adapts — rather than separate scripts per instance type.

Detection sources:
- EC2 instance tags (`service-type`, `stack-name`)
- Instance metadata (instance type prefix for GPU detection)
- A config secret in Secrets Manager

```
┌─────────────────────────────────────────────────┐
│              setup-instance.sh                  │
│  1. Read EC2 tags + instance metadata           │
│  2. Fetch config from Secrets Manager           │
│  3. Install packages                            │
│  4. Mount filesystems based on instance type    │
│  5. Configure instance-specific features        │
└─────────────────────────────────────────────────┘
         │                │               │
   ┌─────┴─────┐   ┌──────┴─────┐  ┌─────┴──────┐
   │ Compute   │   │  Jump host  │  │  Manager   │
   │ (skip FS) │   │ (mount all) │  │ (data only)│
   └───────────┘   └─────────────┘  └────────────┘
```

**Why**: one tested script vs. N diverging scripts. A bug fix or new mount is applied once.

Terraform provisions the script via `user_data` or SSM Run Command, referencing the same S3 object path for all instance types.

---

## Automated User Requests Pattern

Enable users to perform privileged operations (package installs, instance creation, config changes) without granting direct IAM permissions. Use Secrets Manager as the request queue and Lambda as the executor.

### Architecture

```
User (CLI script)
  │
  │  1. Validate input locally
  │  2. Write pending request to Secrets Manager
  ▼
AWS Secrets Manager  ──── CloudWatch Event ──── Lambda
                                                  │
                                                  │  3. Execute with elevated permissions
                                                  │  4. Update secret with result
                                                  │  5. Notify (SNS → Slack/email)
```

### Secret structure

```json
{
  "pending_requests": [
    {
      "id": "uuid",
      "action": "install-package | create-instance | ...",
      "requested_by": "username",
      "requested_at": "2026-06-24T10:00:00Z",
      "source_ip": "10.0.1.50",
      "status": "pending"
    }
  ],
  "request_history": [],
  "settings": {
    "rate_limit_per_user_per_day": 10,
    "use_allowlist": false
  }
}
```

### Terraform resources

```hcl
resource "aws_secretsmanager_secret" "requests" {
  name = "/${var.env}/${var.project}/<operation>-requests"
}

resource "aws_lambda_function" "request_handler" { ... }

resource "aws_cloudwatch_event_rule" "secret_change" {
  event_pattern = jsonencode({
    source      = ["aws.secretsmanager"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail.requestParameters.secretId = [aws_secretsmanager_secret.requests.arn]
  })
}

resource "aws_cloudwatch_event_target" "trigger_lambda" {
  rule = aws_cloudwatch_event_rule.secret_change.name
  arn  = aws_lambda_function.request_handler.arn
}
```

### Benefits

| Benefit | Description |
|---------|-------------|
| Least privilege | Users only need `secretsmanager:GetSecretValue` + `PutSecretValue` |
| Audit trail | Every request logged with user, timestamp, source IP |
| Rate limiting | Configurable per-user limits prevent abuse |
| Input validation | CLI validates before the secret write — bad input never reaches Lambda |
| Consistent execution | Lambda runs the same code path every time |

Good fit when: multiple users share infrastructure, self-service is needed, operations require permissions unsafe to grant broadly.

---

## Infrastructure Layering (AWS)

```
┌──────────────────────────────────┐
│  Project layer (infra/envs/*)    │  ← project-specific config only
├──────────────────────────────────┤
│  Opinionated modules             │  ← e.g. ecs-service-opinionated
├──────────────────────────────────┤
│  Base modules (infra/modules/*)  │  ← reusable: ecs, rds, s3, ecr, alb
├──────────────────────────────────┤
│  AWS resources (hashicorp/aws)   │  ← raw provider resources
└──────────────────────────────────┘
```

Project-level code (`infra/environments/*/`) must **never** declare `resource "aws_*"` blocks directly.

Acceptable exceptions at the project layer:
- `aws_iam_role_policy_attachment` — connecting module `access_policy`/`deploy_policy` outputs
- `data "aws_*"` — referencing pre-existing resources
- `output` blocks

---

## AWS Security Scanning

Common `tfsec`/`checkov` findings specific to AWS to fix before merge:
- Open security groups (allow all inbound `0.0.0.0/0`)
- Unencrypted S3 buckets (missing `server_side_encryption_configuration`)
- Missing ECS `ReadOnlyRootFilesystem`
- Missing KMS encryption for Secrets Manager secrets
- Public IP assignment on ECS Fargate tasks
- RDS instances without deletion protection in prod
- Missing VPC flow logs
