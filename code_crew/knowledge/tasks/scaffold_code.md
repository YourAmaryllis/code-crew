---
name: scaffold_code
description: Create the directory structure and code stubs for the user story
expected_output: Manifest of created files and directories with their purpose
---

Load the issue tracker ticket (use the issue tracker tool) first and identify which stack(s) this story touches. Then load only what that requires with `knowledge_reader`:
- **`scaffold-code`** — scaffolding process and stub format (always load)
- The relevant stack guide(s) for this story — identified from the ticket, the ADD, or the `stacks:` list in `.code-crew/structure.md`

Also use `workspace_reader` to read `.code-crew/structure.md`. The `## Project commands` section has the exact build command for this project — use it to verify scaffolded code compiles, rather than assuming any particular tool.

**FIRST — check what already exists.**
Use `code_index search` to find similar existing code patterns before touching the filesystem — it is faster than listing directories and surfaces the best template to scaffold from:
- `code_index search "<feature> handler service"` → find the nearest existing equivalent
- `code_index search "directory layout <service>"` → understand where files should live

Then confirm the exact target path does not already exist with `workspace_reader list_dir`.

- If the feature's directories and files already exist: output a manifest listing them as "existing — no change needed", then STOP. Do NOT overwrite or recreate existing code.
- Only create stubs for paths that genuinely do not exist yet.
- Skip scaffolding entirely if the story is a bug fix, a config change, or affects only existing files.

Using the acceptance criteria and story context:

1. Determine whether this story requires: a new service, a new feature within an existing service, a new UI component, or a combination.

2. If the architect's review (from context) recommended a specific service name, module name, or structural pattern — follow it exactly.

3. Use the platform_shell tool to create any required directories and stub files that do not exist. Stubs must have:
   - Correct package/module declarations (follow the language conventions in the active stack document)
   - Empty function signatures named after the domain concept from the story
   - No implemented logic — stubs only
   - Import statements for the interfaces/types they will depend on (as TODOs if not yet defined)

4. **After writing any source files**, run the project's build command (`commands.build` from `.code-crew/structure.md`) in the appropriate module directory. If the build fails, report the error in the manifest and do NOT continue.

Output a manifest listing each path and its status: "created", "existing — no change", or "build error: <message>". Include a note on which parts the backend engineer should implement first.

**On tool failure** — log the error, try once with an alternative (list parent dir, use `find_files` before `read_file`), then skip and continue. Never use absolute paths in shell commands. Include unresolved failures in the output manifest.

**Completion signal — required.**
End your output with exactly one of:
- `TASK COMPLETE` — you have produced the full output described above.
- `INCOMPLETE: <reason>` — you could not finish (missing data, tool failure, ambiguity). Describe what is blocking you so a human can resolve it.

Do NOT end with a planning statement or partial summary.
