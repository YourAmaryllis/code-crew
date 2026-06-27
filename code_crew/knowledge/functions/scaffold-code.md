---
type: Function Guide
title: Code Scaffolding
description: How to create directory structure and stub files for a new feature
tags: [scaffold, go, typescript, stubs]
---

## Purpose

Scaffolding creates the *skeleton* — empty files with correct package declarations and function signatures. No implementation logic. It gates the BDD step: stub files must exist before step definitions can reference them.

## Step 1 — Check what already exists

Before creating any file, use `workspace_reader` (`list_dir` or `find_files`) to check if the target path already exists.

- If files already exist: list them as "existing — no change needed" and stop.
- Only create stubs for paths that genuinely do not exist.
- Skip entirely if the story is a bug fix or affects only existing files.

## Step 2 — Determine what to create

From the arch review output and acceptance criteria, decide:

- New service endpoint? → handler stub + service stub
- New React component? → component stub + types stub + test stub
- Both? → create both

## Go backend stubs (portal/backend)

Read `go-backend` stack guide for the module layout. Then create:

``` text
internal/api/<feature>.go               — handler stub
internal/api/<feature>_test.go          — handler test stub
internal/ard/<feature>.go               — service stub
internal/ard/<feature>_test.go          — service test stub
```

Stub format:

```go
package api  // or ard

// <FeatureName> handles <brief description>.
func <FeatureName>(w http.ResponseWriter, r *http.Request) {
    // TODO: implement
}
```

After creating Go files, run `go build ./...` in `portal/backend/`. If the build fails, report the error and stop.

## TypeScript / React stubs (portal/frontend)

Read `typescript-react` stack guide for the component layout. Then create:

``` text
src/components/<Component>/index.tsx    — component stub
src/components/<Component>/types.ts    — prop types
src/components/<Component>/<Component>.test.tsx  — test stub
```

Component stub:

```tsx
import React from 'react';
import { <Props> } from './types';

// Figma: <link from story> | Story: <JIRA-KEY>
export const <Component>: React.FC<<Props>> = () => {
  // TODO: implement
  return null;
};
```

## Output format

List every path and its status:

```
portal/backend/internal/api/data_dictionary_mandatory.go    — created
portal/backend/internal/ard/data_dictionary_mandatory.go    — created
portal/backend/internal/api/data_dictionary_mandatory.go    — existing, no change
go build ./...                                               — PASS
```
