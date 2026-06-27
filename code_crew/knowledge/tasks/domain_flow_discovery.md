---
type: CrewAI Task
title: Domain Flow Discovery
description: Identify distinct business flows and subdomains before per-flow event storming begins
tags: [domain, event-storming, flow-discovery]
agent: architect
expected_output: >
  Ordered list of named business flows with core/supporting/generic classification.
  Ends with FLOW DISCOVERY COMPLETE.
---

You are facilitating Phase 1 of a domain modeling session. Your goal is to identify the distinct business flows before diving into event-level detail.

**Step 1 — Load methodology guide.**
Use `knowledge_reader` to load `functions/domain-methodologies/<DOMAIN_METHODOLOGY>.md` (default: `event-storming`). Follow its Phase 1 instructions exactly.

**Step 2 — Ask the SME to describe the system.**
Use `ask_human` with this opening:

```
SME QUESTIONS — Flow Discovery (round 1):
1. In 2–3 sentences, what does this system do and who are its primary users?
2. What are the most important business outcomes it needs to achieve?
3. Are there distinct areas owned by different teams or stakeholders?
AWAITING SME RESPONSE
```

**Step 3 — Identify candidate flows.**
From the SME's answers, identify 3–7 candidate business flows. Flows should have:
- A distinct lifecycle (start → end)
- A clear owner or actor
- A meaningful business outcome

If any flows are ambiguous, batch up to 5 follow-up questions and call `ask_human` again.

**Step 4 — Classify each flow.**
For each flow, classify as:
- **core** — the primary business capability; competitive differentiator
- **supporting** — necessary but not differentiating (e.g. notifications, reporting)
- **generic** — commodity (e.g. authentication, billing via Stripe)

**Step 5 — Output.**

```
FLOWS IDENTIFIED:
1. <Flow Name> — <one-sentence description> [core|supporting|generic]
2. <Flow Name> — <one-sentence description> [core|supporting|generic]
...

DOMAIN METHODOLOGY: <methodology used>
FLOW DISCOVERY COMPLETE
```
