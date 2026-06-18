---
type: CrewAI Task
title: Environment Plan
description: Scope infra changes and confirm environment readiness before development starts
tags: [environment, readiness, phase-16, ops, gate]
timestamp: 2026-06-17T00:00:00Z
agent: ops_lead
expected_output: >
  An environment readiness plan listing: infrastructure changes needed (Terraform,
  CI/CD, monitoring), sequence and dependencies, estimated effort, and a readiness
  verdict (READY / NOT READY / WORK-REQUIRED). If work is required, list tasks with
  owner assignments.
---

Review the sprint's infrastructure requirements and confirm what needs to change in `ops/`.

Load SOP-3-Dev-Process (Phase 16 section) via the `sop_reader` tool to confirm the
expected readiness criteria.

**Assessment areas:**

1. **Terraform changes**: does the feature require new AWS resources, IAM roles, security
   groups, or changes to existing modules? List each change and its ADD reference.

2. **CI/CD changes**: does the feature require new GitHub Actions workflows or path filter
   updates? Identify which service subtrees are affected (ADR-024).

3. **Monitoring changes**: does the feature add new service endpoints or critical business
   events that need dashboards and alerts?

4. **Database migrations**: are there schema changes? Confirm migration scripts exist and
   will run as part of the deployment pipeline.

5. **Environment variables**: list any new environment variables needed across dev, staging,
   and prod. Confirm secrets are in AWS Secrets Manager (not hardcoded in Terraform).

6. **Dependency readiness**: are all upstream services and environments stable? Any known
   outages or maintenance windows that would block the sprint?

**Readiness verdict:**
- **READY**: all environments are up, no infra changes needed before coding starts
- **NOT READY**: infra changes are needed; work must complete before Phase 17/18 begins
- **WORK-REQUIRED**: changes can be parallelized; identify which must complete first

Output the plan as a structured report with sequenced tasks and clear owner assignments.
