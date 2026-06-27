---
name: SDLC-Team-GitHubConventions
description: Branch naming, commit message format, PR format, Jira-GitHub linking, and merge discipline
metadata:
  type: process
  role: all
  phase: "17, 18, 19"
---

# GitHub Conventions

These conventions are enforced in code review. PRs that don't follow them are rejected.

---

## Branch Naming

```
feature/PROJ-NNN-short-slug
fix/PROJ-NNN-short-slug
chore/PROJ-NNN-short-slug
hotfix/PROJ-NNN-short-slug
```

Rules:
- Lowercase, hyphen-separated — no underscores or spaces
- Must include the Jira ticket key
- Slug: 2–5 words (not the full ticket title)

Examples:
```
feature/PROJ-92-email-verification
fix/PROJ-95-null-profile-pointer
chore/PROJ-101-go-1-23-upgrade
hotfix/PROJ-110-auth-bypass-fix
```

---

## Commit Message Format

```
<type>(<scope>): <description> [REQ:<REQ-ID>] <JIRA-KEY>
```

| Field | Required | Values / Notes |
|-------|----------|---------------|
| `type` | Yes | `feat`, `fix`, `test`, `chore`, `docs`, `refactor`, `perf`, `ci` |
| `scope` | Yes | Package or service name: `portal`, `auth-svc`, `curation-svc`, `infra` |
| `description` | Yes | Imperative mood, lowercase, no period, ≤ 72 chars |
| `[REQ:<ID>]` | When available | References TR-YYYY-NNN or BR-YYYY-NNN requirement |
| `<JIRA-KEY>` | Yes | `PROJ-NNN` |

Multi-line commits:
```
feat(auth-svc): add email verification on registration [REQ:TR-2026-042] PROJ-92

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
feat(auth-svc): add email verification on registration [REQ:TR-2026-042] PROJ-92
```

**Description template**:

```markdown
## Summary
Brief description of what this PR does and why.

## Jira
[PROJ-92](https://your-org.atlassian.net/browse/PROJ-92)

## Design References
- ADD-025-Email-Verification-Flow
- Figma: https://figma.com/... (if applicable)

## Test Evidence
- BDD run: [GitHub Actions #XXXXXXX](https://github.com/...)
- All 4 scenarios passing ✅

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

## Jira ↔ GitHub Linking

Automatic linking via:
1. **PR title** containing `PROJ-NNN` — Jira shows GitHub PR in development panel
2. **Smart commits**: `PROJ-92 #comment Tests passing` — adds Jira comment
3. **Branch name** containing `PROJ-NNN` — Jira shows branch in development panel

Setup required (one-time per repo):
- GitHub App: Atlassian Jira GitHub integration installed on the repo
- Jira project: Development panel enabled in project settings

---

## Signed Commits

All commits must be GPG-signed. The repo pre-receive hook rejects unsigned commits.

Verified by GitHub with the green "Verified" badge on the commit.

See: [development-workflow.md`](development-workflow.md) for GPG setup.

---

## Protected Branches

| Branch | Protection |
|--------|-----------|
| `main` | Require PR, require status checks, no direct push, require signed commits |
| `hotfix/*` | Created from main, short-lived |

No long-running branches other than `main`. All other branches are feature/fix branches deleted after merge.
