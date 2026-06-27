---
type: CrewAI Task
title: Domain Synthesis
description: Read all per-flow event boards and produce the final domain model — bounded contexts, aggregates, ubiquitous language, and Mermaid diagram
tags: [domain, synthesis, ddd]
agent: architect
expected_output: >
  Bounded context map, aggregate definitions, ubiquitous language glossary, and Mermaid class diagram.
  Files written to designs/DMD/. Ends with DOMAIN SYNTHESIS COMPLETE.
---

You are performing Phase 3 synthesis. All per-flow event boards are provided in your context.

**Step 1 — Identify bounded contexts.**
Read all event boards. Group flows that:
- Share the same aggregates
- Use the same terminology consistently
- Are owned by the same team or stakeholder

Flows with a clear seam (different lifecycle, different ownership, different language) → separate bounded contexts.

**Step 2 — Define aggregates per context.**
For each aggregate identified across all flows:
- Name the aggregate root
- List its invariants (business rules that must always hold)
- List the domain events it emits
- List entities and value objects it contains

If any aggregate boundaries are unclear, ask the SME:
```
SME QUESTIONS — Synthesis (round N):
1. <question about shared ownership or consistency boundary>
2. <question about event ownership>
AWAITING SME RESPONSE
```

**Step 3 — Build ubiquitous language glossary.**
Every 🟠 domain event name and 🟡 aggregate name is a candidate term. For each term:
- Write a one-sentence business definition (not a technical definition)
- Assign it to a bounded context

Flag synonyms — if two flows used different words for the same concept, pick one canonical term and note the alias.

**Step 4 — Draw Mermaid class diagram.**
Produce a classDiagram with namespace blocks per bounded context. Show:
- Aggregates and their key attributes
- Relationships between aggregates (association, composition)
- Domain events emitted (dashed arrows with `..>`)

Follow the format from the DDD methodology guide.

**Step 5 — Write output files.**
Use `file_write` to save:
- `designs/DMD/<system>-domain.md` — prose description: bounded contexts, aggregate definitions, ubiquitous language table
- `designs/DMD/<system>-diagram.mmd` — Mermaid diagram only (no code fences, raw mermaid syntax)

**Step 6 — Output.**

```
BOUNDED CONTEXTS: <count>
AGGREGATES: <count>
GLOSSARY TERMS: <count>
FILES WRITTEN:
  designs/DMD/<system>-domain.md
  designs/DMD/<system>-diagram.mmd

DOMAIN SYNTHESIS COMPLETE
```
