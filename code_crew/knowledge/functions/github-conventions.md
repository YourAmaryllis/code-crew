---
name: SDLC-Team-GitHubConventions
description: Branch naming, commit message format, PR format, issue tracker linking, and merge discipline
metadata:
  type: process
  role: all
  phase: "17, 18, 19"
---

# VCS Conventions

These conventions are enforced in code review. PRs that don't follow them are rejected.

---

## Branch Naming

```
feature/<issue-key>-short-slug
fix/<issue-key>-short-slug
chore/<issue-key>-short-slug
hotfix/<issue-key>-short-slug
```

Rules:
- Lowercase, hyphen-separated — no underscores or spaces
- Must include the issue tracker key
- Slug: 2–5 words (not the full ticket title)

Examples:
```
feature/<issue-key>-email-verification
fix/<issue-key>-null-profile-pointer
chore/<issue-key>-dependency-upgrade
hotfix/<issue-key>-auth-bypass-fix
```

---

## Commit Message Format

```
<type>(<scope>): <description> [REQ:<REQ-ID>] <issue-key>
```

| Field | Required | Values / Notes |
|-------|----------|---------------|
| `type` | Yes | `feat`, `fix`, `test`, `chore`, `docs`, `refactor`, `perf`, `ci` |
| `scope` | Yes | Package or service name (e.g. `auth-svc`, `api`, `infra`) |
| `description` | Yes | Imperative mood, lowercase, no period, ≤ 72 chars |
| `[REQ:<ID>]` | When available | References TR-YYYY-NNN or BR-YYYY-NNN requirement |
| `<issue-key>` | Yes | Issue tracker key |

Multi-line commits:
```
feat(auth-svc): add email verification on registration [REQ:TR-2026-042] <issue-key>

Sends a time-limited verification email after account creation.
Token expires after 24 hours. Account remains pending until verified.
```

**Type meanings:**
- `feat` — new feature or capability
- `fix` — bug fix
- `test` — adding or updating tests only
- `chore` — dependencies, tooling, config (no production code change)
- `docs` — documentation only
- `refactor` — code restructure (no behavior change)
- `perf` — performance improvement
- `ci` — CI/CD pipeline changes

---

## Pull Request Format

**Title**: same format as commit subject

```
feat(auth-svc): add email verification on registration [REQ:TR-2026-042] <issue-key>
```

**Description template**:

```markdown
## Summary
Brief description of what this PR does and why.

## Issue
[<issue-key>](<issue tracker URL>)

## Design References
- ADD-NNN-Feature-Name
- Figma: <url> (if applicable)

## Test Evidence
- BDD run: <CI run URL>
- All N scenarios passing

## Checklist
- [ ] Branch name follows convention
- [ ] Commits follow format
- [ ] BDD scenarios implemented and passing
- [ ] Code review checklist completed by reviewer
```

---

## Merge Strategy

- **Squash merge** into `main` — one squash commit per PR
- Squash commit title = PR title (must follow commit format)
- Delete the feature branch after merge
- No merge commits from `main` into feature branches — use rebase

---

## Issue Tracker ↔ VCS Linking

Automatic linking depends on the configured issue tracker (see `issue_tracker.type` in config):
- **Jira**: PR title / branch name containing the issue key triggers the Jira development panel integration
- **Linear**: PR title or branch name with the Linear issue ID auto-links
- **GitHub Issues**: PR description with `Closes #NNN` closes the issue on merge

For Jira-specific setup: see the `jira` stack document.

---

## Signed Commits

All commits must be GPG-signed. The repo pre-receive hook rejects unsigned commits.

See: [`development-workflow.md`](development-workflow.md) for GPG setup.

---

## Protected Branches

| Branch | Protection |
|--------|-----------|
| `main` | Require PR, require status checks, no direct push, require signed commits |
| `hotfix/*` | Created from main, short-lived |

No long-running branches other than `main`. All other branches are feature/fix branches deleted after merge.
