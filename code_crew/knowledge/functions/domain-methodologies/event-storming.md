---
type: Methodology Guide
title: Event Storming
description: Three-phase async event storming facilitation guide for domain modeling sessions
tags: [domain, event-storming, ddd, methodology]
---

## Overview

Event storming is a collaborative domain modeling technique where a facilitator (the Architect) guides participants through discovering domain events, commands, aggregates, actors, and policies. This implementation runs as an async agent-facilitated session with the user acting as SME (Subject Matter Expert).

## Phase structure

```
Phase 1 — Flow Discovery       (once)
Phase 2 — Per-flow Storming    (once per flow identified in Phase 1)
Phase 3 — Synthesis            (once, after all flows complete)
```

---

## Phase 1 — Flow Discovery

**Goal:** Identify the distinct business flows / subdomains before diving into events.

**Agent role:** Architect as facilitator.

**Steps:**
1. Ask the SME to describe the system in 2–3 sentences (what it does, who uses it)
2. Identify candidate flows from that description (look for: distinct user journeys, separate lifecycles, clear handoff points between teams)
3. Batch clarifying questions (max 5) about scope and boundaries:
   - "Is X a core business capability or a supporting service?"
   - "Do Y and Z share the same lifecycle, or are they independent?"
   - "Are there different teams or stakeholders responsible for different parts?"

**SME question format (mandatory):**
```
SME QUESTIONS — Flow Discovery (round N):
1. <question>
2. <question>
...
AWAITING SME RESPONSE
```

**Output format:**
```
FLOWS IDENTIFIED:
1. <Flow Name> — <one-sentence description> [core|supporting|generic]
2. <Flow Name> — <one-sentence description> [core|supporting|generic]
...
FLOW DISCOVERY COMPLETE
```

---

## Phase 2 — Per-flow Event Storming

**Goal:** For one named flow, discover the full event timeline.

**Agent role:** Architect as facilitator, with Product Owner validating business language.

**Sticky colour conventions (textual representation):**
- 🟠 **Domain Event** — something that happened, past tense ("OrderPlaced", "PaymentFailed")
- 🔵 **Command** — what triggered the event ("PlaceOrder", "ProcessPayment")
- 🟡 **Aggregate** — the thing that owns the state change ("Order", "Payment")
- 🟣 **Actor** — who issues the command ("Customer", "PaymentGateway", "ScheduledJob")
- 🩷 **Policy** — "whenever X then Y" rule ("whenever OrderPlaced then ReserveInventory")
- 🔴 **Hot spot** — ambiguity or problem to resolve later

**Steps:**
1. Start with chaotic exploration: list all domain events for this flow (no ordering yet)
2. Enforce a timeline: arrange events left → right in the order they occur
3. Pivot on pivotal events: identify the 2–3 most important events that change the business state
4. Add commands + actors for each event
5. Add aggregates that own the state
6. Identify policies (when → then rules)
7. Mark hot spots (ambiguities, edge cases, missing info)

**SME batching — ask questions in rounds of 3–5:**
```
SME QUESTIONS — <Flow Name> (round N):
1. <question about event trigger or actor>
2. <question about edge case or exception>
3. <question about policy or rule>
AWAITING SME RESPONSE
```

**Per-flow output format:**
```
EVENT BOARD: <Flow Name>
=====================================
DOMAIN EVENTS (timeline order):
🟠 <EventName> — <description>
🟠 <EventName> — <description>

COMMANDS + ACTORS:
🔵 <CommandName> → triggers → 🟠 <EventName>
   🟣 Actor: <ActorName>

AGGREGATES:
🟡 <AggregateName>
   Owns: [<EventName>, <EventName>]
   State transitions: <description>

POLICIES:
🩷 Whenever <EventName> → <PolicyName> → <CommandName>

HOT SPOTS:
🔴 <description of ambiguity or open question>

FLOW STORMING COMPLETE: <Flow Name>
```

---

## Phase 3 — Synthesis

**Goal:** Read all per-flow event boards and produce the final domain model.

**Agent role:** Architect.

**Steps:**
1. Identify bounded contexts: flows that share aggregates and language → same context; flows with clear seams → separate contexts
2. Define aggregates: name, root entity, invariants, owned domain events
3. Build ubiquitous language glossary: every orange sticky becomes a candidate term
4. Draw Mermaid class diagram showing bounded contexts, aggregates, and key relationships

**Output:** Written to `designs/DMD/` — see `domain_synthesis` task for file format.

---

## Ubiquitous language rules

- Terms must be consistent between event board stickies, code, and documentation
- Synonyms are not allowed: pick one term per concept and use it everywhere
- Each term belongs to exactly one bounded context (the same word can mean different things in different contexts — document that explicitly)
- Verbs in domain events: past tense, active voice ("OrderPlaced" not "PlaceOrder" or "OrderWasPlaced")
