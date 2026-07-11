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

From `.code-crew/structure.md` `## Code structure`, identify:
- The HTTP handler or controller file for the primary service (the file that receives requests and delegates to a service layer)
- The service or domain logic file for that same service (the file that implements business logic)

If structure.md does not name specific files, use `code_index search "handler controller request response"` to find the handler file, and `code_index search "service domain business logic"` to find the service file. Read the first relevant file from each search.

Check:
- Does the handler import from the service layer (not the reverse)?
- Is the handler doing routing + service delegation (not raw business logic)?

Output exactly one line:
- Correct layering: `PASS [ARCH]: Layer dependency rules met — handler delegates to service layer, no reverse import`
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
