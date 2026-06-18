---
type: CrewAI Task
title: Definition of Done Check
description: Gate task — verify all six DoD sections pass before a work item can close
tags: [dod, quality-gate, scrum, closure]
timestamp: 2026-06-17T00:00:00Z
agent: scrum_master
context_agents:
  - tech_lead
  - qa_engineer
  - backend_developer
  - frontend_developer
  - security_reviewer
expected_output: >
  A DoD Compliance Report in markdown with: overall verdict (PASS or FAIL),
  per-section status (PASS/FAIL) with specific evidence for each of the six DoD sections,
  a list of blockers if FAIL, and recommended next steps. No ticket may be marked Done
  unless the verdict is PASS.
---

Load the current Definition of Done using the `dod_checker` tool. Do not use a remembered
or cached version — always read the live file from `platform/.planning/DEFINITION-OF-DONE.md`.

Using the outputs from all other agents in this sprint (tech lead's architecture review,
QA engineer's BDD feature files, backend and frontend implementation outputs, security
reviewer's findings), evaluate the completed work item against every section of the DoD:

**Section 1 — Jira issue completeness**
Confirm the Jira issue (key provided in the sprint input) contains:
- Context (why we are doing this)
- Requirements (functional and non-functional)
- Acceptance criteria (testable bullets or checklist)
- Design references (links to `designs/` ADD or ADR)
- Design/implementation parity (the cited ADD describes what actually shipped; if the
  implementation diverged, an updated ADD or tracked doc-debt ticket must exist)

**Section 2 — Tests and traceability**
Use the `bdd_runner` tool to actually run the BDD scenarios tagged with the Jira key
(e.g. `tags="@LOOPLAT-92"`). Include the runner output verbatim in this report as evidence.
"Scenarios were specified" is NOT sufficient — tests must be implemented and pass.

Confirm:
- BDD scenarios exist, are annotated with the Jira issue key and category tags, and cover 100% of ACs
- `bdd_runner` output shows all scenarios PASSING (attach output as evidence)
- A human has verified (or is scheduled to verify) acceptance scenarios — mark pending if not yet done
- A test report summary is available for Jira comment

**Section 3 — Pull request format**
Confirm:
- One primary PR per story
- PR title includes Jira key and REQ ID (e.g., `feat(portal): … [REQ:DATA-02] LOOPLAT-72`)
- PR description links the Jira issue and design docs

**Section 4 — Jira ↔ GitHub linking**
Confirm:
- Branch name includes the Jira key
- Commits include the Jira key (smart-commit format)
- PR is linked in the Jira development panel (or flag for admin to verify)

**Section 5 — Closure criteria**
All of sections 1–4 must pass. State explicitly whether the ticket may be moved to Done.

**Section 6 — Environment release**
If this work completes a GSD phase: confirm staging has been promoted or flag it as required.
Production promotion is human-triggered only — mark as pending human action if applicable.

Produce the DoD Compliance Report with one clear section per DoD section, PASS or FAIL,
and specific evidence (or "evidence not available — requires human confirmation" where
you cannot verify programmatically). End with the overall verdict.
