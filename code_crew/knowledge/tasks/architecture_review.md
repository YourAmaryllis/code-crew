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

Review the user story and proposed implementation approach (from the sprint input) for
architectural alignment, update the relevant documents, and produce a gate decision.

**Step 1 — Load relevant knowledge**

Use the `knowledge_reader` tool to load:
- The `ADR` and `ADD` index documents to identify all relevant records
- Specific ADR/ADD documents that apply to the technical surface area of this story
- For each ADD: check its `stacks` frontmatter field, then load each named stack document via `knowledge_reader` (e.g. if `stacks: [go-backend, terraform-aws]`, load both). This tells you which conventions govern that component.

**Step 2 — Assess alignment**

For each relevant ADR and ADD, state whether the proposed approach is:

- **ALIGNED**: implementation follows the decision as documented
- **DEVIATION**: implementation diverges — describe exactly how, and whether it is
  justified. If justified, a doc update or new ADR must be filed.
- **NEW-DECISION-NEEDED**: the story introduces a cross-cutting technical choice that
  has not been documented — proceed to Step 3 before deciding.

**Step 3 — Resolve NEW-DECISION-NEEDED items**

For each NEW-DECISION-NEEDED item:

1. Search `ADR/` and `ADD/` for any existing document that covers a similar decision.
   - If a similar document exists: reference it. Is the current choice aligned, or a
     deliberate deviation? Mark accordingly and note what doc update (if any) is needed.
   - If no similar document exists (genuinely novel decision): **do not decide alone**.
     Escalate to the Chief Architect via Step 5.

**Step 4 — Update documentation**

Before issuing APPROVED TO PROCEED:

- For any DEVIATION that is justified: write or update the ADR. Mark Status: Accepted.
- For any NEW-DECISION-NEEDED that was resolved (similar ADR/ADD found): note the
  reference in a Jira comment; no new doc required unless the approach deviates.
- If the decision changes component structure, data flow, or security posture:
  update the relevant SAD section (Decomposition, Network, Data Flow, Deployment, or Security View).
- If implementation detail changed for an existing component: update the corresponding ADD.

**Step 5 — Chief Architect consultation (genuinely novel decisions only)**

If one or more NEW-DECISION-NEEDED items have no similar ADR/ADD precedent, the Chief
Architect must weigh in before the flow proceeds. Output the following block — this
pauses the flow and prompts the Chief Architect for a decision:

```
CHIEF_ARCHITECT_CONSULTATION_REQUIRED

## Decision Point
<One sentence: what cross-cutting decision must be made?>

## Option 1: <Name>
**Pros:** <concise pros — 1-3 bullet points or a short sentence>
**Cons:** <concise cons>

## Option 2: <Name>
**Pros:** <concise pros>
**Cons:** <concise cons>

[## Option 3: <Name>  ← include if genuinely distinct third path exists]
[**Pros:** ...]
[**Cons:** ...]

## Architect Recommendation
<Optionally state which option you recommend and the key reason. Omit if no clear preference.>
```

When the Chief Architect's response arrives as human feedback:
- If a numbered option was selected: document the chosen approach in a new ADR
  (Status: Accepted), update the relevant SAD section, and create or update the ADD
  for the affected component.
- If the Chief Architect provided free-text guidance: incorporate it, choose the
  appropriate option or derive a new approach, and document it as above.
- Then re-run this review from Step 1 to confirm alignment before producing APPROVED TO PROCEED.

**Step 6 — Final gate**

Only after all documentation is up to date:

- **APPROVED TO PROCEED**: all surfaces aligned, deviations resolved, docs updated
- **BLOCKED**: deviation or decision requires doc work that cannot be resolved now —
  list exactly what is needed and who must act

Do not approve if any HIGH-impact deviation is unresolved or any novel decision is
undocumented.

**Completion signal — required.**
End your output with exactly one of:
- `TASK COMPLETE` — you have produced the full output and the gate decision above.
- `CHIEF_ARCHITECT_CONSULTATION_REQUIRED` — followed by the structured block from Step 5.
- `INCOMPLETE: <reason>` — you could not finish. Describe what is blocking you.

Do NOT end with a planning statement or partial summary.
