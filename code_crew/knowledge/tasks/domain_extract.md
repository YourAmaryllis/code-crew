---
type: CrewAI Task
title: Domain Extract
description: Scan existing code to extract the current domain model — aggregates, entities, value objects, events, and bounded context boundaries
tags: [domain, extract, reverse-engineering]
agent: architect
expected_output: >
  Extracted domain model in DMD format from code analysis.
  Files written to designs/DMD/. Ends with DOMAIN EXTRACT COMPLETE.
---

You are reverse-engineering the domain model from existing code. The target path is provided in your task input.

**Step 1 — Scan the codebase.**
Use `directory_read` and `file_read` to explore the target path. Look for:
- Struct/class names that represent business concepts (not infrastructure: no "Handler", "Controller", "Repository", "DB")
- Files in directories named: `domain/`, `model/`, `entity/`, `aggregate/`, `value/`, `event/`
- Interface names ending in `Repository`, `Service`, `Factory`
- Types/structs that embed or reference each other (relationships)
- Event types: structs/classes ending in `Event`, `Created`, `Updated`, `Deleted`, or emitting to channels/queues

**Step 2 — Identify aggregates.**
Group related entities. The aggregate root is usually:
- The struct that methods are called on
- The struct that owns the repository interface
- The struct that emits domain events

**Step 3 — Extract ubiquitous language.**
List every business concept found (aggregate names, event names, value object names). Note inconsistencies — if similar concepts have different names in different packages, flag them as 🔴 hot spots.

**Step 4 — Identify bounded context candidates.**
Look for package/module boundaries, import graphs, or directory separation. Each top-level package with its own domain types is a candidate bounded context.

**Step 5 — Produce Mermaid diagram.**
Produce a classDiagram reflecting what was found in code — not what should be there. Mark gaps with comments (`%% missing: ...`).

**Step 6 — Write output files.**
Use `file_write` to save:
- `designs/DMD/<service>-domain.md` — extracted domain model in same format as domain_synthesis output
- `designs/DMD/<service>-diagram.mmd` — Mermaid diagram of extracted model

**Step 7 — Output.**

```
EXTRACTION TARGET: <path>
AGGREGATES FOUND: <count>
EVENTS FOUND: <count>
HOT SPOTS: <count>
FILES WRITTEN:
  designs/DMD/<service>-domain.md
  designs/DMD/<service>-diagram.mmd

DOMAIN EXTRACT COMPLETE
```
