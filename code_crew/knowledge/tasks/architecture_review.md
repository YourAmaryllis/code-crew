---
type: CrewAI Task
title: Architecture Review
description: Review the ticket for architectural alignment, update ADR/ADD/SAD, and consult the Chief Architect on genuinely novel decisions before handing off to QA and engineering
tags: [architecture, adr, add, sad, review, chief-architect, phase-13]
timestamp: 2026-06-17T00:00:00Z
agent: tech_lead
context_agents:
  - scrum_master
expected_output: >
  An architecture alignment report listing: relevant ADRs and ADDs for this story,
  alignment status (ALIGNED / DEVIATION / NEW-DECISION-NEEDED) for each, a record of any
  ADR/ADD/SAD updates made, and a final gate (APPROVED TO PROCEED, BLOCKED,
  or CHIEF_ARCHITECT_CONSULTATION_REQUIRED).
---

Review the user story and proposed implementation approach for architectural alignment, update the relevant documents, and produce a gate decision.

**Step 1 — Load relevant knowledge.**
Load the issue tracker ticket (use the issue tracker tool) to identify the technical surface area (e.g. "backend validation", "frontend form", "DB schema", "IAM policy"). Then:
- Check the **service decomposition diagram** already in the context above (if present) — it shows the service topology and which components connect to each other. Use it to quickly identify which service(s) this story touches before loading any documents.
- Load the ADR and ADD **index** documents — read titles only to find which records apply; do not load every document
- Load only the specific ADR/ADD documents that govern the component(s) this story touches
- For each loaded ADD: check its `stacks` frontmatter field and load only the named stack document(s) relevant to this story's surface area

**Step 2 — Assess alignment.**
For each relevant ADR and ADD, state whether the proposed approach is:
- **ALIGNED**: implementation follows the decision as documented
- **DEVIATION**: implementation diverges — describe how, and whether justified. If justified, a doc update or new ADR must be filed.
- **NEW-DECISION-NEEDED**: the story introduces a cross-cutting technical choice not yet documented — proceed to Step 3 before deciding

**Step 3 — Resolve NEW-DECISION-NEEDED items.**
For each NEW-DECISION-NEEDED item:
1. Search ADR/ and ADD/ for any existing document covering a similar decision
   - If similar document exists: reference it; determine if aligned or a deliberate deviation; note required doc update
   - If no similar document exists (genuinely novel): **do not decide alone** — escalate to Chief Architect via Step 5

**Step 4 — Update documentation.**
Before issuing APPROVED TO PROCEED:
- For justified DEVIATIONs: write or update the ADR (Status: Accepted)
- For resolved NEW-DECISION-NEEDED items with existing precedent: note the reference in the issue tracker; no new doc unless approach diverges
- If the decision changes component structure, data flow, or security posture: update the relevant SAD section
- If implementation detail changed for an existing component: update the corresponding ADD

**Step 5 — Chief Architect consultation (genuinely novel decisions only).**
If any NEW-DECISION-NEEDED item has no similar ADR/ADD precedent, output:

```
CHIEF_ARCHITECT_CONSULTATION_REQUIRED

## Decision Point
<One sentence: what cross-cutting decision must be made?>

## Option 1: <Name>
**Pros:** <concise pros>
**Cons:** <concise cons>

## Option 2: <Name>
**Pros:** <concise pros>
**Cons:** <concise cons>

## Architect Recommendation
<Optional: which option and key reason>
```

When the Chief Architect responds: document the chosen approach in a new ADR, update the SAD and ADD, then re-run this review from Step 1 before issuing APPROVED TO PROCEED.

**Step 5b — Update structure.md.**
After updating docs, check whether this issue introduces structure not yet in `.code-crew/structure.md` (new component, new test suite, new command, new code layer). Make the smallest correct addition using `platform_shell` — do not rewrite the whole file.

**Step 6 — Final gate.**
- **APPROVED TO PROCEED**: all surfaces aligned, deviations resolved, docs updated
- **BLOCKED**: unresolved deviation or undocumented decision — list exactly what is needed and who must act

**Completion signal — required.**
End with exactly one of:
- `TASK COMPLETE`
- `CHIEF_ARCHITECT_CONSULTATION_REQUIRED` followed by the structured block from Step 5
- `INCOMPLETE: <reason>`
