---
type: CrewAI Task
title: Cleanup — Remove Temporary Files and Scripts
description: Engineer removes any temporary scripts, debug helpers, or one-off files created during implementation that should not be committed.
tags: [cleanup, implementation, engineer]
agent: engineer
expected_output: >
  LIST of files removed (one path per line, prefixed REMOVED:), or CLEANUP: nothing to remove
  if no temp files were found. Ends with CLEANUP COMPLETE.
---

Review the working tree for files that were created as implementation aids but should not
be committed. Remove them now, before code review.

**What to look for:**

- Scripts with names like `tmp_`, `temp_`, `scratch_`, `debug_`, `test_`, `fix_`, `patch_`,
  `migrate_once`, `seed_`, `setup_once`, `run_once`, or similar one-off prefixes
- Files in `tmp/`, `scratch/`, `.scratch/`, or `debug/` directories
- Files ending in `.tmp`, `.bak`, `.orig`, `.swp`
- Shell scripts or Python scripts created to run a one-time operation (migration, backfill,
  data fix) that have already been run and are not part of the permanent codebase
- Any file that has a comment like `// TODO: remove`, `# remove after`, `// delete me`,
  or `// temporary`

**What NOT to remove:**

- Migration files that are part of the permanent schema history (e.g. goose, alembic, flyway files)
- Test fixtures or seed data used by the test suite
- Scripts in a `scripts/` directory that are documented and intended to be reusable
- Any file that was present before this implementation began (check `git status` — only
  touch untracked files or files modified as part of this task)

**How to check:**

1. Run `git status` to see all new untracked files and modified files in the working tree
2. For any suspicious untracked file, read the first few lines to determine its purpose
3. Remove files that are clearly temporary (`git rm` for tracked, `rm` for untracked)
4. Do NOT commit — just remove; the next step (release notes) handles the commit

**Output format:**

```
REMOVED: <path>
REMOVED: <path>
...
CLEANUP COMPLETE
```

or if nothing to remove:

```
CLEANUP: nothing to remove
CLEANUP COMPLETE
```
