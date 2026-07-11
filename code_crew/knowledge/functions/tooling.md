---
name: SDLC-Team-Tooling
description: Tool inventory by category — development, testing, infrastructure, communication, and project management
metadata:
  type: reference
  role: all
  phase: all
---

# Tooling

The specific tools in each category are configured for this project. This document describes the categories and how they connect. Refer to the active stack documents for exact tool names and versions.

---

## Development Tools

| Category | Examples |
|----------|---------|
| Version control | GitHub, GitLab, Bitbucket |
| Code editor / IDE | VS Code, JetBrains, Cursor |
| AI coding assistant | Claude Code, Copilot |
| Backend language runtime | Go, Python, Java, Rust, etc. (see backend stack document) |
| Frontend framework | React, Vue, Angular, Svelte (see frontend stack document) |
| Script / AI tooling | Python (see scripts stack document) |

---

## Testing Tools

| Category | Examples |
|----------|---------|
| Unit + integration tests | Language-native test framework (see stack document) |
| BDD runner | Godog, Cucumber, Behave, pytest-bdd (see bdd-testing stack) |
| E2E browser automation | Playwright, Cypress, Selenium |
| Load testing | k6, Locust |

---

## Infrastructure Tools

The project's infrastructure toolchain is documented in `.code-crew/structure.md` under `ci.deployment_methods`. Common categories:

| Category | Examples |
|----------|---------|
| Container orchestration | AWS ECS/Fargate, Kubernetes, Fly.io |
| Database | AWS RDS, Cloud SQL, Supabase |
| Object storage | AWS S3, GCS, Azure Blob |
| Serverless | AWS Lambda, Cloud Functions |
| Secrets | AWS Secrets Manager, HashiCorp Vault, Doppler |
| Config | AWS SSM Parameter Store, environment variables |
| Observability | AWS CloudWatch, Datadog, Grafana |
| Tracing | AWS X-Ray, Jaeger, Honeycomb |
| CI/CD | GitHub Actions, GitLab CI, Jenkins |
| IaC | Terraform, AWS CDK, Pulumi |
| Container registry | AWS ECR, Docker Hub, GHCR |
| CDN / hosting | Vercel, Cloudflare, AWS CloudFront |

---

## Design Tools

| Tool | Purpose |
|------|---------|
| Figma | UI/UX design, wireframes, final designs |
| FigJam / Miro | User journey maps, domain model diagrams |
| `designs/` repo | Architecture docs (ADDs, ADRs, SOPs, SDLC) |

---

## Project Management

The issue tracker type is configured via `issue_tracker.type` in `~/.code-crew/config.yaml`:
- `jira` — Jira Cloud or Server
- `linear` — Linear
- `github` — GitHub Issues

---

## Communication

Standard categories: team messaging (Slack, Teams), video conferencing, email.

---

## Approved License Types

For open-source dependencies:
- **Approved**: MIT, Apache 2.0, BSD 2-Clause, BSD 3-Clause, ISC
- **Review required**: LGPL, MPL 2.0
- **Rejected**: GPL, AGPL, SSPL, BUSL

SBOM generated on every build. License validator checks all dependencies against this list.
