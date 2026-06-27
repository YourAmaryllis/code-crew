---
type: CrewAI Task
title: DevOps Coordination
description: DevOps Lead identifies and applies infrastructure changes required for the feature to run in dev
tags: [devops, terraform, ecs, secrets, iam, github-actions, phase-16]
timestamp: 2026-06-20T00:00:00Z
agent: devops_lead
context_agents:
  - architect
  - engineer
expected_output: >
  NO CHANGES NEEDED (if no new infrastructure is required), OR DEVOPS COMPLETE with a
  specific list of every Terraform change, secret, SSM parameter, and GitHub Actions
  update applied to the dev environment.
---

Review the engineer's implementation output and apply any infrastructure changes required
for the feature to run in the dev environment.

**Step 1 — Load `ecs-deployment`** (`knowledge_reader`).
Confirm conventions for ECS task definition env vars, Secrets Manager patterns, and OIDC IAM roles.

**Step 2 — Read the implementation output.**
The engineer has listed "New infrastructure requirements" at the end of their implementation
output. Extract every item:
- New environment variables (non-sensitive)
- New secrets (Secrets Manager paths)
- New IAM permissions (service, action, resource)
- New SSM parameters
- New GitHub Actions steps

If the engineer listed "No new infrastructure requirements" — output `NO CHANGES NEEDED` and stop.

**Step 3 — Check existing Terraform** (`workspace_reader` on `infra/`).
Verify what already exists before adding duplicates. Read the relevant ECS task definition
module and IAM role modules.

**Step 4 — Apply changes to dev environment.**
For each required change:
- **New env var**: add to `environment` block in `infra/modules/<service>/ecs.tf`
- **New secret**: create in Secrets Manager at `/platform/dev/<service>/<key>`, add to `secrets` block, add `secretsmanager:GetSecretValue` permission
- **New IAM permission**: add statement to `infra/modules/<service>/iam.tf`
- **New SSM parameter**: create at `/platform/dev/<service>/<key>`, add `ssm:GetParameter` if not already present
- **New GitHub Actions step**: update the relevant workflow in `.github/workflows/`

Run `terraform plan` to confirm the diff. Apply only to dev (`-var="env=dev"`).

Staging and production changes are NOT applied here — they occur on the next Terraform apply
during promotion, after the feature is approved.

**Step 5 — Report.**

If no changes were needed:
```
NO CHANGES NEEDED

The feature does not introduce new env vars, secrets, or IAM permissions.
Existing configuration is sufficient for integration tests.
```

If changes were applied:
```
DEVOPS COMPLETE

Applied to dev environment:

Terraform:
- Added env var DB_SECONDARY_URL to portal ECS task definition
- Added s3:GetObject on dev-platform-datasets/* to portal task IAM role

Secrets Manager:
- Created /platform/dev/portal/secondary-db-password

SSM Parameters:
- Created /platform/dev/portal/feature-flag-new-validation

GitHub Actions:
- Added setup-secondary-db step to ci.yml (integration test env setup)

The engineer can now run BDD integration tests with TEST_RESET_ENABLED=true against dev.
```

Do NOT end with a planning statement. Output NO CHANGES NEEDED or DEVOPS COMPLETE.
