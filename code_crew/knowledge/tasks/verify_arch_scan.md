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

**Step 2 — ADR coverage check (do this before reading any source files).**

**IMPORTANT: You MUST complete this step and output at least one PASS or FINDING line.**

Use `workspace_reader` with `list_directory` on `designs/ADR/`. Do NOT read individual ADR
files — only check what titles exist in the filenames.

Look for ADR coverage of these decisions:
- HTTP framework (gin, echo, gorilla/mux, chi) → check for ADR with Go/HTTP/framework in name
- Database driver or ORM → check for ADR with postgres/database/ORM in name
- Auth mechanism (JWT, mTLS, Auth0) → check for ADR with auth/mTLS/Auth0 in name
- Cloud deployment target (ECS, Lambda, Kubernetes) → check for ADR with ECS/cloud/deploy in name

For each decision covered: `PASS [ARCH]: ADR covers <decision> — <filename>`
For each decision with no matching ADR: `FINDING [ARCH]: No ADR for <decision>`
If `designs/ADR/` does not exist: `INFO [ARCH]: No ADR directory found — ADR coverage check skipped`

---

**Step 3 — SAD decomposition drift check.**

**IMPORTANT: You MUST complete this step and output at least one PASS or FINDING line.**

Read `designs/SAD/SAD-3-Decomposition-View.md`. Then use `list_directory` on `.` (relative
path) to confirm which directories exist.

For each SAD component in its Element Catalog:
- Directory exists and matches structure.md: `PASS [ARCH]: SAD component <name> present at <directory> — aligned with SAD`
- Directory not found: `FINDING [ARCH]: SAD component missing from code — <component> (<expected directory>)`
- External actors (no expected code directory): `INFO [ARCH]: External actor in SAD — <name> (no code expected)`

For each component in structure.md NOT in the SAD:
- `INFO [ARCH]: Component not in SAD — <name> (may be newer than SAD)`

If SAD file does not exist: `INFO [ARCH]: No SAD found in designs/SAD/ — SAD drift check skipped`

---

**Step 4 — Layer dependency check (one component, 2 file reads).**

**IMPORTANT: You MUST complete this step and output at least one PASS or FINDING line.**

Pick `portal/backend` as the component to check (it has clear handler/service layering).

Read `portal/backend/internal/api/handlers.go` (or the first `.go` file in that directory
if handlers.go does not exist). Then read `portal/backend/internal/services/dataset.go`
(or the first `.go` file in `portal/backend/internal/services/`).

Check:
- Handler imports services (not the reverse)?
- Service file does NOT import from handlers?
- Handler is mostly parsing + service call (not raw business logic)?

Output:
- Correct layering: `PASS [ARCH]: Layer dependency rules met — portal handler calls service, no reverse import`
- Violation: `FINDING [ARCH]: Layer violation — <detail> — <file>`
- If files not found: `INFO [ARCH]: Layer dependency check — files not found, check skipped`

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
