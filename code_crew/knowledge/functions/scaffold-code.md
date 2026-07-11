---
type: Function Guide
title: Code Scaffolding
description: How to create directory structure and stub files for a new feature
tags: [scaffold, stubs]
---

## Purpose

Scaffolding creates the *skeleton* — empty files with correct package declarations and function signatures. No implementation logic. It gates the BDD step: stub files must exist before step definitions can reference them.

## Step 1 — Check what already exists

Before creating any file, use `workspace_reader` (`list_dir` or `find_files`) to check if the target path already exists.

- If files already exist: list them as "existing — no change needed" and stop.
- Only create stubs for paths that genuinely do not exist.
- Skip entirely if the story is a bug fix or affects only existing files.

## Step 2 — Determine what to create

From the architecture review output and acceptance criteria, decide:

- New service endpoint? → handler stub + service stub
- New UI component? → component stub + types stub + test stub
- Both? → create both

Load the active stack document(s) for the affected layer (e.g. `go-backend`, `typescript-react`, `python-fastapi`) — the stack document defines the exact directory layout, package declarations, and file naming conventions for each stub type.

## Step 3 — Create stubs

For each stub file, follow the stack document's conventions for:
- Package or module declaration
- File placement relative to the service root
- Empty function signatures named after the domain concept
- Import stubs for interfaces/types the function will depend on (as TODOs if not yet defined)

No implementation logic — stubs only.

## Step 4 — Verify the build

After creating all stubs, run `commands.build` from `.code-crew/structure.md` in the appropriate service directory. If the build fails, report the error and stop — do not continue with stubs that break the build.

## Output format

List every path and its status:

```
<service>/<layer>/<feature>.go    — created
<service>/<layer>/<feature>_test.go  — created
<service>/<layer>/<feature>.go    — existing, no change
commands.build                    — PASS
```
