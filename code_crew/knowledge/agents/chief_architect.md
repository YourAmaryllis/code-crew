---
name: ChiefArchitect
description: Human role — final authority on novel architectural decisions with no existing ADR/ADD precedent
metadata:
  type: role
  human: true
  tags: [architecture, decision, governance]
---

# Chief Architect

The Chief Architect is a **human role**. There is no AI agent for this role.

## Responsibility

The Chief Architect is the final authority on architectural decisions that are genuinely novel — situations where no existing ADR or ADD provides precedent, and where the choice will have long-term consequences for the system's structure, security posture, or operational complexity.

## When the Crew Consults the Chief Architect

The Architect agent escalates to the Chief Architect when:

- A story introduces a cross-cutting technical choice with no existing ADR/ADD precedent
- Multiple reasonable options exist and the trade-offs are significant enough that the wrong choice is hard to reverse
- A proposed deviation from an existing ADR is substantial enough to warrant a new architectural direction

The Architect presents:

- The decision point (one sentence)
- Numbered options, each with concise pros and cons
- A recommendation if one is strongly favoured

## Chief Architect Response Options

1. **Select an option** — type the option number. The Architect documents the decision in an ADR, updates the relevant ADD and SAD section, and proceeds.
2. **Ask a question or provide more context** — type it as free text. The Architect incorporates it and may refine the options or make the decision directly.
3. **Provide the decision directly** — type the decision and rationale. The Architect documents it as-is.

## What the Chief Architect Does NOT Do

- The Chief Architect does not review every ticket — only novel decisions escalate
- Routine alignment with existing ADRs is the Architect agent's responsibility
- The Chief Architect does not review code or BDD specs — those go to human reviewers at the PR gate

## After a Decision

Once the Chief Architect responds, the Architect agent:

1. Writes or updates the ADR with Status: Accepted
2. Updates the relevant ADD (or creates one) with implementation detail
3. Updates the SAD section if the decision changes component structure, data flow, or security posture
4. Re-runs the architecture review to confirm alignment before approving for QA and engineering

Only after this documentation is complete does the flow proceed to QA and the engineer.
