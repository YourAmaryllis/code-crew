---
type: CrewAI Task
title: Release Notes
description: Release Engineer writes the changelog contribution and GitHub Release entry for the completed story
tags: [release, changelog, semver, release-notes, phase-20]
timestamp: 2026-06-21T00:00:00Z
agent: release_engineer
context_agents:
  - scrum_master
  - architect
expected_output: >
  Version impact verdict (PATCH/MINOR/MAJOR with reason), CHANGELOG.md entry written to
  the [Unreleased] section, GitHub Release draft entry, migration requirements (explicit
  None or specific steps), and known issues for the Release Manager.
---

Write the release note contribution for the story that just passed DoD.

**Step 1 — Load conventions.** Use `knowledge_reader` to load:
- `release-notes` — changelog format and per-story contribution rules
- `versioning` — version bump decision tree and migration guide conventions

**Step 2 — Read the Jira story** (`jira_view`).
Understand what changed from the user's perspective. Read description, ACs, and any
linked requirements. You are writing for customers, not engineers.

**Step 3 — Read the git log** (`platform_shell`).
```bash
git log --oneline <last-tag>..HEAD  # or --since="<last release date>"
```
Filter for commits related to this Jira key. Note any DB migration files, API contract
changes, or dependency updates — these affect the version bump decision.

**Step 4 — Read current CHANGELOG.md** (`workspace_reader`).
Find the `[Unreleased]` section. Understand what other stories have already contributed
so your entry fits the right sections.

**Step 5 — Determine version impact.**
Apply the decision tree from the `versioning` guide:
- Any removed/renamed field in the public API or a breaking DB migration → MAJOR (0.x: MINOR)
- New feature, new endpoint, new optional field → MINOR
- Bug fix, security fix, internal improvement only → PATCH

State your decision and the specific reason (e.g. "MINOR — adds new validation to
existing endpoint, no removed fields, no breaking migration").

**Step 6 — Write the CHANGELOG.md entry.**
Add one or more lines under the correct section(s) in the `[Unreleased]` block:

```markdown
### Added
- <user-visible description> (<JIRA-KEY>)

### Fixed
- <user-visible fix description> (<JIRA-KEY>)

### Security
- <security improvement> (<JIRA-KEY>)
```

Write the entry to CHANGELOG.md using `platform_shell`.
If CHANGELOG.md does not have an `[Unreleased]` section, create one at the top.

**Step 7 — Write the GitHub Release draft entry.**
1–3 sentences in plain English. What did the customer gain? Is any action required from
them? Include a migration note if applicable.

**Step 8 — Flag migration requirements.**
Inspect git log for migration files (`migrations/`, `*.sql`, `*_migration*`). If any
exist for this story:
- Describe what the migration does
- State whether it is safe to apply before or after the deploy (or requires downtime)
- Flag as MIGRATION REQUIRED in your output

If none: state "No migration required."

**Completion signal — mandatory.**
End with exactly one of:
- `RELEASE NOTE COMPLETE` — CHANGELOG.md updated, all sections filled
- `INCOMPLETE: <reason>` — could not complete (e.g. no git access, no CHANGELOG.md)

Do NOT end with a planning statement.
