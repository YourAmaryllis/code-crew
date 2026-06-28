# Code Crew Tasks

Executed sequentially per sprint story. Each task feeds context to the next.

## Context discipline — applies to every task

**Read the ticket before loading anything.**

Before calling `knowledge_reader` or `workspace_reader`, read the Jira ticket and answer:
1. Which layer is affected? (backend only / frontend only / both)
2. Which stack(s) are involved? (Go, TypeScript/React, Python, Terraform — match to what the ticket actually touches)
3. Which specific ADD/ADR is relevant? (the one governing the component being changed — not all of them)

Then load **only** what those answers require. Examples:
- Backend validation change → `go-backend` + the relevant ADD. Do **not** load `typescript-react`, ECS, or Terraform docs.
- New UI component → `typescript-react` + the relevant ADD. Do **not** load `go-backend` unless the ticket also changes an API.
- Config-only change → load only the ADD for that component. No stack docs needed.

Never load a document speculatively. If you are uncertain whether something is in scope, skip it — a missing doc causes an incomplete answer; an oversized context causes a timeout that fails the whole task.

* [Sprint Planning Check](sprint_planning_check.md) - Verify Definition of Ready; gate before work begins
* [Architecture Review](architecture_review.md) - Align with ADRs/ADDs; gate before implementation
* [BDD Test Authoring](bdd_test_authoring.md) - Write Gherkin features; gate before coding
* [Backend Implementation](backend_implementation.md) - Implement per ADD with unit tests
* [Frontend Implementation](frontend_implementation.md) - Build React components with a11y and tests
* [Security Review](security_review.md) - OWASP, Threat Dragon, platform constraint check gate before PR
* [DoD Check](dod_check.md) - Final gate: all DoD sections must PASS before closure
