---
name: SDLC-Team-DefinitionOfDone
description: The Definition of Done — all criteria that must be satisfied before a user story is closed
metadata:
  type: process
  role: all
  phase: "13, 19, 20"
---

# Definition of Done

A user story is **Done** when all six sections below are satisfied. The Scrum Master verifies each section before closing the Jira ticket.

---

## Section 1: Jira Issue Completeness

- [ ] Story follows "As a / I want / So that" format
- [ ] All acceptance criteria written in plain English (not Gherkin)
- [ ] Each AC is independently testable
- [ ] Design reference present when UI is involved:
  - Figma URL in description, **or**
  - HTML design attachment with explicit reference in description ("see attached HTML design"), **or**
  - ADD/ADR link in description or Jira comment, **or**
  - Explicitly noted as "No design required — backend-only / trivial change"
- [ ] ADD/ADR references extracted and visible to the crew (description or comments)

---

## Section 2: BDD Test Scenarios — Implemented and Passing

- [ ] Every AC has at least one BDD scenario (authored by QA in `.feature` files)
- [ ] Step definitions implemented by engineer
- [ ] BDD runner executed with `@PROJ-NNN` tag — actual runner output attached as evidence
- [ ] All scenarios passing (zero failures)
- [ ] Test report or CI run URL posted as Jira comment

**"Scenarios exist" is not sufficient.** The Scrum Master runs the BDD runner tool and verifies output.

Evidence format (Jira comment):
```
BDD test run for PROJ-NNN: ✅ PASSED
Run: https://github.com/your-org/platform/actions/runs/XXXXXXX
Scenarios: N passing, 0 failing
Coverage: All N ACs covered
```

---

## Section 3: Branch, Commits, and Pull Request

- [ ] Branch name: `feature/PROJ-NNN-short-slug` or `fix/PROJ-NNN-slug`
- [ ] Commits follow format: `<type>(<scope>): <description> [REQ:<ID>] <JIRA-KEY>`
- [ ] PR title matches commit subject format
- [ ] PR description includes: Jira link, design doc references, test report link
- [ ] One primary PR per user story
- [ ] All CI checks passed (lint, tests, security scan)
- [ ] GPG-signed commits (verified by GitHub)

---

## Section 4: Code Review Approved

- [ ] Architect or Tech Lead has reviewed and approved the PR
- [ ] No unresolved CRITICAL or HIGH review comments
- [ ] Architecture compliance verified (clean layers, no hardcoding)
- [ ] Security check completed (OWASP Top 10 considered)
- [ ] No hardcoded config, secrets, or prompts

---

## Section 5: Jira ↔ GitHub Linking

- [ ] PR linked to Jira ticket (GitHub development panel shows branch + PR)
- [ ] Smart commit or PR title used to auto-link (includes `PROJ-NNN`)
- [ ] PR merged and branch deleted

---

## Section 6: Environment Release

### Staging
- [ ] Code deployed to staging environment
- [ ] E2E and smoke tests passed on staging
- [ ] QA Lead staging acceptance comment on release ticket

### Production
- [ ] Production promotion triggered by Release Manager (human-only)
- [ ] Post-deploy health checks passed
- [ ] Jira story transitioned to **Done**

---

## Scrum Master Gate

The Scrum Master is the DoD enforcer. Before closing a story:

1. Verify all six sections above
2. Run BDD runner tool with `@PROJ-NNN` — confirm output shows passing tests
3. Confirm PR is merged, branch deleted, Jira linked
4. Confirm code review approval exists
5. Transition Jira ticket to **Done**

If any section is incomplete, the story stays **In Review** with a blocking comment.

---

## Definition of Ready (reminder)

Before a story enters a sprint, the DoR must also be met. See: [story-format.md`](story-format.md#definition-of-ready-dor)
