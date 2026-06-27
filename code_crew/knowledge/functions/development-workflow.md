---
name: SDLC-Engineer-DevelopmentWorkflow
description: Daily development workflow, environment setup, GPG signing, secrets handling, AI pair programming with GSD, and workstation hygiene
metadata:
  type: process
  role: engineer
  phase: "14, 15, 17, 18"
---

# Developer Environment & Workflow

---

## Provisioning (New Developer)

Before writing any code, complete provisioning with DevOps Lead:

1. **GitHub access** scoped to the repositories you need — no blanket org access
2. **GPG key** generated, registered in GitHub, and configured for signed commits
3. **AWS access** via IAM role (no long-lived access keys; use SSO or instance profile)
4. **Secrets access** — relevant AWS Secrets Manager paths only
5. **MFA enabled** on GitHub, AWS, and all SaaS tools
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

# Export public key → add to GitHub
gpg --armor --export <KEY-ID>
```

---

## Pre-Commit Hooks

Install via `pre-commit`:

```bash
pip install pre-commit
pre-commit install
```

Hooks enforced:
- Secret scanning (detect-secrets)
- Go lint (`golangci-lint`)
- TypeScript type check (`tsc --noEmit`)
- Terraform format (`terraform fmt`)
- Markdown lint

Hooks run on every `git commit`. CI also runs them — don't bypass with `--no-verify`.

---

## Daily Workflow

```
1. Pull latest from main
   git pull --rebase origin main

2. Rebase feature branch
   git rebase origin/main

3. Write tests first (BDD scenario or unit test)

4. Implement feature/fix

5. Run tests locally
   go test ./...  (backend)
   npm test       (portal)

6. Commit with required format:
   feat(auth-svc): add email verification [REQ:TR-2026-042] PROJ-92

7. Push + open/update PR
```

---

## Branch Naming

```
feature/PROJ-NNN-short-slug
fix/PROJ-NNN-slug
chore/PROJ-NNN-slug
```

See: [branching-strategy.md`](branching-strategy.md) for full rules.

---

## AI Pair Programming (Claude Code / Cursor)

GSD orchestrates AI pair programming for implementation phases 14–19.

**How to use:**
```bash
# In the platform monorepo root
/gsd:execute   # AI executes the current phase task
/gsd:quick     # Proportional mode for small changes (skip heavy phases)
```

GSD reads `.planning/` artifacts (DEFINITION-OF-DONE.md, codebase context, sprint goal) and injects them into the agent context.

**AI pair programming rules:**
- Human reviews all AI-generated code before committing
- Security-sensitive logic (auth, crypto, data handling) requires explicit human review — don't merge AI output without reading it
- Architect reviews AI-generated architecture suggestions before adopting
- No AI-generated secrets or credentials — ever
- AI-generated Terraform is reviewed via `terraform plan` before apply

---

## Secrets Handling

- Secrets live in **AWS Secrets Manager** or **AWS SSM Parameter Store**
- Local development: use `aws sso login` + SDK credential chain (never hardcode)
- `.env` files: config only (URLs, feature flags, non-sensitive defaults) — never real secrets
- `.env` files are in `.gitignore` — pre-commit hook catches accidental commits
- If you discover a secret in the codebase: rotate it immediately, then clean the git history

---

## Isolated Local Execution

- Use Docker or local virtual environments to avoid dependency pollution
- AI coding agents run in the repo directory — never give them write access outside the repo
- Terraform operations run from `infra/` only — no applying outside the standard workflow

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

