---
type: CrewAI Task
title: Architecture Verification Scan
description: Architect performs layer dependency check; SAD drift and ADR coverage are pre-computed by Python and merged automatically
tags: [verify, architecture, scan, sad, add]
agent: architect
expected_output: >
  Structured list of architecture findings tagged [ARCH], each prefixed with FINDING, PASS, or INFO.
  Ends with ARCH SCAN COMPLETE.
---

Perform an architecture layer dependency check. SAD drift and ADR coverage are already
pre-computed and will be merged into the final report — you do not need to check those.

**CRITICAL: All paths must be relative to `.`. Never use absolute paths.**

---

**Step 1 — Output component list from structure.md (no tool calls).**

Your context includes `## Project structure` with `## Architectural components`. Output one
INFO line per component:
```
INFO [ARCH]: Component identified — <name> (<directory>)
```

---

**Step 2 — Layer dependency check (2 file reads).**

Read `portal/backend/internal/api/handlers.go`. If not found, use `list_directory
portal/backend/internal/api/` and read the first `.go` handler file.

Then read `portal/backend/internal/services/dataset.go`. If not found, use `list_directory
portal/backend/internal/services/` and read the first `.go` service file.

Check:
- Does the handler import from services/ (not the reverse)?
- Is the handler doing routing + service calls (not raw business logic)?

Output exactly one line:
- Correct layering: `PASS [ARCH]: Layer dependency rules met — portal handler calls service, no reverse import`
- Violation: `FINDING [ARCH]: Layer violation — <detail> — <file>`
- Files not found: `INFO [ARCH]: Layer dependency check — files not found, skipped`

---

**Step 3 — End.**

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
