---
name: scaffold_code
description: Create the directory structure and code stubs for the user story
expected_output: Manifest of created files and directories with their purpose
---

Load the scaffolding guide and stack conventions with `knowledge_reader`:
- **`scaffold-code`** — scaffolding process and stub format
- **`go-backend`** and/or **`typescript-react`** — exact directory layout and stub format for the relevant stack(s)

If the project has a `.code-crew/stacks/` directory, those files override the built-in stack guides.

**FIRST — check what already exists.**
Before creating any file, use workspace_reader (list_dir or read_file) to check if the target path already exists.

- If the feature's directories and files already exist: output a manifest listing them as "existing — no change needed", then STOP. Do NOT overwrite or recreate existing code.
- Only create stubs for paths that genuinely do not exist yet.
- Skip scaffolding entirely if the story is a bug fix, a config change, or affects only existing files.

Using the acceptance criteria and story context:

1. Determine whether this story requires: a new service, a new feature within an existing service, a new UI component, or a combination.

2. If the architect's review (from context) recommended a specific service name, module name, or structural pattern — follow it exactly.

3. Use the platform_shell tool to create any required directories and stub files that do not exist. Stubs must have:
   - Correct package declarations (Go) / module exports (TypeScript) / class definitions (Python)
   - Empty function signatures named after the domain concept from the story
   - No implemented logic — stubs only
   - Import statements for the interfaces/types they will depend on (as TODOs if not yet defined)

4. **After writing any Go files**, run `go build ./...` in the module directory (e.g. `portal/backend`). If the build fails, report the error in the manifest and do NOT continue.

Output a manifest listing each path and its status: "created", "existing — no change", or "build error: <message>". Include a note on which parts the backend engineer should implement first.

**Completion signal — required.**
End your output with exactly one of:
- `TASK COMPLETE` — you have produced the full output described above.
- `INCOMPLETE: <reason>` — you could not finish (missing data, tool failure, ambiguity). Describe what is blocking you so a human can resolve it.

Do NOT end with a planning statement or partial summary.
