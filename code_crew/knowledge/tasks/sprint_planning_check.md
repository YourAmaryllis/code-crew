---
type: CrewAI Task
title: Sprint Planning Check
description: Verify each story in the sprint input meets the Definition of Ready before work begins
tags: [sprint-planning, dor, scrum, phase-13]
timestamp: 2026-06-17T00:00:00Z
agent: scrum_master
expected_output: >
  A sprint readiness report listing each story with READY or NOT READY status.
  For NOT READY stories, list the specific missing elements. Include a recommended
  action (block, proceed with caveat, or escalate) for each story.
---

You are opening the sprint. For each user story provided in the input, evaluate it
against the **Definition of Ready** from SOP-3-Dev-Process:

1. **Written as a user story**: "As a [who], I want [what], so that [why]"
2. **Acceptance criteria**: clear, testable statements (plain English bullets or checklist — Gherkin belongs in BDD feature files, not in Jira ACs)
3. **Designs** *(optional — use whatever is available)*: Figma URL if linked; or an HTML design explicitly referenced in the Jira description (e.g. "see attached design.html"); or no design at all for small/mechanical changes (e.g. making a field mandatory, renaming a label). Do NOT flag missing Figma as a blocker unless the ticket clearly involves new UI flows or visual design decisions.
4. **Dependencies identified**: no unresolved blockers
5. **Story points estimated**: team has estimated complexity
6. **No known blockers**
7. **Linked to technical requirements**: TR-XXX or BR-XXX linked in Jira

Use the `sop_reader` tool to load SOP-3-Dev-Process if you need to verify the exact
DoR criteria. Do not rely on memory for the criteria wording.

For each story, state READY or NOT READY with the specific missing items. A NOT READY
story must not be pulled into the sprint without explicit Product Owner escalation —
note this clearly in your report.

Also confirm that the sprint has a clear **Sprint Goal** (one sentence describing
what the team will deliver). If no Sprint Goal is provided, flag this as a blocker
before the sprint can start.
