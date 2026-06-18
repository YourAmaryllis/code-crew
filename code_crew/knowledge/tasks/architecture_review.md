---
type: CrewAI Task
title: Architecture Review
description: Verify the implementation plan aligns with relevant ADRs and ADDs before coding starts
tags: [architecture, adr, add, review, phase-13]
timestamp: 2026-06-17T00:00:00Z
agent: tech_lead
context_agents:
  - scrum_master
expected_output: >
  An architecture alignment report listing: relevant ADRs and ADDs for this story,
  alignment status (ALIGNED / DEVIATION / NEW-DECISION-NEEDED) for each, any required
  doc updates or new ADR/ADD to file, and a final gate (APPROVED TO PROCEED or BLOCKED).
---

Review the user story and proposed implementation approach (from the sprint input) for
architectural alignment.

Step 1: Identify every ADR and ADD in `designs/` that is relevant to the technical
surface area of this story. Use the `sop_reader` tool to load `designs/ADD/ADD.md`
and `designs/ADR/ADR.md` index files to find candidates. Load the specific documents
you need.

Step 2: For each relevant document, state whether the proposed approach:
- **ALIGNED**: implementation follows the decision as documented
- **DEVIATION**: implementation diverges — describe exactly how, and whether it is
  justified. If justified, a doc update or new ADR must be filed as a subtask.
- **NEW-DECISION-NEEDED**: the story introduces a cross-cutting technical choice that
  has not been documented — an ADR or ADD must be filed before implementation.

Step 3: Check that the implementation plan:
- References the Jira key and REQ ID in the proposed branch name and commit format
- Touches only the correct subtree (path-filtered CI per ADR-024)
- Does not introduce a cross-service API contract change without a corresponding ADD update

Step 4: Produce the final gate decision:
- **APPROVED TO PROCEED**: all surfaces aligned, no new decisions needed
- **BLOCKED**: deviation or new decision requires doc work first — list what is needed

Do not approve to proceed if any HIGH-impact deviation is unresolved.
