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

Use `workspace_reader` to read `designs/SAD/SAD-3-Decomposition-View.md`, focusing on
section 3.2 (Element Catalog table).

For each SAD component in the Element Catalog:
1. Does the corresponding code directory exist? (use list_directory on the project root)
2. Does the component's documented purpose match what the `## Architectural components`
   section in structure.md describes?

For each code component NOT in the SAD: flag as INFO (may be newer than the SAD).
For each SAD component with no code directory: flag as FINDING.
For each mismatch between SAD description and actual code purpose: flag as FINDING.

If no SAD exists:
```
INFO [ARCH]: No SAD found in designs/ — SAD drift check skipped
```

Read at most **1 SAD file**. Do not read ADD files in this step.

---

**Step 3 — Layer dependency check (one component only).**

Pick the most critical deployable service from Step 1 (prefer the one with the most
complex layering, e.g. a service with handlers + services + models).

For that one component:
1. List its internal directory structure
2. Read **1 handler file** and **1 service file**
3. Check that:
   - Handlers import services (not the other way)
   - Services do not import from handlers
   - No business logic visible in the handler (parsing + service call only)

Report the component name and what you checked. Output one PASS or FINDING line.

If you already read enough from Step 2 to assess this: use that, don't re-read.

---

**Step 4 — ADR coverage check (index only).**

Use `knowledge_reader` to list available ADR documents. Do **not** read individual ADRs —
only check what titles exist.

Look for ADR coverage of these key decisions (visible from prior steps):
- HTTP framework choice (e.g. gin, echo, gorilla/mux)
- Database driver or ORM
- Auth mechanism (JWT, mTLS, Auth0)
- Primary cloud provider and deployment target (ECS, Lambda)

For each decision visible in the code that has no matching ADR title: flag as FINDING.
For each that is covered: flag as PASS.

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
