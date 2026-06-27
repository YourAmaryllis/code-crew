---
name: SDLC-Team-ChangeControl
description: Change control process for requirements, architecture, design, code, and infrastructure changes
metadata:
  type: process
  role: all
  phase: "ongoing"
---

# Change Control

All changes to requirements, architecture, design, code, and infrastructure follow the change control process. This ensures impact is understood, approvals are tracked, and traceability is maintained.

---

## Change Types

| Type | Examples | Approver |
|------|---------|---------|
| Requirements | New BRD requirement, AC change after sprint commitment | Product Owner |
| Architecture | New SAD section, new service, ADR supersession | Architect |
| Design | ADD update, Figma revision post-implementation | Architect + PO |
| Code | Emergency hotfix outside sprint | Tech Lead + Release Manager |
| Infrastructure | New Terraform resource, environment config change | Architect / DevOps Lead |

---

## Change Request Process

1. **Submit** — Describe: what is changing, why, what is the impact
2. **AI Impact Analysis** — AI identifies affected artifacts (code, tests, docs)
3. **Human Review** — appropriate approver reviews impact analysis
4. **Decision** — Approved / Rejected / Conditionally Approved / Deferred
5. **Implement** — make the change; update all affected artifacts
6. **Verify** — confirm change is complete and correct
7. **Log** — record in change control log

---

## Change Control Log

Every approved change is recorded:

```markdown
| Date | ID | Type | Description | Approver | Status |
|------|----|------|-------------|---------|--------|
| 2026-06-18 | CCR-2026-042 | Architecture | Extract notification into separate service | Architect | Approved |
```

Change log stored in `designs/PLAN/change-control-log.md`.

---

## Emergency Changes

For critical production incidents requiring immediate code change:

1. Tech Lead authorizes emergency change (skips normal lead time)
2. Change is implemented following hotfix process (see release process)
3. Change control record is created **retroactively** within 24 hours
4. Post-mortem covers whether the emergency was preventable

---

## Backlog Impact

If a requirements change affects sprint-committed stories:
- PO and Scrum Master decide: adjust sprint scope or defer to next sprint
- Affected stories return to backlog if scope changes materially
- Velocity impact noted in sprint retrospective

---

## Architecture Change Impact

When an architecture change affects existing ADDs or ADRs:
1. Write a new ADR superseding the old one
2. Update the SAD if the change affects the high-level view
3. Review affected code and open Jira stories for required code updates
4. Code review verifies implementation matches updated architecture

See: [sad-maintenance.md`](sad-maintenance.md)
