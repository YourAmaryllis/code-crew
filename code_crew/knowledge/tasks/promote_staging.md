---
type: CrewAI Task
title: Promote to Staging
description: DevOps promotes the verified dev image to staging and waits for ECS stabilisation
tags: [devops, staging, promotion, ecs, ecr, cicd, phase-21]
agent: devops_lead
expected_output: >
  STAGING DEPLOYED — image sha, ECS service name, staging URL, and confirmation that
  the service reached a stable state. OR INCOMPLETE: <reason> if the pipeline failed.
---

Promote the implementation from dev to the staging environment.

**Step 1 — Identify the image to promote.**
From the release_notes task output (in your context), find the git SHA or image tag that
passed DoD. If not explicit, run:
```bash
git rev-parse --short HEAD
```

**Step 2 — Determine the CI/CD stack.**
Use `knowledge_reader` to load `github` or `gitlab` (whichever the platform uses).
Check for a `.github/` directory or `.gitlab-ci.yml` in `workspace_reader` to confirm.

**Step 3 — Trigger staging promotion.**
Using the CI/CD stack conventions, trigger the `promote-staging` workflow/pipeline:

For GitHub Actions:
```bash
gh workflow run promote-staging.yml \
  --field image_sha=<sha> \
  --field service=<ecs-service-name>

# Wait for the run to complete
gh run watch $(gh run list --workflow=promote-staging.yml --limit=1 --json databaseId -q '.[0].databaseId')
```

For GitLab CI, use the pipeline trigger API (see `gitlab` stack doc).

**Step 4 — Confirm stabilisation.**
After the workflow completes, verify ECS reports the service as RUNNING:
```bash
aws ecs describe-services --cluster staging --services <service> \
  --query 'services[0].{status:status,running:runningCount,desired:desiredCount}'
```

Expected: `status: ACTIVE`, `running == desired`.

**Step 5 — Output the staging URL.**
Retrieve the staging load balancer DNS from the ECS service or from Terraform outputs:
```bash
aws elbv2 describe-load-balancers --names staging-alb \
  --query 'LoadBalancers[0].DNSName' --output text
```

**Completion signal — mandatory.**
End with exactly:
- `STAGING DEPLOYED` — service stable, URL confirmed
- `INCOMPLETE: <reason>` — pipeline failed or service did not stabilise
