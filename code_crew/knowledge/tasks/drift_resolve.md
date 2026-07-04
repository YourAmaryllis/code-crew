---
type: CrewAI Task
title: Infrastructure Drift Resolution
description: DevOps Lead works through the drift assessment report and resolves each item
tags: [devops, drift, terraform, cicd, monitoring, infrastructure]
agent: devops_lead
context_agents:
  - devops_lead
expected_output: >
  DRIFT RESOLVED with a list of every change made, or DRIFT PARTIALLY RESOLVED listing
  which items were fixed and which require manual intervention with reasons.
---

Work through the drift assessment report (provided as context) and resolve each drift item.
Address items in severity order: CRITICAL → HIGH → MEDIUM → LOW.

**Before starting**, re-read the drift report carefully:
- Group items by category (terraform, cicd, monitoring, config)
- Identify which items you can fix directly vs. which require human action
- Note any items that are blocked on each other (e.g. a config drift fix may require
  a Terraform change to complete first)

---

## Terraform drift

For each `DRIFT: terraform` item:

1. Read the relevant infrastructure module using `workspace_reader`.
2. Make the required changes (instance size, tag, encryption setting, variable value).
3. Run `terraform plan` scoped to the affected resource to confirm the diff is correct.
4. Apply **to dev first**: `terraform apply -target=<resource> -var-file=env/dev.tfvars`
5. Verify the apply succeeded with `terraform show`.
6. Note the change in your report. Staging and prod will be updated on promotion.

For environment parity issues (dev/staging/prod inconsistency):
- Fix the lowest environment first (dev), then staging, then prod
- Each apply is separate and must be verified before the next

**Never run `terraform apply` without a `-target` scope or without a preceding `plan`.**

---

## CI/CD pipeline drift

For each `DRIFT: cicd` item:

1. Read the relevant workflow file using `workspace_reader`.
2. Fix the issue:
   - Missing script: create the script stub or update the step to use the correct path
   - Dead step reference: remove or update the step
   - OIDC migration: replace static credential secrets with the OIDC provider config; see `stacks/cicd-github-actions` for the standard OIDC setup pattern
   - Missing service coverage: add build/test/deploy steps following the existing patterns
3. Commit the updated workflow file using `platform_shell`:
   ```
   git add .github/workflows/<file>.yml
   git commit -m "fix(ci): resolve CI/CD drift — <description>"
   ```
4. Push to the current branch. The CI pipeline will validate on the next run.

---

## Monitoring drift

For each `DRIFT: monitoring` item:

1. Read the relevant monitoring definition (Terraform CloudWatch module, Grafana JSON, etc.)
2. Fix the issue:
   - Dead metric reference: update the metric name/dimension to the current value, or remove the alert if the service no longer exists
   - Dead endpoint reference: update the health-check URL or remove the probe
   - Missing service monitor: add a health-check alarm using the project's monitoring module pattern
   - Dead runbook link: update the annotation to point to the current designs doc path
3. If the monitoring config is in Terraform: run `terraform plan` and apply as per the Terraform drift steps above.
4. If the monitoring config is in a non-IaC format (Grafana JSON exported, Datadog YAML): commit the updated file and note that the config must be imported manually.

---

## Config drift (environment variable parity)

For each `DRIFT: config` item:

1. Read the task/pod definition for the affected environment using `workspace_reader`.
2. Add the missing env var or secret reference to the environment's definition.
3. For non-sensitive values: add to the `environment` block in the task definition.
4. For secrets: verify the secret path exists in the target environment's Secrets Manager
   before adding the reference. If the secret does not exist, create it first:
   ```
   aws secretsmanager create-secret \
     --name /platform/<env>/<service>/<key> \
     --description "Added by drift resolution" \
     --secret-string "PLACEHOLDER — update with actual value"
   ```
   Then add it to the `secrets` block in the task definition.
5. Apply the Terraform change as per the Terraform drift steps.

---

## Report

When all items are processed:

```
DRIFT RESOLVED

Changes applied:

Terraform:
- [resource]: [what changed] (dev ✓ | staging ✓ | prod ✓)
- ...

CI/CD:
- [workflow file]: [what changed] — committed to [branch]
- ...

Monitoring:
- [monitor name]: [what changed]
- ...

Config:
- [service]/[environment]: added [KEY] env var / secret reference
- ...

Items requiring manual intervention:
- [item]: [reason it could not be auto-resolved, what the human must do]
```

If all items were resolved, use `DRIFT RESOLVED`.
If some items remain, use `DRIFT PARTIALLY RESOLVED` and list the outstanding items with
the reason each could not be completed automatically.
