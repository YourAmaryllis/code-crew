---
type: CrewAI Task
title: CI/CD Config
description: Author GitHub Actions workflow for path-filtered CI covering the sprint's service subtree
tags: [cicd, github-actions, path-filter, pipeline, phase-12]
timestamp: 2026-06-17T00:00:00Z
agent: cicd_engineer
context_agents:
  - ops_lead
  - terraform_engineer
expected_output: >
  GitHub Actions workflow YAML (ready to commit to .github/workflows/) with:
  path-filtered triggers, quality gate sequence (lint → test → scan → build),
  staging auto-deploy on main merge, and production manual-trigger only.
---

Design or update the GitHub Actions CI/CD workflow for the service subtrees affected
by this sprint.

Load ADR-024 via the `sop_reader` tool to confirm the path-filter requirements.

**Trigger configuration** (ADR-024 path-filtered):
```yaml
on:
  push:
    paths: ['<service>/**', '.github/workflows/<workflow>.yml']
  pull_request:
    paths: ['<service>/**']
  workflow_dispatch:
    inputs:
      environment:
        type: choice
        options: [staging, prod]
```

**Quality gate sequence** (SOP-3 Phase 19) — jobs run in dependency order:
1. `lint` — golangci-lint (Go) or ruff (Python) or eslint (TS); fail fast
2. `unit-test` — run unit tests with coverage report; fail if coverage drops below threshold
3. `integration-test` — run BDD/integration tests against ephemeral test environment
4. `security-scan` — SBOM (syft) + vulnerability scan (grype); fail on Critical/High CVEs
5. `build-image` — build Docker image; push to ECR dev repository only (not prod ECR)
6. `staging-deploy` — only on push to `main`; uses OIDC to assume role; calls ECS UpdateService

**Production deploy** (manual only):
- `workflow_dispatch` with `environment: prod` input; requires GitHub environment approval
- Never triggered automatically — only on explicit human dispatch

**OIDC auth** for AWS:
```yaml
permissions:
  id-token: write
  contents: read
```
Use `aws-actions/configure-aws-credentials@v4` with `role-to-assume`; no long-lived keys.

**Reusable workflows**: if lint/test/scan steps already exist in `.github/workflows/shared/`,
call them with `uses: ./.github/workflows/shared/<step>.yml` rather than duplicating.

Produce the complete workflow YAML with inline comments explaining non-obvious choices.
