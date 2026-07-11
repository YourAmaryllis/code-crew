---
type: CrewAI Task
title: Project Exploration — Code Structure
description: Discover and document the code layer layout, architectural components (from SAD), and service entry points for all detected stacks.
tags: [explore, code-structure, architecture, entry-points]
agent: architect
expected_output: >
  Three DISCOVERY_BEGIN/END blocks: code_structure, architectural_components, entry_points.
  Ends with STRUCTURE COMPLETE.
---

You are documenting how this codebase is organised. Read actual files — do not guess.

Use `workspace_reader` throughout. **IMPORTANT: Limit tool calls aggressively — read at most
ONE file per service directory. Use `list_directory` to pick the most informative file, then
read only that one. Do not read more than 10 files total across the entire task.**

---

## Step 1 — Code structure discovery

For each detected service stack (from the **Service dirs** in context):

1. Use `workspace_reader` `list_directory` on the service's main source directory
   (`internal/`, `src/`, or equivalent — whichever is listed in the directory tree or context)
2. Note the subdirectory names — these reveal the layer layout
3. Read ONE source file from the most important layer (handler, API, or main entry point)
4. Document the layer layout based on directory names and that single file

Output:
```
DISCOVERY_BEGIN: code_structure
## Code structure

### <stack-name> (<root-directory>/)

**Layer layout**:

| Layer | Directory | Purpose |
|-------|-----------|---------|
| <layer> | `<path>` | <what goes here> |

**Naming conventions**:
- New handler: `<example path>`
- New service: `<example path>`

**Key source file read**: `<file>`

[repeat for each service — maximum 3 services]
DISCOVERY_END: code_structure
```

Focus on the **primary service** (largest or most central). If there are more than 3 services,
document the top 3 by significance and note the rest exist.

---

## Step 2 — Architectural component discovery

1. Use `workspace_reader` to find and read the SAD decomposition view (look in a `designs/` or
   `docs/` directory for a file with "decomposition" or "SAD" in the name). Read the Element
   Catalog table if present.
2. Map SAD component names to code directories.
3. Note any code services not in the SAD, and SAD components with no code directory.

Output:
```
DISCOVERY_BEGIN: architectural_components
## Architectural components

| SAD Component | Code directory | Type | Notes |
|---------------|----------------|------|-------|
| <component> | `<dir>/` | deployable service | |

**In code but not in SAD**:
- `<dir>/` — <description>

**In SAD but not in code**:
- (list if any)
DISCOVERY_END: architectural_components
```

If no SAD exists:
```
DISCOVERY_BEGIN: architectural_components
## Architectural components

No SAD found. Components derived from service dirs in context.

| Component | Directory | Type |
|-----------|-----------|------|
| <name> | `<dir>/` | deployable service |
DISCOVERY_END: architectural_components
```

---

## Step 3 — Entry points

For the primary services only (top 3 by significance), identify the entry point file.
Look for it by name based on the detected stack (`main.go`, `cmd/*/main.go`, `main.py`,
`index.ts`, etc.) — use `find_files` with the expected pattern, not a broad search.

Output:
```
DISCOVERY_BEGIN: entry_points
## Entry points

| Service | Entry point file | Notes |
|---------|-----------------|-------|
| <name> | `<path>` | <key env vars or ports if visible> |
DISCOVERY_END: entry_points
```

---

## On tool failure

Log the error and continue. Skip any service you cannot read. Never block the scan on
a single failure. Stop using tools once you reach the 10-call limit — synthesise from
what you have.

---

## Final step

Output exactly:
```
STRUCTURE COMPLETE
```
