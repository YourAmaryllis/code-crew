# ADD-008: Incremental Per-Unit LLM Task Decomposition

**Status:** Accepted  
**Date:** 2026-07-04  
**Related:**
- [ADR-007: Python Flow Orchestration](../adr/ADR-007-Python-Flow-Orchestration.md)
- [ADD-006: OKF Knowledge Architecture](../add/ADD-006-OKF-Knowledge-Architecture.md)

---

## Purpose

Define the design pattern for decomposing tasks whose scope is unknown in advance into a series of small, bounded LLM calls driven by a Python outer loop. Each call handles exactly one unit of work; Python accumulates state between calls and writes incremental output to disk after each step.

This pattern was introduced for threat modeling (`/threat`) but applies to any flow where the number of work units is discovered at runtime and the units are independently analysable.

---

## Problem

Some tasks require the LLM to analyse every component, boundary, actor, or connection in a system before the work is complete. The number of units is unknown until a discovery step runs — a five-service system and a fifty-service system use the same crew definition.

Handling this with a single large crew call causes several cascading problems:

| Problem | Root cause |
|---|---|
| Context grows without bound | Each new unit's output is appended to the conversation before the next unit is analysed |
| 504 gateway timeouts | Hosted LLMs (NVIDIA Build, Bedrock) impose generation-time limits; large accumulated context hits them |
| Total failure on partial error | One bad unit aborts the entire run; work already done is lost |
| Opaque progress | No partial output until the entire run completes (or crashes) |
| Retry cost is total | A failure at unit N means re-running all N units |

---

## Pattern

### Structure

```
Python outer loop
│
├── Phase 1 — Discovery (one crew call)
│     Scope is small and bounded: read source + infra, output unit inventory
│     Result: list of units (components, boundaries, actors, connections)
│
├── Phase 2 — Per-unit analysis (one crew call per unit)
│     Context: pre-scanned project facts + unit definition
│     No tools — all context provided by Python from Phase 1
│     Result: unit-specific analysis (e.g. threats for this component)
│     → write partial output to disk after each call
│
├── Phase 3 — Per-unit synthesis (one crew call per unit)
│     Context: unit + its Phase 2 results only
│     No tools
│     Result: derived artifacts (e.g. mitigations for this component's threats)
│     → write partial output to disk after each call
│
└── Gate — one crew call on the assembled output
      Validates the full accumulated result
      Revision loop retries only the gate + patch, not Phases 1–3
```

### Key constraints

**No tools in Phases 2 and 3.** Python pre-scans the project and injects all necessary context into the task description before calling the crew. Giving the agent file-reading tools causes it to loop on irrelevant documents instead of using the provided context.

**Context is bounded per call.** Each Phase 2/3 call receives: (a) pre-scanned project facts, (b) the unit being analysed, (c) results from the previous phase for this unit. It does not receive the accumulated results of all other units. This keeps every call under ~20k tokens regardless of system size.

**One crew = one agent = one LLM call.** Phases 2 and 3 use `Process.sequential` with a single agent and `max_iter=5`. No manager, no delegation. The agent either produces the required YAML in one generation or is retried by Python.

**Partial output on disk after every unit.** Python writes a valid (though incomplete) output file after each unit completes. This means: progress is visible, the run can be inspected mid-flight, and a checkpoint resume is possible (future work).

**504 retry at the call level.** Gateway timeouts are retried with backoff (`_kickoff_timed`) rather than propagated as failures. This handles transient API slowness without restarting earlier phases.

---

## Unit sizing guidance

A unit should be:
- **Independently analysable** — the analysis of unit A does not require the completed analysis of unit B
- **Small enough** to fit comfortably in one LLM call alongside the shared project context (~5–15k tokens total input)
- **Large enough** to produce a meaningful output — avoid splitting units so finely that the overhead of N crew constructions dominates

For threat modeling: one component per Phase 2 call, one component per Phase 3 call. Threats that span components are captured in the gate's revision pass.

For code review: one file or one logical module per call.

For dependency audit: one dependency per call (or one manifest if manifests are small).

---

## Python responsibilities

The outer loop in Python is responsible for:

1. **Unit inventory** — parsing Phase 1 output into a structured list
2. **Context assembly** — building the task description string for each unit from pre-scanned facts + unit definition + prior phase results
3. **ID management** — assigning sequential IDs across units (e.g. T-001 through T-NNN across components, renumbered at final assembly)
4. **Cross-reference updates** — after renumbering, updating all references (e.g. `mitigatedThreats`, `targetedComponents`)
5. **Partial writes** — writing the accumulating output file after each unit
6. **Final assembly** — combining all units' outputs into the complete artifact
7. **Gate handoff** — passing the fully assembled artifact to the gate crew

The LLM is responsible only for analysis within a single unit. Coordination, ordering, and assembly are Python's job.

---

## Output format contract

Each per-unit crew must output a named YAML section that Python can extract reliably:

```yaml
threats:          # or: mitigations:, findings:, events:, etc.
  - id: T-001
    ...
THREATS COMPLETE  # completion signal — required for _parse_yaml_section
```

The `_parse_yaml_section(text, key)` helper strips markdown fences and completion markers, extracts the named section, and returns a parsed list. It returns `[]` on any parse failure — never raises, so a single bad unit does not abort the run.

---

## When to apply this pattern

Apply when all of the following are true:

- The number of work units is unknown until a discovery step runs
- Units are independently analysable (no cross-unit dependency within a phase)
- A single all-in-one call would accumulate unbounded context
- Partial results are useful (gate or human can review incomplete output)

Do **not** apply when:
- The task has fixed, known scope (use a standard sequential or hierarchical crew)
- Units have strong dependencies (later units need earlier units' results to reason)
- The total output is small enough to fit comfortably in one call

---

## Implementation checklist

When adding a new flow that uses this pattern:

- [ ] Phase 1 crew: hierarchical or sequential, outputs structured YAML inventory
- [ ] Phase 2 crew builder: `tools=[]`, `max_iter=5`, context assembled by Python
- [ ] Phase 3 crew builder (if needed): same constraints as Phase 2
- [ ] `_parse_yaml_section` used for all LLM output parsing
- [ ] Partial output written to disk after every unit
- [ ] `_kickoff_timed` used for all crew calls (handles timeout + 504 retry)
- [ ] Gate receives fully assembled output, not per-unit output
- [ ] Revision loop retries gate + patch only, not Phases 1–3
