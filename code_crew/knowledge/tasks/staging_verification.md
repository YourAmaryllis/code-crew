---
type: CrewAI Task
title: Staging Verification
description: QA runs the BDD smoke suite against staging to confirm the promoted build is healthy
tags: [qa, staging, bdd, smoke, verification, phase-21]
agent: qa_lead
expected_output: >
  STAGING VERIFIED — BDD smoke suite pass count, any skipped or failed scenarios, and
  a go/no-go recommendation for production promotion. OR STAGING FAILED: <reason> if
  critical scenarios failed.
---

Run the BDD smoke suite against the staging environment and confirm the build is healthy.

**Step 1 — Confirm staging URL.**
The `promote_staging` task output (in your context) includes the staging URL. Use it as
`BASE_URL` for the test run.

**Step 2 — Load BDD conventions.**
Use `knowledge_reader` to load `bdd-testing` so you know the tagging conventions and
test reset endpoint (`POST /internal/test/reset`).

**Step 3 — Reset staging test state.**
Before running, reset staging to a known state:
```bash
curl -X POST https://<staging-url>/internal/test/reset \
  -H "X-Internal-Token: $TEST_RESET_TOKEN"
```
`TEST_RESET_ENABLED=true` must be set on staging. If the reset endpoint returns non-200,
stop and flag `INCOMPLETE: staging test reset failed`.

**Step 4 — Run the smoke suite.**
Run only scenarios tagged `@smoke` (fast, critical-path only). Use whichever approach is configured for this project:
- If `commands.staging_smoke` is set in `.code-crew/structure.md`: run it with `BASE_URL=<staging-url>` prepended
- Otherwise use the `bdd_runner` tool with the `@smoke` tag filter and the staging URL

**Step 5 — Evaluate results.**
- All `@smoke` scenarios pass → `STAGING VERIFIED`
- Any `@smoke` scenario fails → `STAGING FAILED: <scenario name and failure reason>`

Do NOT run the full BDD suite in staging — `@smoke` only. Full suite runs in dev via
`devops_coordination`.

**Completion signal — mandatory.**
End with exactly:
- `STAGING VERIFIED` — all smoke scenarios passed, production promotion is unblocked
- `STAGING FAILED: <reason>` — one or more critical scenarios failed; do not promote to prod
