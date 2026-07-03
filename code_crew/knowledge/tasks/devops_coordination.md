---
type: CrewAI Task
title: DevOps Coordination
description: DevOps Lead applies infrastructure changes and deploys the feature using the project's configured tooling
tags: [devops, infrastructure, deployment, phase-16]
timestamp: 2026-06-20T00:00:00Z
agent: devops_lead
context_agents:
  - architect
  - engineer
expected_output: >
  NO CHANGES NEEDED (if no new infrastructure or code to deploy), OR DEVOPS COMPLETE with a
  specific list of every infrastructure change applied and the deployment action taken.
---

Review the engineer's implementation output and: (1) apply any required infrastructure changes, and (2) deploy the code changes using the project's configured tooling.

**Step 0 — Read the FILES CHANGED block.**
From the engineer's implementation output, find the `FILES CHANGED:` block listing every file created or modified. If the block is absent, output `INCOMPLETE: engineer did not provide FILES CHANGED block` and stop.

**Step 1 — Understand the project's tooling.**
Read `.code-crew/structure.md` (or `.code-crew/config.yaml`) using `workspace_reader`. The `ci.deployment_methods` field lists every CI/CD and infrastructure tool detected in this project, for example:
```
ci:
  deployment_methods:
    - github-actions
    - terraform
```
Multiple tools are common. Use the right tool for each concern:
- **Infra provisioning** (new resources, permissions, secrets): Terraform, AWS CDK, Pulumi, etc.
- **Code deployment** (getting new code running in dev): the CI/CD pipeline (GHA, GitLab CI, Jenkins), docker-compose, fly.io, Vercel, etc.

The startup checks have already verified that required CLIs are installed (terraform, gh, glab, docker, cdk, etc.). Use those tools directly.

**Step 2 — Check infrastructure requirements.**
From the engineer's output, find "New infrastructure requirements". Extract every item:
- New environment variables (non-sensitive)
- New secrets (e.g. Secrets Manager, Vault, SSM)
- New IAM permissions or roles
- New managed resources (databases, queues, topics, buckets)
- New CI/CD workflow changes needed for the test environment

If the engineer stated "No new infrastructure requirements" — skip Steps 3–4 and go to Step 5.

**Step 3 — Identify new env vars / secrets in the changed code.**
Before reading infrastructure files, use `search_ast` to enumerate exactly what the code now requires:
- Go: `search_ast pattern="os.Getenv($KEY)" language="go" path="<service>"` — lists every env var read
- TypeScript: `search_ast pattern="process.env[$KEY]" language="typescript"` or `search_ast pattern="process.env.$KEY" language="typescript"`

Cross-reference this list against the FILES CHANGED block to identify which env vars are new in this PR.

**Step 3b — Check existing infrastructure** (`workspace_reader`).
Use `code_index search "terraform env var secret <var_name>"` to find if a variable is already declared before reading Terraform files. Read the relevant infrastructure files (Terraform modules, CDK stacks, Helm values, etc.) only for variables confirmed to be new. Verify what already exists to avoid duplicates.

**Step 4 — Apply infrastructure changes.**
Use whichever infra tool is configured (from Step 1) to apply the changes to the dev environment:
- Add env vars / secrets / IAM permissions to the dev-tier resource definitions
- For Terraform: `terraform plan` first to confirm the diff, then apply with `-target` scoped to dev resources
- For CDK: `cdk deploy --context env=dev`
- For Pulumi: `pulumi up --stack dev`
- For cloud CLIs (aws, gcloud, az): apply only to dev; document exact commands run
- Do NOT touch staging or production — those are promoted separately

**Step 5 — Deploy the code changes.**
Only run this step if the FILES CHANGED block contains application code files (not infra-only changes).

Use the deployment tool configured for this project (from Step 1):
- **CI pipeline (GHA, GitLab CI, Jenkins, etc.)**: commit the files from FILES CHANGED (list them explicitly — do not use `git add .`) with a conforming commit message, then push the feature branch. The pipeline handles build, test, and deploy to dev automatically.
- **docker-compose**: rebuild and restart the affected services (`docker-compose up -d --build <service>`)
- **fly.io**: `fly deploy --config fly.toml`
- **Vercel**: `vercel deploy --env dev`
- **Custom script**: run the project's deploy script with the dev target

When using a CI pipeline: push the branch and stop — do NOT use `async_job` to trigger or wait here.
`async_job` is for staging/production promotion only. Dev CI runs automatically from the push.

**Step 6 — Report.**

If infrastructure was changed and code was deployed:
```
DEVOPS COMPLETE

Infrastructure changes applied (dev):
  [Terraform / CDK / etc.]:
  - Added DB_SECONDARY_URL env var to portal service definition
  - Added s3:GetObject on dev-datasets/* to portal task role
  - Created secret /platform/dev/portal/secondary-db-password

Code deployment:
  - Committed 4 files to feature/LOOPLAT-92-data-dictionary-mandatory
  - Pushed branch → [CI pipeline] now running against dev
```

If only code was deployed (no infra changes):
```
DEVOPS COMPLETE

No infrastructure changes required.

Code deployment:
  - Committed 4 files to feature/LOOPLAT-92-data-dictionary-mandatory
  - Pushed branch → [CI pipeline] now running against dev
```

If nothing was needed:
```
NO CHANGES NEEDED

No new infrastructure requirements and no code files to deploy.
```

**On tool failure** — log the error, try once with an alternative, then skip and continue. Never use absolute paths in shell commands. Document any skipped steps in the report.

Do NOT end with a planning statement. Output NO CHANGES NEEDED or DEVOPS COMPLETE.
