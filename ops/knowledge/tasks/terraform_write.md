---
type: CrewAI Task
title: Terraform Write
description: Author or update Terraform modules per ADD-018; produce plan output for human review
tags: [terraform, iac, plan, aws, phase-12, add-018]
timestamp: 2026-06-17T00:00:00Z
agent: terraform_engineer
context_agents:
  - ops_lead
expected_output: >
  Terraform resource blocks (HCL) for the required infrastructure changes, organized
  per ADD-018 module structure. A `terraform plan` summary showing what would be created,
  modified, or destroyed. A human-review gate note — apply must not proceed without
  explicit approval.
---

Write or update Terraform code for the infrastructure changes identified in the environment plan.

**Before writing**, use the `sop_reader` tool to load ADD-018 to confirm the correct
module structure, state key format, and environment layout.

**Module placement** (ADD-018):
- Shared/foundational resources → `ops/core/terraform/` (VPC, IAM roles, KMS keys, ECR)
- Application resources → `ops/<service>/terraform/` (ECS services, ALBs, RDS, S3)
- Follow the existing directory structure; do not create parallel patterns

**For each new resource block:**
1. Use the correct Terraform AWS provider resource type
2. Apply standard tags: `Environment`, `Project`, `ManagedBy = "terraform"`, `Jira = "<key>"`
3. Reference existing variables from the module's `variables.tf` — do not hardcode IDs or ARNs
4. Output any values that other modules will need in `outputs.tf`
5. Add a `description` attribute to every `variable` and `output` block

**IAM policies:**
- List exact `Action` permissions needed — no wildcards without justification
- Scope `Resource` to the specific resource ARN where possible
- Add an inline comment explaining why each permission is required

**Secrets:**
- Passwords, tokens, and API keys via `data.aws_secretsmanager_secret_version` references
- Never output sensitive values: `sensitive = true` on all secret outputs

**Produce:**
1. HCL resource blocks (full, ready to review)
2. A plain-English `terraform plan` summary: what will be created/modified/destroyed and why
3. A clear marker: **⚠️ HUMAN REVIEW REQUIRED BEFORE APPLY ⚠️**
