---
type: CrewAI Task
title: Promote to Staging
description: DevOps triggers the staging promotion CI run and returns a run handle for async polling
tags: [devops, staging, promotion, ecs, ecr, cicd, phase-21]
agent: devops_lead
expected_output: >
  RUN_HANDLE: {"type": "gh_actions", "run_id": <id>, "workflow": "<file>", "repo": "<owner/repo>"}
  on the last line when the CI run is triggered asynchronously, OR
  STAGING DEPLOYED — image sha, ECS service name, staging URL, and confirmation that
  the service reached a stable state, if the pipeline completes inline.
  INCOMPLETE: <reason> if the pipeline could not be triggered.
---

Promote the implementation from dev to the staging environment.

**Step 1 — Identify the image to promote.**
From the release_notes task output (in your context), find the git SHA or image tag that
passed DoD. If not explicit, run:
```bash
git rev-parse --short HEAD
```

**Step 2 — Determine the CI/CD stack.**
Use `knowledge_reader` to load `github` or `gitlab` (whichever the platform uses).
Check for a `.github/` directory or `.gitlab-ci.yml` in `workspace_reader` to confirm.

**Step 3 — Trigger staging promotion (fire-and-return).**
Using the `async_job` tool, kick off the staging promotion:

**Option A — GHA workflow:**
```
async_job(operation="start", type="gh_actions",
          params={"workflow": "promote-staging.yml", "ref": "<branch>",
                  "inputs": {"image_sha": "<sha>", "service": "<ecs-service>"}})
```

**Option B — ECS direct update:**
```
async_job(operation="start", type="ecs",
          params={"cluster": "staging", "service": "<ecs-service>", "image": "<ecr-uri>:<tag>"})
```

Do NOT use `gh run watch` or wait for completion inline — the REPL polls via /loop.

**Step 4 — Output the run handle.**
After `async_job` returns, emit the handle on its own line at the end of your response:

```
RUN_HANDLE: {<handle dict returned by async_job>}
```

**If the trigger fails** (`async_job` returns an error), output:
```
INCOMPLETE: <reason> — could not trigger staging promotion
```

**Inline completion (optional).**
If the platform has no `promote-staging.yml` workflow and you must deploy directly
(e.g. `aws ecs update-service` + wait), you may complete inline. In that case confirm
the service reached a stable state and end with `STAGING DEPLOYED`.
