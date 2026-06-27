---
type: CrewAI Task
title: Production Smoke Test
description: QA runs a minimal smoke test against production after human-triggered promotion to confirm the deployment is healthy
tags: [qa, production, smoke, post-deploy, phase-22]
agent: qa_lead
expected_output: >
  SMOKE PASSED — production URL, scenarios run, pass count, and confirmation that
  all critical paths are healthy. OR SMOKE FAILED: <reason> if any smoke scenario fails.
---

Run a minimal smoke test against production to confirm the deployment landed cleanly.

This task runs AFTER a human has triggered production promotion via `workflow_dispatch`
(GitHub Actions) or the manual pipeline job (GitLab CI). Do not promote yourself.

**Step 1 — Confirm production URL.**
Use `workspace_reader` to find the production URL in `.env.production`, `README.md`,
Terraform outputs, or ask via `knowledge_reader("environment-management")`.

**Step 2 — Run smoke tests (read-only only).**
Production smoke tests MUST be read-only — no test resets, no data writes.
Run only scenarios tagged `@smoke` and `@readonly`:
```bash
BASE_URL=https://<production-url> go test ./... -v -tags "smoke readonly" 2>&1 | tail -50
```

`TEST_RESET_ENABLED` must be false/unset on production. If the test suite attempts a
reset, fail immediately and report it.

**Step 3 — Evaluate results.**
- All `@smoke @readonly` scenarios pass → `SMOKE PASSED`
- Any scenario fails → `SMOKE FAILED: <scenario name and failure reason>`

Do NOT run write-path scenarios, mutation tests, or any scenario that creates/modifies
production data.

**Step 4 — Report to Release Engineer.**
State the production URL, git SHA deployed, version tag, pass count, and whether any
rollback is recommended.

**Completion signal — mandatory.**
End with exactly:
- `SMOKE PASSED` — production deployment is healthy
- `SMOKE FAILED: <reason>` — production deployment has issues; escalate immediately
