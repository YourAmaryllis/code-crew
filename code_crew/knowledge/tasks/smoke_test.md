---
type: CrewAI Task
title: Production Smoke Test
description: QA triggers a minimal smoke test against production and returns a run handle for async polling
tags: [qa, production, smoke, post-deploy, phase-22]
agent: qa_lead
expected_output: >
  RUN_HANDLE: {"type": "gh_actions", "run_id": <id>, "workflow": "<file>", "repo": "<owner/repo>"}
  on the last line when the smoke suite is triggered asynchronously, OR
  SMOKE PASSED — production URL, scenarios run, pass count, and confirmation that
  all critical paths are healthy, if the suite completes inline.
  SMOKE FAILED: <reason> if any smoke scenario fails inline.
---

Run a minimal smoke test against production to confirm the deployment landed cleanly.

This task runs AFTER a human has triggered production promotion via `workflow_dispatch`
(GitHub Actions) or the manual pipeline job (GitLab CI). Do not promote yourself.

**Step 1 — Confirm production URL.**
Use `workspace_reader` to find the production URL in `.env.production`, `README.md`,
Terraform outputs, or ask via `knowledge_reader("environment-management")`.

**Step 2 — Trigger the smoke suite (fire-and-return preferred).**

Use `async_job` to start the smoke test in the background. Choose the type that fits:

**Option A — GHA workflow** (if `production-smoke.yml` or similar exists):
```
async_job(operation="start", type="gh_actions",
          params={"workflow": "production-smoke.yml", "ref": "<release-tag>",
                  "inputs": {"base_url": "<production-url>"}})
```

**Option B — Direct shell** (run smoke suite locally):
```
async_job(operation="start", type="shell",
          params={"command": "<commands.production_smoke or bdd runner> --tags @smoke @readonly",
                  "label": "production smoke", "cwd": "<project root>"})
```

Then emit a `RUN_HANDLE:` line (see Step 3) and stop — do NOT wait for completion.

**Option B — Inline:** If there is no CI workflow for production smoke, run directly.
Production smoke tests MUST be read-only — no test resets, no data writes. Run only
scenarios tagged `@smoke` and `@readonly`.
- If `commands.production_smoke` is set in `.code-crew/structure.md`: run with `BASE_URL=<production-url>` prepended
- Otherwise use `async_job(operation="start", type="shell", params={"command": "<commands.production_smoke> --tags @smoke @readonly", "label": "production smoke"})` — do NOT use `bdd_runner` directly for long-running suites

`TEST_RESET_ENABLED` must be false/unset on production. If the suite attempts a reset, fail immediately.

For inline runs: all pass → `SMOKE PASSED`; any fail → `SMOKE FAILED: <reason>`.

**Step 3 — Output the run handle (async path).**
After `async_job` returns, emit the handle on the last line of your response:

```
RUN_HANDLE: {<handle dict returned by async_job>}
```

**If the trigger fails**, output `INCOMPLETE: <reason>`.

Do NOT run write-path scenarios, mutation tests, or any scenario that creates/modifies
production data.
