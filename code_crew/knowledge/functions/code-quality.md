---
name: SDLC-Architect-CodeQuality
description: Code review standards, quality gates, and what the architect checks before approving a PR
metadata:
  type: process
  role: architect
  phase: "19"
---

# Code Quality & Review Standards

Code review is a hard gate before merge to trunk. The architect or tech lead reviews every PR. This document defines what is checked and what triggers rejection.

---

## Code Review Checklist

### 1. Architecture Compliance
- [ ] Clean architecture layers respected (no inward dependency violations)
- [ ] Business logic is in use cases, not handlers or repositories
- [ ] New external dependencies are behind interfaces
- [ ] Bounded context boundaries not crossed via shared DB tables
- [ ] If a new service or integration is introduced, a corresponding ADD exists or is referenced

### 2. Hardcoding Check
- [ ] No hardcoded config values (URLs, timeouts, feature flags)
- [ ] No hardcoded secrets or credentials
- [ ] No hardcoded prompt strings or agent instructions (must be external OKF files)
- [ ] No hardcoded infrastructure ARNs or resource names

### 3. Branch, Commit, and PR Format
- [ ] Branch: `feature/JIRA-NNN-short-slug` or `fix/JIRA-NNN-slug`
- [ ] Commits: `<type>(<scope>): <description> [REQ:<ID>] <JIRA-KEY>`
- [ ] PR title matches commit subject format
- [ ] PR description includes Jira link, design references, test report
- [ ] One primary PR per user story

See: [github-conventions.md`](github-conventions.md)

### 4. Error Handling
- [ ] All external I/O errors handled (no silent swallows)
- [ ] Errors wrapped with context (`fmt.Errorf("doing X: %w", err)` in Go)
- [ ] No `panic()` except in truly unrecoverable startup conditions
- [ ] User-facing errors do not leak internal details

### 5. Test Coverage
- [ ] Unit tests exist for all use cases and domain logic
- [ ] BDD scenarios annotated with `@JIRA-KEY` tag
- [ ] All acceptance criteria covered by at least one BDD scenario
- [ ] No test stubs left as TODO

See: [test-coverage.md`](test-coverage.md)

### 6. Security
- [ ] No new secrets in code or config files
- [ ] Authentication/authorization checks present on new endpoints
- [ ] Input validated at system boundary (not trusted internally)
- [ ] No PII logged or returned in error messages
- [ ] OWASP Top 10 considerations checked for web-facing changes

See: [security-privacy.md`](security-privacy.md)

---

## Review Outcomes

**APPROVED** — all checklist items pass; PR is ready to merge.

**CHANGES REQUESTED** — one or more items fail. Each finding is documented as:

```
Severity: CRITICAL | HIGH | MEDIUM | LOW
File: path/to/file.go:line
Description: what is wrong
Fix: what to change
```

| Severity | Meaning | Blocks merge? |
|----------|---------|---------------|
| CRITICAL | Security vulnerability, hardcoded secret, data loss risk | Yes — must fix before merge |
| HIGH | Architecture violation, missing auth, uncaught error on critical path | Yes — must fix |
| MEDIUM | Suboptimal pattern, missing test, naming convention | Yes — must address |
| LOW | Style nit, suggestion | No — can merge with acknowledgement |

---

## AI-Assisted Code Review

The code review task in the AI crew performs an initial review pass covering:
- Architecture compliance
- Hardcoding check
- Branch/commit/PR format
- Error handling patterns
- Overall verdict

The human architect reviews the AI output and the diff before final approval. The AI review is evidence, not a substitute for human judgment.

---

## What Does NOT Block Merge

- Pending documentation updates (if tracked in Jira)
- Refactors outside the PR scope (tracked separately)
- Performance optimizations that require profiling data not yet gathered
