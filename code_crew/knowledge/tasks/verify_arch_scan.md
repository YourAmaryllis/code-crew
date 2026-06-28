---
type: CrewAI Task
title: Architecture Verification Scan
description: Architect scans codebase for layer violations, dependency rule breaches, and missing ADRs
tags: [verify, architecture, scan]
agent: architect
expected_output: >
  Structured list of findings tagged [ARCH], each prefixed with FINDING, PASS, or INFO.
  Ends with ARCH SCAN COMPLETE.
---

Scan the codebase for architecture violations. Use `workspace_reader` to inspect source files and `knowledge_reader` to load the active architecture guide (`stacks/arch-clean.md`, `stacks/arch-hexagonal.md`, `stacks/arch-onion.md`, or `stacks/arch-layered.md` — determined by `ARCHITECTURE_STYLE` env or detected from project structure).

**Scope:** This is a static code scan only. Do not call `jira_view`, do not check Jira tickets, and do not validate branch or commit traceability — those are handled by the DoD check in the code crew flow.

**Step 1 — Identify active architecture pattern.**
Check `ARCHITECTURE_STYLE` env. If unset, infer from directory names:
- `ports/` with `driving/` or `driven/` → hexagonal
- `domain/model/` + `application/` → onion
- `usecases/` or (`domain/` + `adapters/`) → clean
- `handlers/` or `controllers/` + `services/` + `repository/` or `storage/` → layered

Load the matching `stacks/arch-<style>.md` guide (clean, hexagonal, onion, or layered). If the style is unrecognised or the guide is missing, emit one `FINDING [ARCH]: No active architecture pattern detected` and skip Steps 2–3.

**Step 2 — Dependency rule check.**
For each source directory in the project:
- Verify imports flow only inward (inner layers do not import from outer layers)
- Flag any cross-layer import that violates the loaded architecture guide
- Check at most 50 files — prioritise files that contain imports

**Step 3 — Dead code scan.**
Look for exported functions, types, or constants that have zero references in the codebase. Flag those in core/domain layers especially (dead domain code is a design signal).

**Step 4 — ADR coverage.**
Use `knowledge_reader` to load available ADR documents (e.g. `knowledge_reader("ADR")` to list, then fetch individual ones by stem). Check if any major architectural decisions visible in the code (choice of HTTP framework, DB driver, auth mechanism, external API client) are undocumented. The designs directory path is provided in the task context — use it for any direct file operations.

**Step 5 — Handle tool failures.**

If any tool call fails (directory not found, file missing, shell command errors):
- Log it: `ERROR: <tool>(<args>) → <error>` — do not retry the same call more than once.
- Try an alternative: `list_dir` on the parent, `find_files` before `read_file`, or drop the step.
- **Never use absolute paths** in shell commands — use paths relative to the project root (cwd).
- If `designs/` is unavailable, emit `INFO [ARCH]: designs directory not found — ADR coverage check skipped` and continue.
- Collect all failures and include them in a `TOOL FAILURES:` block before the final line.

**Step 6 — Format findings.**

Use this exact format for each finding:
```
FINDING [ARCH]: <one-sentence description> — <file:line if applicable>
```

Use this for items that are confirmed clean:
```
PASS [ARCH]: <what was checked and found clean>
```

End your output with exactly:
```
ARCH SCAN COMPLETE
```
