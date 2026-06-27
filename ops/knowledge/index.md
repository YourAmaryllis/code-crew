---
okf_version: "0.1"
type: Bundle Index
title: Ops Crew Knowledge Bundle
description: OKF knowledge bundle for the your organization virtual ops team (SDLC phases 12, 16, 20-22).
tags: [crewai, ops-crew, terraform, cicd, deployment]
timestamp: 2026-06-17T00:00:00Z
---

# Ops Crew Knowledge Bundle

Agent instructions and task definitions for the your organization virtual ops team.
Covers SOP-0 phases 12, 16, and 20–22: infrastructure code, environment preparation,
staging deployment, production deployment, and post-launch monitoring.

## Agents

* [Ops Lead](agents/ops_lead.md) - Infrastructure orchestration and environment readiness
* [Terraform Engineer](agents/terraform_engineer.md) - Terraform modules per ADD-018
* [CI/CD Engineer](agents/cicd_engineer.md) - GitHub Actions pipelines (path-filtered per ADR-024)
* [Monitoring Engineer](agents/monitoring_engineer.md) - CloudWatch, alerting, anomaly detection
* [Release Manager](agents/release_manager.md) - ECR promote, GitHub Releases, staging/prod gates

## Tasks

* [Environment Plan](tasks/environment_plan.md) - Scope and readiness check before infra work
* [Terraform Write](tasks/terraform_write.md) - Author/review Terraform per ADD-018
* [CI/CD Config](tasks/cicd_config.md) - GHA workflow for path-filtered CI
* [Monitoring Setup](tasks/monitoring_setup.md) - Dashboards, alerts, anomaly detection
* [Release Plan](tasks/release_plan.md) - Staging promote checklist; prod gate (human-triggered)

## References

* [ADD-044: Virtual AI Development Team](/designs/ADD/ADD-044-Virtual-AI-Development-Team.md)
* [ADD-018: Terraform Module Structure](/designs/ADD/ADD-018-Terraform-Module-Structure.md)
* [ADR-024: Monorepo](/designs/ADR/ADR-024-Monorepo-Product-Repositories.md)
* [SOP-SDLC-Trunk-Promote-Release](/designs/SOP/SOP-SDLC-Trunk-Promote-Release.md)
* [Definition of Done](/platform/.planning/DEFINITION-OF-DONE.md)
