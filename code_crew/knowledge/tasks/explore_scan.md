---
type: CrewAI Task
title: Project Exploration Scan
description: Architect reads the project tree and key files to assess architecture pattern, summarise project purpose, and describe service components for the OTM threat model
tags: [explore, architecture, project-scan]
agent: architect
expected_output: >
  ARCHITECTURE_STYLE: <clean|hexagonal|onion|layered|undetected>
  PROJECT_SUMMARY: <1-2 sentence description of what this project does>
  COMPONENT: <dir_name>: <one-sentence description>
  ...one COMPONENT line per service directory...
  EXPLORE SCAN COMPLETE
---

You are performing a project exploration scan. The project tree and Phase 1 detection results are provided in your context. Your goal is to produce three outputs that a pure file-scan cannot reliably determine:

1. The architecture pattern
2. A plain-English summary of what the project does
3. Descriptions of each service/component directory

**Step 1 — Read README and entrypoints.**
Use `workspace_reader` to try reading (in order, stop when found):
- `README.md` or `README.rst` at root
- `docs/README.md`
- The main entrypoint file: `main.go`, `cmd/*/main.go` (first match), `main.py`, `app.py`, `server.py`, `index.ts`, `index.js`

Read at most 3 files. If none exist, proceed with the tree only.

**Step 2 — Architecture assessment.**
Consider the directory tree in your context. Look for:
- Hexagonal (Ports & Adapters): explicit separation of `ports/` (or `driving/`/`driven/`) from domain logic; adapters directory; no business logic in transport layer
- Clean Architecture: `usecases/` or `use_cases/` directory with business rules isolated from frameworks; `entities/`, `adapters/`
- Onion: concentric rings — `domain/` innermost, then `application/`, then `infrastructure/`; dependencies point inward only
- Layered: `handlers/` or `controllers/` + `services/` + `repository/` or `storage/` — classic three-tier, less strict than the above
- Undetected: none of the above is clearly identifiable

Use `knowledge_reader` to load the matching `stacks/arch-<style>.md` if you identify a style, to confirm your assessment matches the definition.

Output exactly one line:
```
ARCHITECTURE_STYLE: <style>
```

If Phase 1 already detected a style (provided in context) and you agree, output the same value. If you disagree or have higher confidence in a different answer, output your assessment. If genuinely undetected, output `undetected`.

**Step 3 — Project summary.**
From the README / entrypoint / tree, write 1-2 sentences describing what this project does and who uses it. Be specific: name the domain, not just the technology.

Output exactly one line:
```
PROJECT_SUMMARY: <description>
```

**Step 4 — Component descriptions.**
The context lists the candidate service/component directories identified in Phase 1. For each, use `workspace_reader` to skim its README (if any) or the first 30 lines of its main source file. Write one sentence describing what the component does.

Output one line per component:
```
COMPONENT: <dir_name>: <description>
```

If a directory is a shared library or utility (not a deployable service), note that: `COMPONENT: pkg: shared utility library — not a deployable service`.

**Step 5 — Output EXPLORE SCAN COMPLETE.**
