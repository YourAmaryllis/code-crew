---
name: SDLC-Engineer-DevelopmentWorkflow
description: Daily development workflow, environment setup, GPG signing, secrets handling, and workstation hygiene
metadata:
  type: process
  role: engineer
  phase: "14, 15, 17, 18"
---

# Developer Environment & Workflow

---

## Provisioning (New Developer)

Before writing any code, complete provisioning with DevOps Lead:

1. **VCS access** scoped to the repositories you need — no blanket org access
2. **GPG key** generated, registered in the VCS provider, and configured for signed commits
3. **Cloud access** via IAM role (no long-lived access keys; use SSO or instance profile)
4. **Secrets access** — relevant secret store paths only
5. **MFA enabled** on VCS, cloud, and all SaaS tools
6. **Workstation compliance** — full-disk encryption, auto-lock (5 min), OS patches current
7. **Pre-commit hooks** installed (see below)

DevOps Lead maintains the access log. Access review is quarterly.

---

## Signed Commits (Required)

All commits must be GPG-signed. The repo rejects unsigned commits.

```bash
# Generate key
gpg --full-generate-key

# List keys
gpg --list-secret-keys --keyid-format LONG

# Configure git
git config --global user.signingkey <KEY-ID>
git config --global commit.gpgsign true

# Export public key → add to VCS provider
gpg --armor --export <KEY-ID>
```

---

## Pre-Commit Hooks

Install using the project's hook manager (see `.code-crew/structure.md` for the tool and config file):

Hooks typically enforced:
- Secret scanning
- Language linting (exact tool is in the active stack document)
- Type checking (for statically typed languages)
- Infrastructure format checks
- Markdown lint

Hooks run on every `git commit`. CI also runs them — don't bypass with `--no-verify`.

---

## Daily Workflow

```
1. Pull latest from the default branch
   git pull --rebase origin <default-branch>

2. Rebase feature branch
   git rebase origin/<default-branch>

3. Write tests first (BDD scenario or unit test)

4. Implement feature/fix

5. Run tests locally
   Use commands.test from .code-crew/structure.md

6. Commit with required format:
   feat(<scope>): <description> [REQ:<REQ-ID>] <issue-key>

7. Push + open/update PR
```

---

## Branch Naming

```
feature/<issue-key>-short-slug
fix/<issue-key>-slug
chore/<issue-key>-slug
```

See [`branching-strategy.md`](branching-strategy.md) for full rules.

---

## AI Pair Programming

AI coding agents assist with implementation. Use the crew's REPL to run implementation phases.

**AI pair programming rules:**
- Human reviews all AI-generated code before committing
- Security-sensitive logic (auth, crypto, data handling) requires explicit human review — don't merge AI output without reading it
- Architect reviews AI-generated architecture suggestions before adopting
- No AI-generated secrets or credentials — ever
- AI-generated infrastructure is reviewed via a plan/preview command before apply

---

## Secrets Handling

- Secrets live in the project's secret store (see `environment-management` function for the configured provider)
- Local development: use credential chain from the cloud provider CLI (never hardcode)
- `.env` files: config only (URLs, feature flags, non-sensitive defaults) — never real secrets
- `.env` files are in `.gitignore` — pre-commit hook catches accidental commits
- If you discover a secret in the codebase: rotate it immediately, then clean the git history

---

## Isolated Local Execution

- Use containers or local virtual environments to avoid dependency pollution
- AI coding agents run in the repo directory — never give them write access outside the repo
- Infrastructure operations run from the designated infra directory only — no applying outside the standard workflow

---

## Workstation Hygiene

| Requirement | Standard |
|-------------|---------|
| Disk encryption | FileVault (macOS) / BitLocker (Windows) / LUKS (Linux) |
| Screen lock | Auto-lock after 5 minutes of inactivity |
| OS patches | Applied within 7 days of release |
| Password manager | Required for all credentials |
| VPN | Required for any on-premises resource access |

Report lost or compromised devices to the Security Lead immediately.
