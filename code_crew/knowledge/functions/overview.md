---
name: SDLC-Overview
description: End-to-end software development lifecycle — phases, roles, human gates, and AI collaboration model
metadata:
  type: process
  role: all
  phase: all
---

# SDLC Overview

This document describes the full software development lifecycle (SDLC). It covers all phases from business discovery through post-launch operations, the roles responsible for each phase, human review gates, and how AI agents assist the workflow.

## Guiding Principles

- **Lean Scrum** — 2-week sprints, continuous delivery to trunk
- **Human-in-the-loop** — AI assists at every phase; humans own every gate
- **Traceability** — every artifact traces back to a requirement ID
- **Trunk-based development** — short-lived branches, no long-running feature branches
- **Zero-custody sensitive data** — customer data handling follows data governance policy
- **Clean architecture** — all code follows layered, testable structure

---

## Phases

### Discovery & Requirements (Phases 1–4)

| Phase | Activity | Owner | AI Support |
|-------|----------|-------|------------|
| 1 | Business intelligence collection | Product Owner | Market analysis, competitive research |
| 2 | Business Requirements Document (BRD) | Business Analyst / PO | Draft BRD sections |
| 3 | User journey + domain model | Product Owner + Architect | Generate journey maps, identify bounded contexts |
| 3b | Compliance requirements (CRD) | Compliance Officer | Regulation clause mapping |
| 4 | Technical Requirements Document (TRD) | Tech Lead | Translate business reqs to technical specs |

Traceability chain: `BR-YYYY-NNN → CR-YYYY-NNN → TR-YYYY-NNN → US-YYYY-NNN → code`

See: `user-journey`, `domain-model`, `story-format`, `requirements-management`

---

### Architecture & Design (Phases 5–11)

| Phase | Activity | Owner | AI Support |
|-------|----------|-------|------------|
| 5 | Architecture design (SAD/TSD) | Architect | Diagram generation, pattern analysis |
| 6 | Security analysis + threat modeling | Security Lead | Threat scenario generation |
| 7 | Architecture & requirements alignment | **Human gate** (Architect + PO) | Consistency checking |
| 8 | Technical requirements update | Tech Lead | Gap analysis |
| 9 | UX wireframe design | UX Designer | Layout suggestions |
| 10 | UX final design (Figma) | UX Designer | Component catalogue alignment |
| 11 | Technical design document (ADD) | Architect | ADD draft generation |

See: `code-architecture`, `sad-maintenance`, `security-privacy`, `domain-driven-design`

---

### Implementation (Phases 12–19)

Managed via sprints. Each Jira ticket is a user story.

| Phase | Activity | Owner | AI Support |
|-------|----------|-------|------------|
| 12 | Infrastructure code + CI/CD pipelines | DevOps Lead | Terraform scaffold, pipeline templates |
| 13 | Implementation planning | Tech Lead + SM | **Human gate**: sprint planning check |
| 14 | E2E (BDD) test case development | QA Lead | Scenario generation from ACs |
| 15 | Unit test development | Engineer | Test stubs, coverage analysis |
| 16 | Environment preparation | DevOps Lead | Environment diff check |
| 17 | UI development | Frontend Engineer | AI pair programming (Figma → code) |
| 18 | Backend development | Backend Engineer | AI pair programming |
| 19 | Code review + QA | Tech Lead / Architect | **Human gate**: code review approval |

See: `development-workflow`, `bdd-implementation`, `bdd-authoring`, `scaffold-code`, `scaffold-test`

---

### Release & Operations (Phases 20–22)

| Phase | Activity | Owner | AI Support |
|-------|----------|-------|------------|
| 20 | Staging deployment + E2E testing | DevOps Lead | Test run analysis |
| 21 | Production deployment | **Human gate**: Release Manager approval | Release notes generation |
| 22 | Post-launch care + support | Ops Engineer | Anomaly summaries, access reports |

Production promotion is **human-triggered only**. Agents do not push, apply Terraform, or promote to production autonomously.

See: `release-process`, `ci-cd-pipeline`

---

## Ongoing Processes

- **Product backlog management** — weekly refinement (Wednesdays), bi-weekly sprint planning (Tuesdays)
- **Change control** — all requirement, architecture, design, code, and infra changes; see `change-control`
- **Vulnerability scanning** — continuous; see `security-privacy`
- **Audit & compliance evidence** — CI artefacts, traceability chain; see `auditing-evidence`, `compliance-evidence`

---

## Sprint Ceremonies

| Ceremony | Cadence | Duration | Facilitator |
|----------|---------|----------|-------------|
| Daily Standup | Daily | 15 min | Scrum Master |
| Backlog Refinement | Weekly (Wednesday) | 1–2 hr | Scrum Master + PO |
| Sprint Planning | Bi-weekly (Tuesday) | 2–4 hr | Scrum Master |
| Sprint Review | Bi-weekly (Friday) | 1–2 hr | Product Owner |
| Retrospective | Bi-weekly (Friday) | 1 hr | Scrum Master |

---

## Sprint Metrics

- **Velocity** — story points completed per sprint
- **Burndown** — daily progress toward sprint goal
- **Cycle time** — Jira ticket open → done

---

## Three-System Architecture

| System | Purpose |
|--------|---------|
| Jira | Product scope, user stories, sprint execution |
| `designs/` (this repo) | Architecture documents (ADD, ADR, SDLC) |
| GitHub (`platform`) | Code, CI/CD, pull requests |

---

## Human Checkpoints Summary

| Gate | Who approves | Blocks |
|------|-------------|--------|
| Sprint Planning Check (Phase 13) | Scrum Master | Sprint start |
| Architecture Alignment (Phase 7) | Architect + PO | Design work |
| Code Review (Phase 19) | Tech Lead / Architect | Merge to trunk |
| DoD Check | Scrum Master | Story closure |
| Staging sign-off (Phase 20) | QA Lead | Prod promotion |
| Production promotion (Phase 21) | Release Manager | Prod deploy |
| Terraform apply | Architect / Release Manager | Infra change |
