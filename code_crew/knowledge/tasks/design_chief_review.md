---
type: CrewAI Task
title: Chief Architect Review Gate
description: Architect presents the complete design to the Chief Architect and blocks until approval or feedback is received
tags: [design, architecture, review, approval, human-gate]
agent: architect
expected_output: >
  Exactly one of:
  DESIGN APPROVED
  — Chief Architect has approved; design finalization can proceed.
  
  DESIGN NEEDS REVISION: <verbatim feedback from Chief Architect>
  — Feedback must be incorporated before re-presenting.
---

Compile the complete design into a concise review summary and present it to the Chief Architect for approval.

**Step 1 — Compile the design summary.**

From your context (requirements analysis, ADD draft, security addendum, compliance addendum), produce a structured summary:

```
## Design review: <ISSUE-KEY>

### What is being built
<1–2 sentences>

### Architectural decisions
<bullet list of key decisions: components, data flows, tech choices>

### Security controls
<bullet list from security addendum>

### Compliance requirements
<bullet list from compliance addendum>

### Open questions / deferred items
<anything not resolved in the design>
```

**Step 2 — Ask the Chief Architect.**

Call `ask_human` with the full summary above as the question text, appending:

```
Please type APPROVED to proceed with commit/push/PR, or provide feedback
for the team to incorporate before re-presenting.
```

The Chief Architect will type either:
- `APPROVED` (case-insensitive) — proceed to finalization
- Any other text — that text is their feedback for the next revision

**Step 3 — Output the result.**

Read the Chief Architect's response:

- If it contains "APPROVED" (case-insensitive): output exactly:
  ```
  DESIGN APPROVED
  ```

- Otherwise: output exactly:
  ```
  DESIGN NEEDS REVISION: <Chief Architect's response verbatim>
  ```

Do not add commentary, interpretation, or additional text.
