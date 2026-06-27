---
type: CrewAI Task
title: Launch Decision
description: Release Engineer reviews staging verification results and makes a formal go/no-go recommendation for production promotion
tags: [release, launch, go-no-go, staging, production, phase-22]
agent: release_engineer
expected_output: >
  LAUNCH APPROVED — explicit go/no-go verdict with: staging smoke summary, migration
  requirements (None or specific steps), open known issues, and the recommended
  workflow_dispatch inputs (image SHA, version, service name).
  OR LAUNCH BLOCKED: <reason> if staging is unhealthy or migration risk is unacceptable.
---

Review the staging verification results and make a formal launch recommendation.
This is the go/no-go gate before a human triggers production promotion.

**Step 1 — Read staging results.**
From `staging_verification` task output (in your context): how many scenarios ran,
how many passed, any failures. If `STAGING FAILED` is in the output, output
`LAUNCH BLOCKED: staging smoke failed — <reason>` immediately.

**Step 2 — Review release notes.**
From `release_notes` task output (in your context): version impact (PATCH/MINOR/MAJOR),
migration requirements, and known issues. If `MIGRATION REQUIRED` is flagged, explicitly
confirm whether it is safe to apply before or after the deploy.

**Step 3 — Check for open blockers.**
Use `jira_view` to check the ticket. If any sub-task or linked issue is open and
blocking, flag it. If all blocking issues are resolved, note that.

**Step 4 — Compile the launch recommendation.**

Go format:
```
## Launch Decision for <JIRA-KEY>

**Verdict**: LAUNCH APPROVED

**Staging**: <N> smoke scenarios passed. No failures.

**Version impact**: PATCH / MINOR / MAJOR — <reason>

**Migration**: None / <description and timing>

**Known issues**: None / <list>

**Production promotion inputs**:
- image_sha: <git SHA>
- version: <semver>
- service: <ecs-service-name>

To promote: trigger `promote-and-release.yml` workflow_dispatch (GitHub)
or the manual `promote-production` pipeline job (GitLab) with the inputs above.
```

No-go format:
```
## Launch Decision for <JIRA-KEY>

**Verdict**: LAUNCH BLOCKED

**Reason**: <specific reason — failed smoke, open blocker, unsafe migration>

**Next step**: <what must happen before re-attempting launch>
```

**Completion signal — mandatory.**
End with exactly:
- `LAUNCH APPROVED` — staging is healthy, migration risk is acceptable, production promotion is unblocked
- `LAUNCH BLOCKED: <reason>` — do not promote to production until the blocker is resolved
