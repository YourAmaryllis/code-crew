---
type: CrewAI Task
title: Architecture Verification Scan
description: Architect checks code against SAD decomposition, verifies layer rules, and flags ADR gaps — in focused steps to stay within tool limits
tags: [verify, architecture, scan, sad, add]
agent: architect
expected_output: >
  Structured list of findings tagged [ARCH], each prefixed with FINDING, PASS, or INFO.
  Every checked item — whether clean or not — gets a line. Ends with ARCH SCAN COMPLETE.
---

Scan the codebase for architecture violations. Use `workspace_reader` throughout.

**CRITICAL: All paths must be relative to the project root (`.`). Never use absolute paths.**
**SCOPE LIMIT: At most 10 file reads total. Choose the most informative files.**

---

**Step 1 — Identify architectural components from structure.md.**

Your task context includes `## Architectural components` from `.code-crew/structure.md`. This
table maps SAD components to code directories. Use it as the authoritative component list.

If the structure context does not have an `## Architectural components` section, use the `##
Components` section as fallback, or list top-level service directories yourself.

Output one INFO line per component found:
```
INFO [ARCH]: Component identified — <name> (<directory>)
```

---

**Step 2 — SAD decomposition drift check.**

**IMPORTANT: You MUST complete this step and output at least one PASS or FINDING line.**

Use `workspace_reader` to read `designs/SAD/SAD-3-Decomposition-View.md`, focusing on
section 3.2 (Element Catalog table). Then use `list_directory` on `.` (the project root,
relative path) to confirm which component directories exist.

For each SAD component in the Element Catalog, check if its code directory exists:
- Directory exists and purpose matches structure.md: `PASS [ARCH]: SAD component <name> present at <directory> — aligned with SAD`
- Directory exists but purpose seems mismatched: `FINDING [ARCH]: SAD drift — <component> purpose mismatch — <file>`
- Directory not found: `FINDING [ARCH]: SAD component missing from code — <component> (<expected directory>)`

For each component in structure.md NOT in the SAD:
- `INFO [ARCH]: Component not in SAD — <name> (may be newer than SAD)`

If no SAD file exists at `designs/SAD/SAD-3-Decomposition-View.md`:
```
INFO [ARCH]: No SAD found in designs/SAD/ — SAD drift check skipped
```

---

**Step 3 — Layer dependency check (one component only).**

**IMPORTANT: You MUST complete this step and output at least one PASS or FINDING line.**

Pick the most critical deployable service from Step 1 (prefer one with handlers + services
+ models layers). For that one component:
1. List its `internal/` directory structure (1 tool call)
2. Read **1 handler file** and **1 service file** (2 tool calls)
3. Check:
   - Handlers import services (not the reverse)
   - Services do not import from handlers
   - Handler contains parsing + service call, not raw business logic

Output format:
- Correct layering: `PASS [ARCH]: Layer dependency rules met — <component> handler calls service, no reverse import`
- Violation found: `FINDING [ARCH]: Layer violation — <detail> — <file>`

If you cannot read the files (too many reads used in Step 2): output
`INFO [ARCH]: Layer dependency check skipped — file read budget exhausted`

---

**Step 4 — ADR coverage check (index only).**

**IMPORTANT: You MUST complete this step and output at least one PASS or FINDING line.**

Use `workspace_reader` with `list_directory` on `designs/ADR/`. Do **not** read individual
ADRs — only check what titles exist in the filenames.

Look for ADR coverage of these decisions (visible from prior steps):
- HTTP framework choice (e.g. gin, echo, gorilla/mux)
- Database driver or ORM
- Auth mechanism (JWT, mTLS, Auth0)
- Cloud deployment target (ECS, Lambda, Kubernetes)

For each decision visible in the code with no matching ADR title: `FINDING [ARCH]: No ADR for <decision>`
For each that is covered: `PASS [ARCH]: ADR covers <decision>`
If `designs/ADR/` does not exist: `INFO [ARCH]: No ADR directory found — ADR coverage check skipped`

---

**Step 5 — Handle tool failures.**

If any tool call fails: log `ERROR: <tool>(<args>) → <error>`, try once with an alternative.
Never use absolute paths. If `designs/` is unavailable, emit one INFO line and continue.
Collect failures in a `TOOL FAILURES:` block before the final line.

---

**Step 6 — Format findings.**

Every check performed — whether it passed or failed — must appear in the output.

```
FINDING [ARCH]: <one-sentence description> — <file:line if applicable>
PASS [ARCH]: <what was checked and found clean>
INFO [ARCH]: <contextual note — not a violation>
```

End with exactly:
```
ARCH SCAN COMPLETE
```
