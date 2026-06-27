---
type: CrewAI Task
title: BDD Spec Finalization
description: QA Lead consolidates PO and Architect review feedback and updates feature files
tags: [bdd, finalization, qa, review-consolidation, phase-14]
timestamp: 2026-06-20T00:00:00Z
agent: qa_lead
context_agents:
  - product_owner
  - architect
expected_output: >
  BDD APPROVED with a summary of changes made, OR NEEDS FURTHER REVIEW with a list of
  unresolved items requiring human input. Updated .feature files written to disk.
---

Consolidate the Product Owner and Architect review feedback and update the Gherkin feature
files accordingly.

The review feedback is provided in your context (BDD Review Feedback section).

**Step 1 — Load `bdd-testing`** (`knowledge_reader`) to confirm conventions.

**Step 2 — Read the review feedback.**
The context contains two feedback sections:
- **Product Owner Feedback** — AC coverage gaps, business logic corrections, suggested scenarios
- **Architect Feedback** — ADD alignment issues, missing security scenarios, test structure concerns

**Step 3 — Categorise each feedback item:**
- **ACTIONABLE** — you can resolve it by adding/modifying a scenario
- **NEEDS HUMAN INPUT** — the AC is ambiguous, a design doc is missing, or the reviewers contradict each other

For items that need human input: use `ask_human` to get clarification before proceeding.

**Step 4 — Update feature files.**
For each ACTIONABLE item:
- Add missing scenarios to the relevant `.feature` file
- Correct scenario steps that misrepresent business logic or ADD contracts
- Adjust scenario ordering if test structure concerns were raised
- Update the seed data description if new setup requirements were identified

Use `platform_shell` to write updated `.feature` file content to disk.

**Step 5 — Produce updated coverage matrix.**

| Acceptance Criterion | Scenario(s) | File | Tags |
|---|---|---|---|

**Step 6 — Output verdict.**

If all PO and Architect feedback has been addressed:
```
BDD APPROVED

Changes made:
- Added Scenario "..." to cover AC-3 (PO feedback)
- Added unauthenticated scenario to [file] (Architect feedback)
- Corrected response assertion for field "X" to match ADD-NNN

Coverage matrix: [updated table]
```

If unresolved items remain after `ask_human`:
```
NEEDS FURTHER REVIEW

Unresolved items:
- [item]: [reason it cannot be resolved without human escalation]
```

Do NOT end with a planning statement. Output BDD APPROVED or NEEDS FURTHER REVIEW.
