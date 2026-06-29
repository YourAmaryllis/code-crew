---
type: CrewAI Task
title: Verify Domain Scan
description: Check for drift between designs/DMD/ domain model and actual code entities; flag when no domain model exists
tags: [verify, domain, drift, ubiquitous-language]
agent: architect
expected_output: >
  List of FINDING [DOMAIN], PASS [DOMAIN], or INFO [DOMAIN] lines for each drift check.
  Every check performed appears in the output. Ends with DOMAIN SCAN COMPLETE.
---

You are performing a domain model completeness and drift check.

**CRITICAL: All paths must be relative to the project root (`.`). Never use absolute paths.**

---

**Step 1 — Check for formal domain model.**

Use `knowledge_reader` to load all files matching `DMD/*.md`.

If **no DMD files exist**, do not silently pass — instead:

```
INFO [DOMAIN]: No formal domain model (DMD) found in designs/DMD/
```

Then proceed to Step 1b to check for implicit domain concepts before concluding.

If DMD files exist, proceed to Step 2.

---

**Step 1b — Implicit domain model check (runs when no DMD exists).**

Even without a formal DMD, the code may have implicit domain structure worth surfacing.

1. Look for domain-shaped code:
   - Directories named `domain/`, `model/`, `entity/`, `aggregate/`, `value_object/`
   - Struct or class names ending in common DDD terms: `Aggregate`, `Entity`, `Event`, `Repository`,
     `Service`, `ValueObject`, `Command`, `Query`
   - Use `find_files` and read 2-3 source files to check

2. Look for ubiquitous language:
   - Is there a glossary or ubiquitous language document in `designs/`?
   - Do code names (types, functions, endpoints) use consistent domain terminology?
   - Read the README and 1-2 ADD documents to identify the primary domain concepts

Output:

If domain-shaped code or ubiquitous language exists but no DMD:
```
FINDING [DOMAIN]: Implicit domain model exists in code (e.g. <Entity1>, <Entity2>) but no DMD
  documents it — consider formalising with a domain model document [MEDIUM]
INFO [DOMAIN]: No ubiquitous language glossary found in designs/
```

If no domain-shaped code at all:
```
INFO [DOMAIN]: No domain model layer and no formal DMD — domain modelling not established
INFO [DOMAIN]: Consider whether DDD is appropriate for this project's complexity
```

Then output `DOMAIN SCAN COMPLETE` and stop.

---

**Step 2 — Extract code entities (when DMD exists).**

Scan the source code (use `workspace_reader` starting from the project root). Collect:
- All struct/class/type names in `domain/`, `model/`, `entity/`, `aggregate/` directories
- All event types (ending in `Event`, `Created`, `Updated`, `Deleted`)
- All value object types

---

**Step 3 — Compare against DMD.**

For each aggregate in DMD:
- Does a corresponding struct/class exist in code? If missing → `FINDING [DOMAIN]`
- Does the aggregate name match exactly (case-sensitive)? If different → `FINDING [DOMAIN]`

For each domain event in DMD:
- Does a corresponding event type exist in code? If missing → `FINDING [DOMAIN]`

For each bounded context in DMD:
- Does a corresponding package/module/directory exist? If missing → `FINDING [DOMAIN]`

---

**Step 4 — Check for undocumented entities.**

For each significant code entity (aggregate-shaped struct) NOT in DMD:
```
FINDING [DOMAIN]: <Entity> exists in code but not in domain model
```

---

**Step 5 — Handle tool failures.**

If any tool call fails: log `ERROR: <tool>(<args>) → <error>`, try once with an alternative,
then skip. Never use absolute paths in shell commands. Include a `TOOL FAILURES:` block before
the final line if any step was skipped.

---

**Step 6 — Output.**

Every check that was performed — whether it passed or failed — must appear in the output.
Do not omit checks that passed.

```
FINDING [DOMAIN]: <AggregateName> defined in DMD but not found in code at <expected path>
FINDING [DOMAIN]: <EventName> defined in DMD but <ActualName> found in code — name drift
PASS [DOMAIN]: <context> — all aggregates and events accounted for
INFO [DOMAIN]: <contextual note — not a violation, but worth noting>
```

End with:
```
DOMAIN SCAN COMPLETE
```
