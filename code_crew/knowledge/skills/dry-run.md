---
type: skill
name: dry-run
description: Preview mode — plan without executing; show what would run instead of running it
---

## Execution rules — dry-run mode

You are in dry-run mode. Do not execute. Show what would happen.

**Shell commands (`platform_shell`):**
- Do NOT run any command
- Instead output: `WOULD RUN: <command>`
- One `WOULD RUN:` line per command, in the order they would execute

**File writes:**
- Do NOT write any file to disk
- Instead output the full file content in a fenced code block with the target path as the title:
  ```
  # Would write: path/to/file.ext
  <file content>
  ```

**Git operations:**
- Do NOT commit, push, branch, or merge
- Output: `WOULD GIT: <git command>`

**External API calls (Figma, Jira, Linear):**
- Read-only calls (GET) are allowed — you may fetch data to inform the plan
- Write/mutate calls (POST, PUT, PATCH): output `WOULD CALL: <tool> <args>` instead

**Output format:**
End your output with a summary section:
```
DRY RUN SUMMARY
  Files that would be written: <count>
  Commands that would run:     <count>
  Git operations:              <count>
  Estimated impact:            <brief description>
```

**Purpose:** This mode is for previewing what a crew run would do before committing. It is safe to run at any time without side effects.
