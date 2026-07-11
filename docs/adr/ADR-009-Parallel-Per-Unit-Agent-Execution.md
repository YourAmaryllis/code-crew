# ADR-009: Parallel Per-Unit Agent Execution

**Status:** Accepted  
**Date:** 2026-07-04  
**Related:**
- [ADR-007: Python Flow Orchestration](ADR-007-Python-Flow-Orchestration.md)
- [ADD-008: Incremental Per-Unit LLM Decomposition](../add/ADD-008-Incremental-Per-Unit-LLM-Decomposition.md)
- [ADD-009: Parallel Crew Execution](../add/ADD-009-Parallel-Crew-Execution.md)

---

## Context

ADD-008 established the incremental per-unit decomposition pattern: Python drives an outer loop, one LLM call per unit of work, results accumulated sequentially. This solved context accumulation and 504 timeouts.

The remaining bottleneck is **wall time**. With N components and ~5–15 min per unit (including API latency and retries), a sequential run takes N×T minutes. For threat modeling a 6-component system this is 1–2 hours on the NVIDIA Build free tier.

Units in Phase 2 (threats) and Phase 3 (mitigations) have **no cross-unit dependency**: threat analysis for component A does not require the completed result from component B. This is the necessary condition for parallelism.

Additionally, the two-phase structure (threats then mitigations) creates artificial sequencing: Phase 3 only needs the threats for the **same component**, which are available the moment Phase 2 finishes for that component. Running them as separate phases forces every component's Phase 2 to complete before any component's Phase 3 begins.

---

## Decision

**Run per-unit analysis in parallel** using `crew.kickoff_async()` and `asyncio.gather()`, with a bounded semaphore to stay within API rate limits.

**Combine threats + mitigations into a single per-component call.** The agent generates `threats:` then immediately generates `mitigations:` for those same threats in one pass, eliminating the need for a separate Phase 3 entirely.

---

## Consequences

### Benefits

- **Wall time**: drops from `N × T` to approximately `ceil(N / MAX_PARALLEL) × T` — e.g. 6 components at 3 parallel = 2 rounds instead of 6 sequential rounds
- **Fewer API calls**: combining threats + mitigations halves the number of crew calls vs the previous two-phase approach
- **Self-consistent output**: the agent generates mitigations in the same context window as the threats, so `mitigatedThreats` references are always correct (no cross-call ID mismatch)
- **Simpler control flow**: one loop, one result collection, one OTM write — vs two sequential for-loops with interleaved partial writes

### Trade-offs

- **No per-unit partial writes during execution**: the OTM is written once after all parallel jobs complete (vs after each unit in the sequential model). Progress is still visible via console output per unit.
- **Semaphore required**: uncapped parallelism hits API rate limits. `MAX_PARALLEL = 3` is the default; adjust per provider.
- **asyncio boundary**: `_asyncio.run()` creates a new event loop inside the REPL's synchronous flow. If the REPL is ever made async itself, this needs to change to `await asyncio.gather(...)` directly.
- **Error isolation is per-unit**: a failed component is skipped (logged as warning) rather than aborting the run. The gate catches missing coverage.

### When NOT to parallelize

Units with cross-dependencies must remain sequential. Example: if component B is a downstream consumer of component A's output (e.g. a derived data store), threats for B depend on knowing threats for A. The architect must declare such dependencies explicitly in discovery output for the orchestrator to respect them.

---

## Alternatives considered

**Keep sequential, reduce unit size** — would not fix wall time; smaller units increase total API calls without reducing elapsed time on a slow API.

**CrewAI built-in parallel crew** — CrewAI's `Process.parallel` runs tasks within one crew in parallel, but cannot be used for dynamically-scoped units discovered at runtime. Python-level `asyncio.gather()` is more flexible and explicit.

**Thread pool instead of asyncio** — `ThreadPoolExecutor` would also work but mixes threading and asyncio context poorly when CrewAI uses async internally. `kickoff_async()` is the intended API.
