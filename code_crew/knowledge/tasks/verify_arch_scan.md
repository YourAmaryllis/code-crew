---
type: CrewAI Task
title: Architecture Verification Scan
description: Architect reports pre-computed SAD/ADR facts and does one targeted layer dependency check
tags: [verify, architecture, scan, sad, add]
agent: architect
expected_output: >
  Structured list of findings tagged [ARCH], each prefixed with FINDING, PASS, or INFO.
  Every checked item — whether clean or not — gets a line. Ends with ARCH SCAN COMPLETE.
---

Scan the codebase for architecture violations. Use `workspace_reader` when needed.

**CRITICAL: All paths must be relative to `.`. Never use absolute paths.**
**CRITICAL: Steps 1, 2, and 3 use pre-computed facts from your context — do NOT read files
for those steps. Report the pre-computed results directly as PASS/FINDING/INFO lines.**

---

**Step 1 — Report component list from structure.md (no tool calls).**

Your context includes `## Project structure` with `## Architectural components`. List each
component as:
```
INFO [ARCH]: Component identified — <name> (<directory>)
```

---

**Step 2 — Report SAD drift results (no tool calls).**

Your context includes `## Pre-computed architecture facts` → `### SAD decomposition drift`.
For each entry:

- `EXISTS`: `PASS [ARCH]: SAD component <name> present at <directory> — aligned with SAD`
- `MISSING`: `FINDING [ARCH]: SAD component missing from code — <name> (directory not found)`
- `EXTERNAL ACTOR`: `INFO [ARCH]: External actor in SAD — <name> (no code directory expected)`
- `directory mapping unknown`: `INFO [ARCH]: SAD component directory unmapped — <name>`
- "SAD drift check skipped": `INFO [ARCH]: No SAD found — SAD drift check skipped`

---

**Step 3 — Report ADR coverage results (no tool calls).**

Your context includes `### ADR coverage`. For each entry:

- `COVERED`: `PASS [ARCH]: ADR covers <decision> — <filenames>`
- `NOT COVERED`: `FINDING [ARCH]: No ADR for <decision>`
- "ADR coverage check skipped": `INFO [ARCH]: No ADR directory found — ADR coverage check skipped`

---

**Step 4 — Layer dependency check (2 file reads only).**

Read `portal/backend/internal/api/handlers.go`. If that exact file does not exist, use
`list_directory portal/backend/internal/api/` to find the first `.go` handler file and read it.

Then read `portal/backend/internal/services/dataset.go`. If that exact file does not exist,
use `list_directory portal/backend/internal/services/` and read the first `.go` file.

Check from what you read:
- Does the handler import from services? (no reverse: service importing from handlers?)
- Is the handler file mostly routing + service calls (not raw business logic)?

Output exactly one line:
- Correct: `PASS [ARCH]: Layer dependency rules met — portal handler calls service, no reverse import`
- Violation: `FINDING [ARCH]: Layer violation — <detail> — <file>`
- Files not found: `INFO [ARCH]: Layer dependency check — files not found, skipped`

---

**Step 5 — End.**

Output format:
```
FINDING [ARCH]: <one-sentence description> — <file if applicable>
PASS [ARCH]: <what was checked and found clean>
INFO [ARCH]: <contextual note — not a violation>
```

End with exactly:
```
ARCH SCAN COMPLETE
```
