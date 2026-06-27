---
type: CrewAI Task
title: Domain Event Storming — Per-flow
description: Run a full event storming session for one named business flow, producing a structured event board
tags: [domain, event-storming, per-flow]
agent: architect
expected_output: >
  Structured event board for one flow with events, commands, actors, aggregates, policies, and hot spots.
  Ends with FLOW STORMING COMPLETE: <Flow Name>.
---

You are facilitating Phase 2 event storming for **one specific business flow**. The flow name and prior context are provided in your task input.

**Step 1 — Load methodology guide.**
Use `knowledge_reader` to load `functions/domain-methodologies/<DOMAIN_METHODOLOGY>.md` (default: `event-storming`). Follow its Phase 2 instructions exactly.

**Step 2 — Announce the flow.**
State clearly which flow you are modeling. Reference prior flows already completed (if any) to avoid repeating the same events.

**Step 3 — Chaotic exploration.**
Ask the SME to brain-dump everything that can happen in this flow. Batch 4–5 questions:

```
SME QUESTIONS — <Flow Name> (round 1):
1. Walk me through what happens from the start of this flow to its happy-path end.
2. What triggers the flow? (user action, external event, schedule?)
3. What are the worst things that can go wrong in this flow?
4. Are there any approval steps, waiting states, or async hand-offs?
AWAITING SME RESPONSE
```

**Step 4 — Build the event timeline.**
From the SME's answers, identify all domain events (past tense, e.g. "OrderPlaced"). Arrange them in timeline order.

If events are unclear or ordering is ambiguous, ask another round (max 5 questions):
```
SME QUESTIONS — <Flow Name> (round N):
1. <specific ordering or trigger question>
...
AWAITING SME RESPONSE
```

**Step 5 — Add commands, actors, aggregates, and policies.**
For each event, identify:
- 🔵 The command that triggered it
- 🟣 The actor who issued the command
- 🟡 The aggregate that owns the state change
- 🩷 Any policy ("whenever X then Y") triggered by the event

Mark 🔴 hot spots for anything ambiguous.

**Step 6 — Output the event board.**

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
