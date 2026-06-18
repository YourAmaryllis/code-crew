---
type: CrewAI Task
title: Release Plan
description: Produce staging promote checklist and production release gate; never trigger prod autonomously
tags: [release, staging, production, promote, gate, phase-20, phase-21]
timestamp: 2026-06-17T00:00:00Z
agent: release_manager
context_agents:
  - ops_lead
  - monitoring_engineer
expected_output: >
  A staging promote summary (what was promoted, RC tag, ECS status) and a production
  release checklist that a human must complete before triggering prod promote. Draft
  release notes with Jira keys. Clear statement that production promote is human-triggered only.
---

Produce the release artifacts for this sprint's changes.

Load SOP-SDLC-Trunk-Promote-Release via the `sop_reader` tool before producing any
release artifacts. Do not rely on memory for the exact sequence.

**Staging promote** (this may be triggered after CI is confirmed green):

1. Confirm `main` CI is green for all affected service paths (report the workflow run status)
2. Trigger `Promote and release` workflow with `environment: staging`
3. Record the RC tag produced (format: `v<X>.<Y>.<Z>-rc<N>`)
4. Confirm ECS service stability: all tasks healthy, no failed deployments
5. Post staging URL and RC tag to the team channel

**Draft release notes:**

```markdown
## Release <RC tag> — <date>

### Features
- <JIRA-KEY>: <PR title / description>

### Fixes
- <JIRA-KEY>: <PR title>

### Infrastructure
- <JIRA-KEY>: <Terraform/CI change description>
```

**Production release checklist** (must be completed by a human before prod promote):

- [ ] Staging QA sign-off: QA engineer has run and approved all BDD scenarios
- [ ] Security scan clean: no Critical/High CVEs in the staging image
- [ ] Monitoring dashboards reviewed: no anomalies in staging error rate or latency
- [ ] Release notes reviewed and approved by Tech Lead
- [ ] Stakeholder sign-off: Product Owner has accepted the increment
- [ ] Rollback plan confirmed: previous image tag recorded, rollback GHA run verified
- [ ] On-call engineer briefed: aware of the deploy and monitoring plan
- [ ] Human runs: `Promote and release` with `environment: prod`

**⚠️ PRODUCTION PROMOTE IS HUMAN-TRIGGERED ONLY. This agent does not and cannot
initiate the production promote workflow. A human must run it after completing
the checklist above. ⚠️**
