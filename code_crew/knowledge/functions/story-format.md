---
name: SDLC-Product-StoryFormat
description: User story format, Definition of Ready, estimation, and Jira conventions for product backlog items
metadata:
  type: process
  role: product
  phase: "2, 4, 13"
---

# User Story Format & Product Backlog

---

## User Story Format

```
As a <persona>,
I want <action or capability>,
So that <business value or outcome>.
```

Every story must have:
- A clear persona (from the user journey / domain model)
- A specific action (not vague: "manage" → "add", "edit", "delete")
- A stated value (why this matters to the user or business)

---

## Acceptance Criteria

ACs are plain English statements describing observable, testable outcomes. They are **not** Gherkin — Gherkin is for BDD feature files (authored by QA in Phase 14).

Good AC format:
```
1. When a user submits the registration form with a valid email, 
   the system creates a pending account and sends a verification email.
2. When a user submits the registration form with an invalid email, 
   a validation error is displayed and no account is created.
3. The verification email contains a link that expires after 24 hours.
```

Bad AC (too vague):
```
- Email verification works
- Handle errors
```

Rules:
- Each AC is a complete sentence
- Each AC is independently testable
- Each AC maps to at least one BDD scenario (written by QA)
- No Gherkin in Jira ACs — save Given/When/Then for `.feature` files

---

## Requirement Traceability IDs

Each requirement has a unique ID that flows through all artifacts:

```
BR-YYYY-NNN   Business Requirement
CR-YYYY-NNN   Compliance Requirement
TR-YYYY-NNN   Technical Requirement
US-YYYY-NNN   User Story (Jira key used in code)
```

Traceability chain: `BR-2026-001 → TR-2026-042 → PROJ-92 → code commit`

The commit message references `[REQ:TR-2026-042]` to maintain this chain.

---

## Definition of Ready (DoR)

A story is **ready to be pulled into a sprint** when:

- [ ] Story follows "As a / I want / So that" format
- [ ] Acceptance criteria are written in plain English (not Gherkin)
- [ ] All ACs are independently testable
- [ ] Story is estimated (Fibonacci story points)
- [ ] Dependencies are identified and either resolved or tracked
- [ ] Design reference exists (Figma URL, HTML attachment, or ADD link) — required when UI is involved; optional for backend-only or trivial changes
- [ ] Story is sized appropriately (≤ 8 points; split if larger)
- [ ] Story is linked to parent epic (if applicable)

---

## Estimation

Story points use the Fibonacci scale: 1, 2, 3, 5, 8 (split if > 8).

| Points | Meaning |
|--------|---------|
| 1 | Trivial — < 1 hour, no risk |
| 2 | Small — a few hours, low risk |
3 | Medium — half day, some uncertainty |
| 5 | Large — 1–2 days, moderate complexity |
| 8 | Very large — multi-day, significant unknowns → consider splitting |

Estimation is done by the team in backlog refinement. Tech Lead provides feasibility input. Product Owner provides business value context.

---

## Jira Conventions

| Field | Convention |
|-------|-----------|
| Issue type | Story, Bug, Chore, Spike |
| Summary | `[PROJ-NNN] Short imperative description` |
| Labels | Feature area (e.g. `auth`, `portal`, `billing`) |
| Epic | Every story linked to an epic |
| Sprint | Assigned during sprint planning |
| Story Points | Required before sprint commitment |
| Design ref | ADD/ADR number or Figma URL in description |

**Jira ↔ GitHub linking:**
- Smart commit: `PROJ-92 #comment BDD test passing` auto-links the commit
- PR title must include the Jira key
- Use Jira's GitHub integration development panel to show branch and PR status

---

## Product Backlog Management

- **Backlog refinement**: weekly (Wednesdays), 1–2 hours
- **Sprint planning**: bi-weekly (Tuesdays), 2–4 hours
- **Prioritization factors**: business value, user impact, dependency unblocking, compliance deadline, technical debt ratio

The Product Owner owns backlog prioritization. Scrum Master facilitates refinement. Tech Lead provides feasibility and estimation guidance.
