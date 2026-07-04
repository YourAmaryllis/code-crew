---
type: CrewAI Task
title: Infrastructure Drift Assessment
description: DevOps Lead surveys all infrastructure categories and produces a categorized drift report
tags: [devops, drift, terraform, cicd, monitoring, infrastructure]
agent: devops_lead
expected_output: >
  NO DRIFT DETECTED (if everything is consistent), OR a structured drift report listing
  each item as DRIFT: [category] [severity] — [description of actual vs. expected],
  followed by DRIFT ASSESSMENT COMPLETE.
---

Survey the project's infrastructure for drift: mismatches between what the codebase
defines and what is currently deployed or configured.

**Step 1 — Read the project structure.**
Load `.code-crew/structure.md` to understand the project's stacks, services, CI/CD
methods, and detected architecture. This tells you which categories to check and where
to look.

**Step 2 — Terraform drift.**
If Terraform (or equivalent IaC) is in use:
1. Read the infrastructure directory (Terraform modules, CDK stacks, Pulumi programs)
   using `workspace_reader` to understand what resources are defined.
2. Run `terraform plan -detailed-exitcode` (or equivalent) to surface differences
   between the IaC definition and the current state. Do not run `apply`.
3. Check for environment parity: are dev, staging, and prod modules using consistent
   instance sizes, encryption settings, and tags? Inconsistencies that could cause
   "works in dev, breaks in prod" failures are HIGH severity.
4. Check that all defined resources are tagged with required tags (env, service,
   managed-by, project).

**Step 3 — CI/CD pipeline drift.**
Read the CI/CD configuration files (GitHub Actions workflows, GitLab CI YAML,
Jenkinsfile, etc.) using `workspace_reader`:
1. Are all services represented in the CI pipeline? Check that services present in the
   codebase have corresponding build, test, and deploy steps.
2. Do pipeline steps reference files, scripts, or Docker images that still exist?
   A step referencing a removed script or a deleted service directory is HIGH severity.
3. Is OIDC authentication used for cloud access (no long-lived keys in secrets)?
   Any long-lived access key in CI secrets is CRITICAL severity.
4. Are deploy steps scoped correctly — dev deploys on PR, staging on merge to main,
   prod only on explicit trigger?

**Step 4 — Monitoring and alerting drift.**
Read monitoring configuration (Terraform CloudWatch alarms, Grafana dashboards,
Datadog monitors, etc.) using `workspace_reader`:
1. Does each service have a health-check alarm or uptime monitor?
2. Do alert rules reference endpoints, metric names, or log groups that currently exist?
   Alerts referencing removed endpoints or renamed metrics are dead alerts (HIGH severity).
3. Are runbook links in alerts pointing to files that exist in the designs repo?

**Step 5 — Environment configuration drift.**
Compare environment variable and secret configuration across dev, staging, and prod:
1. Read the Terraform (or equivalent) task/pod definitions for each environment.
2. Identify env vars present in dev but missing from staging or prod — these will cause
   silent runtime failures on promotion (HIGH severity).
3. Identify secrets that exist in dev Secrets Manager but have no equivalent path in
   staging or prod.

**Step 6 — Produce the drift report.**

Format each drift item as:
```
DRIFT: [category] [severity] — [what you found] vs. [what is expected]
```

Severity levels:
- **CRITICAL** — will cause immediate production failure or security incident
- **HIGH** — will cause failure on promotion to staging or prod
- **MEDIUM** — inconsistency that should be resolved but won't block current work
- **LOW** — style/convention deviation; no functional impact

Example items:
```
DRIFT: terraform HIGH — staging RDS instance uses db.t3.micro; dev and prod use db.t3.small; promotion will behave differently
DRIFT: cicd HIGH — deploy-staging workflow references ./scripts/migrate.sh which does not exist
DRIFT: cicd CRITICAL — AWS_ACCESS_KEY_ID found as a hardcoded secret in .github/workflows/deploy.yml; OIDC must be used
DRIFT: monitoring MEDIUM — CloudWatch alarm 'api-latency' references metric dimension ServiceName=old-api-gateway which was renamed
DRIFT: config HIGH — FEATURE_SERVICE_URL env var set in dev task definition but missing from staging task definition
DRIFT: terraform LOW — dev ECS task is missing managed-by = "terraform" tag
```

If there is no drift across all categories, output:
```
NO DRIFT DETECTED

All checked categories are consistent:
- Terraform: plan shows no changes
- CI/CD: all pipeline steps reference existing files and use OIDC auth
- Monitoring: all alert rules reference active resources
- Config: env var parity confirmed across dev, staging, prod
```

Otherwise, end with exactly:
```
DRIFT ASSESSMENT COMPLETE
```

**On tool failure**: if `terraform plan` is unavailable or fails with an auth error,
note it as a skipped check and continue with the remaining categories. Do not block
the entire assessment on a single tool failure.
