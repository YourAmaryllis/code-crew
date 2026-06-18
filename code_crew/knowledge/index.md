---
okf_version: "0.1"
type: Bundle Index
title: Code Crew Knowledge Bundle
description: OKF knowledge bundle for the YourAmaryllis virtual code development team (SDLC phases 13-19).
tags: [crewai, code-crew, sdlc]
timestamp: 2026-06-17T00:00:00Z
---

# Code Crew Knowledge Bundle

Agent instructions and task definitions for the YourAmaryllis virtual code development team.
All documents follow [OKF v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md).

Covers SOP-0 phases 13–19: sprint planning, BDD test authoring, backend/frontend development,
code review, and Definition of Done enforcement.

## Agents

* [Scrum Master](agents/scrum_master.md) - Sprint ceremonies and DoD enforcement
* [Tech Lead](agents/tech_lead.md) - Architecture alignment and cross-cutting review
* [Backend Developer](agents/backend_developer.md) - BDD-first backend implementation
* [Frontend Developer](agents/frontend_developer.md) - React + Ant Design portal UI
* [QA Engineer](agents/qa_engineer.md) - Gherkin BDD feature authoring
* [Security Reviewer](agents/security_reviewer.md) - OWASP, SBOM, zero-custody alignment

## Tasks

* [Sprint Planning Check](tasks/sprint_planning_check.md) - Verify stories meet Definition of Ready
* [Architecture Review](tasks/architecture_review.md) - Align implementation with ADRs/ADDs
* [BDD Test Authoring](tasks/bdd_test_authoring.md) - Write Gherkin feature files
* [Backend Implementation](tasks/backend_implementation.md) - Implement backend per ADD
* [Frontend Implementation](tasks/frontend_implementation.md) - Build React components
* [Security Review](tasks/security_review.md) - OWASP review and SBOM generation
* [DoD Check](tasks/dod_check.md) - Gate: verify all DoD sections pass before closure

## References

* [ADD-044: Virtual AI Development Team](/designs/ADD/ADD-044-Virtual-AI-Development-Team.md)
* [SOP-3: Dev Process](/designs/SOP/SOP-3-Dev-Process.md)
* [SOP-SDLC-GSD](/designs/SOP/SOP-SDLC-GSD.md)
* [Definition of Done](/platform/.planning/DEFINITION-OF-DONE.md)
