---
type: CrewAI Task
title: Architecture Verification Scan
description: Architect scans codebase for layer violations, dependency rule breaches, drift from SAD/ADDs, and missing ADRs
tags: [verify, architecture, scan]
agent: architect
expected_output: >
  Structured list of findings tagged [ARCH], each prefixed with FINDING, PASS, or INFO.
  Every checked item — whether clean or not — gets a line. Ends with ARCH SCAN COMPLETE.
---

Scan the codebase for architecture violations. Use `workspace_reader` to inspect source files
and `knowledge_reader` to load architecture guides and design documents.

**Scope:** This is a static code scan only. Do not call `jira_view`, do not check Jira tickets,
and do not validate branch or commit traceability — those are handled by the DoD check.

**CRITICAL: All paths must be relative to the project root (`.`). Never use absolute paths.**

---

**Step 1 — Identify active architecture pattern.**

Check `ARCHITECTURE_STYLE` env. If unset, infer from directory names:
- `ports/` with `driving/` or `driven/` → hexagonal
- `domain/model/` + `application/` → onion
- `usecases/` or (`domain/` + `adapters/`) → clean
- `handlers/` or `controllers/` + `services/` + `repository/` or `storage/` → layered

Load the matching `stacks/arch-<style>.md` guide (clean, hexagonal, onion, or layered).
If the style is unrecognised or the guide is missing, emit one
`FINDING [ARCH]: No active architecture pattern detected` and skip Step 2.

---

**Step 2 — Dependency rule check.**

For each source directory in the project:
- Verify imports flow only inward (inner layers do not import from outer layers)
- Flag any cross-layer import that violates the loaded architecture guide
- Check at most 50 files — prioritise files that contain imports

Output one PASS or FINDING per layer pair checked.

---

**Step 3 — Dead code scan.**

Look for exported functions, types, or constants that have zero references in the codebase.
Flag those in core/domain layers especially (dead domain code is a design signal).

Output one PASS or FINDING per scan result.

---

**Step 4 — ADR coverage.**

Use `knowledge_reader` to load available ADR documents (e.g. `knowledge_reader("ADR")` to list,
then fetch individual ones by stem). Check if any major architectural decisions visible in the
code (choice of HTTP framework, DB driver, auth mechanism, external API client) are undocumented.
The designs directory path is provided in the task context — use it for any direct file operations.

---

**Step 4b — SAD and ADD drift check.**

Load the System Architecture Document (SAD) if one exists in designs/ (look for files named
`SAD*.md` or containing "system architecture" in the title). Load the ADD index from
`designs/ADD/` — read titles to find which components are documented.

For each component documented in the SAD or ADDs:
1. Does the documented structure match what is actually in the code?
   - Documented: "attestation service handles health attestations via REST handlers in `internal/handlers/`"
   - Actual: check that `internal/handlers/` exists and contains the expected files
2. Are documented data flows reflected in the code? (e.g. if the ADD says "calls the access DB
   service", verify there is a client or call in the code)
3. Are documented tech choices still in use? (e.g. if ADD says "uses PostgreSQL", verify no
   SQLite or other DB driver has crept in)

If no SAD exists: `INFO [ARCH]: No SAD found in designs/ — system-level architecture undocumented`.
If an ADD documents a component but the code directory is missing or empty: `FINDING [ARCH]`.
If code has a major service with no corresponding ADD: `FINDING [ARCH]: Service <name> has no ADD`.

Read at most 4 ADD documents and 1 SAD document — focus on the most critical components.

---

**Step 5 — Handle tool failures.**

If any tool call fails (directory not found, file missing, shell command errors):
- Log it: `ERROR: <tool>(<args>) → <error>` — do not retry the same call more than once.
- Try an alternative: `list_dir` on the parent, `find_files` before `read_file`, or drop the step.
- **Never use absolute paths** in shell commands — use paths relative to the project root (cwd).
- If `designs/` is unavailable, emit `INFO [ARCH]: designs directory not found — ADR/ADD/SAD coverage check skipped` and continue.
- Collect all failures and include them in a `TOOL FAILURES:` block before the final line.

---

**Step 6 — Format findings.**

Every check that was performed — whether it passed or failed — must appear in the output.
Do not omit checks that passed.

```
FINDING [ARCH]: <one-sentence description> — <file:line if applicable>
PASS [ARCH]: <what was checked and found clean>
INFO [ARCH]: <contextual note — not a violation, but worth noting>
```

End your output with exactly:
```
ARCH SCAN COMPLETE
```
