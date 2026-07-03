---
type: CrewAI Task
title: Staging Verification
description: QA triggers the BDD smoke suite against staging and returns a run handle for async polling
tags: [qa, staging, bdd, smoke, verification, phase-21]
agent: qa_lead
expected_output: >
  RUN_HANDLE: {<async_job handle — type gh_actions or shell>}
  on the last line when the BDD run is triggered asynchronously, OR
  STAGING VERIFIED — BDD smoke suite pass count, any skipped or failed scenarios, and
  a go/no-go recommendation for production promotion, if the suite completes inline.
  STAGING FAILED: <reason> if critical scenarios failed inline.
---

Run the BDD smoke suite against the staging environment and confirm the build is healthy.

**Step 1 — Confirm staging URL.**
The `promote_staging` task output (in your context) includes the staging URL. Use it as
`BASE_URL` for the test run.

**Step 2 — Load BDD conventions.**
Use `knowledge_reader` to load `bdd-testing` so you know the tagging conventions,
the `@smoke` tag filter, and the test reset endpoint (`POST /internal/test/reset`).

**Step 3 — Reset staging test state.**
Before running, reset staging to a known state:
```bash
curl -X POST https://<staging-url>/internal/test/reset \
  -H "X-Internal-Token: $TEST_RESET_TOKEN"
```
`TEST_RESET_ENABLED=true` must be set on staging. If the reset endpoint returns non-200,
stop and flag `INCOMPLETE: staging test reset failed`.

**Step 4 — Trigger the smoke suite (fire-and-return preferred).**

Use `async_job` to start the test run in the background. Choose the type that fits the project:

**Option A — GHA workflow** (if `staging-smoke.yml` or similar exists):
```
async_job(operation="start", type="gh_actions",
          params={"workflow": "staging-smoke.yml", "ref": "<branch>",
                  "inputs": {"base_url": "<staging-url>"}})
```

**Option B — Direct shell** (BDD suite run locally, no CI workflow needed):
```
async_job(operation="start", type="shell",
          params={"command": "<commands.staging_smoke or bdd runner command> --tags @smoke",
                  "label": "BDD smoke suite", "cwd": "<project root>"})
```

For both options: emit the `RUN_HANDLE:` line (Step 5) and stop — the REPL polls via /loop.
Do NOT use `bdd_runner` directly for long-running suites; use `async_job type=shell` instead.

Do NOT run the full BDD suite — `@smoke` only.

**Step 5 — Output the run handle (async path).**
After `async_job` returns, emit the handle on the last line of your response:

```
RUN_HANDLE: {<handle dict returned by async_job>}
```

**If the trigger fails**, output `INCOMPLETE: <reason>`.
