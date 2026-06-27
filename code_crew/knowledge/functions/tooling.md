---
name: SDLC-Team-Tooling
description: Complete tool inventory — development, testing, infrastructure, communication, and marketing tools with integrations
metadata:
  type: reference
  role: all
  phase: all
---

# Tooling

---

## Development Tools

| Tool | Purpose | Who uses it |
|------|---------|------------|
| GitHub | Version control, code review, CI/CD | All engineers |
| VS Code | Code editor | Engineers |
| Claude Code | AI coding assistant (CLI) | Engineers |
| Cursor | AI-powered IDE | Engineers |
| GSD | AI orchestration for SDLC phases | Engineers, Tech Lead |
| Go 1.23+ | Backend services | Backend engineers |
| TypeScript / React | Portal SPA | Frontend engineers |
| Python 3.12+ | AI tooling, scripts | AI/ML engineers |
| Ant Design v6 | Portal UI component library | Frontend engineers |

---

## Testing Tools

| Tool | Purpose | Layer |
|------|---------|-------|
| `go test` + `testify` | Go unit + integration tests | Unit, Integration |
| Godog | BDD runner for Go | Integration BDD |
| Jest | JavaScript unit tests | Unit |
| React Testing Library | Component tests | Unit |
| Playwright | E2E browser automation | E2E BDD |
| Cypress | Alternative E2E (legacy) | E2E |
| k6 | Load testing | Performance |

---

## Infrastructure Tools

| Tool | Purpose |
|------|---------|
| AWS ECS + Fargate | Container orchestration |
| AWS RDS (PostgreSQL) | Relational database |
| AWS S3 | Object storage |
| AWS Lambda | Serverless functions |
| AWS SageMaker | ML model hosting |
| AWS Bedrock | LLM inference (IAM auth only) |
| AWS Secrets Manager | Secret storage |
| AWS SSM Parameter Store | Config storage |
| AWS CloudWatch | Metrics, logs, alarms |
| AWS X-Ray | Distributed tracing |
| AWS GuardDuty | Threat detection |
| AWS CloudTrail | API audit logging |
| Terraform | Infrastructure as code |
| GitHub Actions | CI/CD pipelines |
| OIDC | CI/CD → AWS auth (no long-lived keys) |
| ECR | Container image registry |
| Vercel | Portal SPA hosting + CDN |
| Route 53 | DNS |
| ACM | TLS certificate management |

---

## Design Tools

| Tool | Purpose |
|------|---------|
| Figma | UI/UX design, wireframes, final designs |
| FigJam | User journey maps, domain model diagrams |
| `designs/` repo | Architecture docs (ADDs, ADRs, SOPs, SDLC) |

---

## Project Management

| Tool | Purpose |
|------|---------|
| Jira | Product backlog, sprint execution, ticket tracking |
| GitHub Issues | Engineering bugs and chores (linked to Jira) |
| Confluence / Notion | Long-form documentation (non-OKF content) |
| GitHub Wiki | Technical documentation |

---

## Communication

| Tool | Purpose |
|------|---------|
| Slack | Team communication, alerts, incidents |
| Google Meet | Video conferencing |
| Email (your-org.com) | External communication, formal records |

---

## Tool Integrations

| Integration | What it does |
|------------|-------------|
| Jira ↔ GitHub | PR / branch / commit auto-linked to Jira tickets |
| GitHub → CI/CD | PR creates CI run; merge triggers deploy |
| CloudWatch → PagerDuty | Critical alerts page on-call engineer |
| CloudWatch → Slack | Warning alerts posted to `#ops-alerts` |
| Figma → Jira | Design links in Jira descriptions |

---

## Approved License Types

For open-source dependencies:
- **Approved**: MIT, Apache 2.0, BSD 2-Clause, BSD 3-Clause, ISC
- **Review required**: LGPL, MPL 2.0
- **Rejected**: GPL, AGPL, SSPL, BUSL

SBOM generated on every build. License validator checks all dependencies against this list.
