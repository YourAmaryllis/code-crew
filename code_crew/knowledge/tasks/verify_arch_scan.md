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

Scan the codebase for architecture violations. Use `workspace_reader` to inspect source files and `knowledge_reader` to load the active architecture guide (`stacks/arch-clean.md`, `stacks/arch-hexagonal.md`, or `stacks/arch-onion.md` — determined by `ARCHITECTURE_STYLE` env or detected from project structure).

**Step 1 — Identify active architecture pattern.**
Check `ARCHITECTURE_STYLE` env. If unset, infer from directory names (`ports/` → hexagonal, `domain/model/` + `application/` → onion, `usecases/` or `domain/` + `adapters/` → clean). Load the matching `stacks/arch-*.md` guide.

**Step 2 — Dependency rule check.**
For each source directory in the project:
- Verify imports flow only inward (inner layers do not import from outer layers)
- Flag any cross-layer import that violates the loaded architecture guide
- Check at most 50 files — prioritise files that contain imports

**Step 3 — Dead code scan.**
Look for exported functions, types, or constants that have zero references in the codebase. Flag those in core/domain layers especially (dead domain code is a design signal).

**Step 4 — ADR coverage.**
Use `knowledge_reader` to load `designs/ADR/` index. Check if any major architectural decisions visible in the code (choice of HTTP framework, DB driver, auth mechanism, external API client) are undocumented. Flag decisions with no matching ADR.

**Step 5 — Format findings.**

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
