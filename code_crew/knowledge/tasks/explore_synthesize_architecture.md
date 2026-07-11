---
type: CrewAI Task
title: Architecture Synthesis
description: Given component summaries, produce architecture style assessment, component descriptions, and code structure overview. No tools.
tags: [explore, synthesis, architecture]
agent: architect
expected_output: >
  ARCHITECTURE_STYLE line, PROJECT_SUMMARY line, COMPONENT lines, and a
  DISCOVERY_BEGIN/END code_structure block. Ends with ARCHITECTURE COMPLETE.
---

**DO NOT USE ANY TOOLS. All information needed is already in the context above.**

The context contains service summaries (what each service does, its type, entry points)
and the Python-detected architecture hint. Use these to produce structured output.

---

## Step 1 — Architecture style

Based on service subdirectories listed in the summaries, identify the architecture pattern:
- **Hexagonal**: `ports/` + `adapters/` directories present
- **Clean**: `usecases/` or `usecase/` directories present
- **Onion**: `domain/` innermost, `application/`, `infrastructure/` rings
- **Layered**: `handlers/` or `controllers/` + `services/` + `repository/` pattern
- **Undetected**: none of the above is clearly identifiable

Output:
```
ARCHITECTURE_STYLE: <style>
```

---

## Step 2 — Project summary

Write 1-2 sentences describing the overall platform — what it does and who uses it —
based on the service summaries.

Output:
```
PROJECT_SUMMARY: <description>
```

---

## Step 3 — Component descriptions

For each service in the summaries, output one line:
```
COMPONENT: <dir_name>: <one sentence from the PURPOSE field of its summary>
```

---

## Step 4 — Code structure overview

Based on the subdirectory lists in the service summaries, document the layer layout
for the primary services.

Output:
```
DISCOVERY_BEGIN: code_structure
## Code structure

### <service-name>

**Subdirectories**: <list from context>
**Layer pattern**: <what the directory names suggest — handlers/, services/, internal/, etc.>
**Primary language**: <from manifest or entry points in summary>
**Entry points**: <from ENTRY_POINTS field of summary>

[repeat for each deployable service]
DISCOVERY_END: code_structure
```

---

## Step 5

Output exactly:
```
ARCHITECTURE COMPLETE
```
