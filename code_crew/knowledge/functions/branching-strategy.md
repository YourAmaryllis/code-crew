---
name: SDLC-Architect-BranchingStrategy
description: Trunk-based development, branch lifecycle, merge discipline, and signed commit requirements
metadata:
  type: process
  role: architect
  phase: "13, 17, 18, 19"
---

# Branching Strategy

This project uses **trunk-based development**. The `main` branch is always deployable. Engineers work on short-lived feature branches that merge within the sprint.

---

## Trunk Rules

- `main` is the integration trunk — always in a releasable state
- No long-running feature branches
- Feature branches live for the duration of one user story (≤ sprint)
- Branches are rebased frequently against `main` — no stale branches
- Direct pushes to `main` are prohibited; all changes go through PR

---

## Branch Naming

```
feature/<issue-key>-short-slug
fix/<issue-key>-short-slug
chore/<issue-key>-short-slug
hotfix/<issue-key>-short-slug
```

Rules:
- Lowercase with hyphens — no underscores, no spaces
- Must include the issue tracker key
- Slug: 2–5 words describing the work (not the ticket title verbatim)

Examples:
```
feature/<issue-key>-add-mandatory-email-field
fix/<issue-key>-null-pointer-on-empty-profile
chore/<issue-key>-dependency-upgrade
```

---

## Commit Message Format

```
<type>(<scope>): <description> [REQ:<REQ-ID>] <JIRA-KEY>
```

| Field | Required | Values |
|-------|----------|--------|
| `type` | Yes | `feat`, `fix`, `test`, `chore`, `docs`, `refactor`, `perf`, `ci` |
| `scope` | Yes | affected service/package (e.g. `auth-svc`, `api`, `infra`) |
| `description` | Yes | imperative, lowercase, ≤ 72 chars |
| `[REQ:<REQ-ID>]` | When tracing to a requirement | TR-YYYY-NNN or BR-YYYY-NNN |
| `<issue-key>` | Yes | issue tracker key |

Examples:
```
feat(auth-svc): add mandatory email verification on registration [REQ:TR-2026-042] <issue-key>
fix(api): null pointer when profile field empty <issue-key>
test(auth-svc): add BDD scenarios for email verification <issue-key>
chore(infra): upgrade dependencies <issue-key>
```

Multi-line commits: first line is the subject; blank line; body for rationale.

---

## Signed Commits

All commits must be GPG-signed. Unsigned commits are rejected by the repository pre-receive hook.

Setup:
```bash
git config --global commit.gpgsign true
git config --global user.signingkey <YOUR-KEY-ID>
```

See: [development-workflow.md`](development-workflow.md) for full GPG setup instructions.

---

## Pull Request Requirements

- Title matches the commit subject format (type, scope, description, issue key)
- Description must include:
  - Issue tracker ticket link
  - Referenced design docs (ADD/ADR numbers)
  - BDD test report or CI run URL
- One primary PR per user story
- PR must be linked to the issue tracker ticket (via the configured issue tracker integration)
- All CI checks must pass before review

---

## Cross-Repo Pull Requests

When a story touches multiple repositories (platform repo + `designs/` submodule, or a shared library), each PR must reference the others.

**Required in every PR description when multiple repos are involved:**

```markdown
## Related PRs
- platform: https://github.com/org/platform/pull/NNN
- designs:  https://github.com/org/designs/pull/NNN
```

Rules:
- All linked PRs must be open before any is merged
- Reviewers must inspect all linked PRs together — partial review is not sufficient
- Merge order: `designs/` changes first, then application code (so the submodule reference stays valid)
- All linked PRs must pass CI before any is merged
- Update the submodule pointer commit in the platform PR after the designs PR merges

---

## Merge Strategy

- **Squash merge** for feature branches — keeps trunk history clean
- The squash commit message must follow the commit format above
- Delete the feature branch after merge

---

## Rebase Discipline

- Rebase feature branch on `main` at least daily
- Resolve conflicts locally — do not create merge commits from `main` into the feature branch
- `git pull --rebase` is the default pull strategy for all developers

---

## Hotfixes

1. Branch from `main`: `hotfix/PROJ-NNN-slug`
2. Fix + test
3. PR to `main` — expedited review (same checklist, no shortcuts)
4. After merge to `main`, cherry-pick to any active release branches if needed

Production deploy follows normal promotion process — no direct prod pushes.
See: [release-process.md`](release-process.md)
