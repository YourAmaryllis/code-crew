---
name: SDLC-Team-SprintProcess
description: Sprint ceremonies, cadence, roles, and how AI crews fit into the sprint workflow
metadata:
  type: process
  role: all
  phase: "13"
---

# Sprint Process

---

## Sprint Cadence

- **Sprint length**: 2 weeks
- **Sprint start**: Tuesday (planning)
- **Sprint end**: Friday (review + retro)

| Day | Event | Cadence |
|-----|-------|---------|
| Tuesday | Sprint Planning | Bi-weekly (sprint start) |
| Wednesday | Backlog Refinement | Weekly |
| Daily | Standup (15 min) | Daily |
| Friday | Sprint Review | Bi-weekly (sprint end) |
| Friday | Retrospective | Bi-weekly (sprint end) |

---

## Sprint Planning (Phase 13)

**Duration**: 2–4 hours  
**Facilitator**: Scrum Master  
**Participants**: Scrum Master, Product Owner, Tech Lead, Engineers

Agenda:
1. Product Owner presents sprint goal and prioritized backlog
2. Team reviews each story for DoR compliance
3. Stories not meeting DoR are returned to backlog (not pulled in)
4. Team estimates (if not already estimated in refinement)
5. Team commits to stories for the sprint
6. Scrum Master performs sprint planning check (AI-assisted):
   - All pulled stories meet DoR
   - Dependencies identified and sequenced
   - Figma/design references present where needed
   - Sprint goal is coherent

**Sprint planning check outcome:**
- APPROVED — sprint can start
- CHANGES REQUESTED — specific stories returned with reasons

---

## Backlog Refinement (Weekly)

**Duration**: 1–2 hours  
**Facilitator**: Scrum Master  
**Participants**: Scrum Master, Product Owner, Tech Lead

Agenda:
1. Review new stories added since last refinement
2. Write/refine acceptance criteria
3. Add design references (Figma, ADD, etc.)
4. Estimate story points
5. Identify and link dependencies
6. Confirm DoR checklist

---

## Daily Standup

**Duration**: 15 minutes  
**Format**: What did I do yesterday? What am I doing today? Any blockers?

Blockers are escalated to the Scrum Master immediately. A blocker that isn't resolved within the sprint puts the story at risk.

---

## Sprint Review

**Duration**: 1–2 hours  
**Audience**: Stakeholders welcome  
**Format**: Demo of completed work; Product Owner accepts or requests changes

- Only stories meeting DoD are presented as "done"
- Stories not meeting DoD carry over to next sprint (not accepted)
- Product Owner updates the backlog based on feedback

---

## Retrospective

**Duration**: 1 hour  
**Format**: What went well? What could be better? What do we try next sprint?

Three action items max per retro. Actions are tracked in Jira as chore tickets.

---

## AI Crew in the Sprint

The code-crew CLI executes phases 13–19 for each ticket in the sprint:

```
code-crew sprint --sprint "Sprint 5"
```

Execution order is determined by dependency analysis (topological sort). The crew produces evidence (test reports, code review output, DoD check output) for human review.

**Human gates that AI does not replace:**
- Sprint planning check approval → Scrum Master
- Code review approval → Architect / Tech Lead
- Staging acceptance sign-off → QA Lead
- Production promotion → Release Manager

The crew's output is text for human review. Engineers implement, merge, and deploy.

---

## Sprint Metrics

| Metric | Meaning | Target |
|--------|---------|--------|
| Velocity | Story points completed per sprint | Stable or improving |
| Burndown | Daily progress toward sprint commitment | Linear toward 0 |
| Cycle time | Jira ticket opened → Done | < sprint length |
| Defect escape rate | Bugs found in prod that passed QA | 0 per sprint |
| DoD pass rate | Stories closed without rework | > 90% |

Metrics reviewed at retrospective. Scrum Master owns the dashboard.
