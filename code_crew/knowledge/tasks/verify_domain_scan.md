---
type: CrewAI Task
title: Verify Domain Scan
description: Check for drift between designs/DMD/ domain model and actual code entities
tags: [verify, domain, drift]
agent: architect
expected_output: >
  List of FINDING [DOMAIN] or PASS [DOMAIN] lines for each drift check.
  Ends with DOMAIN SCAN COMPLETE.
---

You are performing a domain model drift check. Compare `designs/DMD/` against actual code.

**Step 1 — Load the domain model.**
Use `knowledge_reader` to load all files matching `DMD/*.md`. If no DMD files exist, output:
```
PASS [DOMAIN]: No domain model defined — skip drift check
DOMAIN SCAN COMPLETE
```

**Step 2 — Extract code entities.**
Scan the source code (use `directory_read` starting from the project root). Collect:
- All struct/class/type names in `domain/`, `model/`, `entity/`, `aggregate/` directories
- All event types (ending in `Event`, `Created`, `Updated`, `Deleted`)
- All value object types

**Step 3 — Compare against DMD.**
For each aggregate in DMD:
- Does a corresponding struct/class exist in code? If missing → `FINDING [DOMAIN]`
- Does the aggregate name match exactly (case-sensitive)? If different → `FINDING [DOMAIN]`

For each domain event in DMD:
- Does a corresponding event type exist in code? If missing → `FINDING [DOMAIN]`

For each bounded context in DMD:
- Does a corresponding package/module/directory exist? If missing → `FINDING [DOMAIN]`

**Step 4 — Check for undocumented entities.**
For each significant code entity (aggregate-shaped struct) NOT in DMD → `FINDING [DOMAIN]: <Entity> exists in code but not in domain model`

**Step 5 — Handle tool failures.**
If any tool call fails: log `ERROR: <tool>(<args>) → <error>`, try once with an alternative, then skip. Never use absolute paths in shell commands. Include a `TOOL FAILURES:` block before the final line if any step was skipped.

**Step 6 — Output.**

For each finding:
```
FINDING [DOMAIN]: <AggregateName> defined in DMD but not found in code at <expected path>
FINDING [DOMAIN]: <EventName> defined in DMD but <ActualName> found in code — name drift
PASS [DOMAIN]: <context> — all aggregates and events accounted for
```

End with:
```
DOMAIN SCAN COMPLETE
```
