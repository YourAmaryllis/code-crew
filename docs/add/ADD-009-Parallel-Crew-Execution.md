# ADD-009: Parallel Crew Execution

**Status:** Accepted  
**Date:** 2026-07-04  
**Related:**
- [ADR-009: Parallel Per-Unit Agent Execution](../adr/ADR-009-Parallel-Per-Unit-Agent-Execution.md)
- [ADD-008: Incremental Per-Unit LLM Decomposition](ADD-008-Incremental-Per-Unit-LLM-Decomposition.md)

---

## Purpose

Define how to execute per-unit crews in parallel within the Python outer loop established by ADD-008. This document covers: the async execution model, rate-limit bounding, combined single-pass tasks, and the extension path to parallel engineering agents.

---

## Parallel execution model

### Requirements for a unit to be parallelisable

A unit is safe to run in parallel when:

1. **No cross-unit dependency within the phase** — unit A's analysis does not need unit B's result
2. **Idempotent context** — each unit receives only its own pre-assembled context; no shared mutable state
3. **Independent output** — results are collected into a list; insertion order is preserved by sorting on original index

Threat/mitigation analysis per component satisfies all three. Engineering tasks per file module satisfy (2) and (3) but may violate (1) if module B imports module A — see [Engineering parallelism](#engineering-agents-in-parallel) below.

### Implementation

```python
import asyncio

_MAX_PARALLEL = 3  # tune per provider rate limit

async def _run_all_parallel(components, build_crew_fn, context):
    sem = asyncio.Semaphore(_MAX_PARALLEL)

    async def _guarded(comp, idx):
        async with sem:
            crew = build_crew_fn(comp, context)
            try:
                result = await crew.kickoff_async()
            except Exception as exc:
                console.print(f"[yellow]  {comp['id']}: failed ({exc}) — skipping[/yellow]")
                return idx, [], []
            threats = _parse_yaml_section(result.raw, "threats")
            mits    = _parse_yaml_section(result.raw, "mitigations")
            return idx, threats, mits

    tasks = [_guarded(c, i) for i, c in enumerate(components)]
    results = await asyncio.gather(*tasks)
    # sort preserves original discovery order in OTM
    return sorted(results, key=lambda x: x[0])

all_results = asyncio.run(_run_all_parallel(components, build_threat_component_crew, ctx))
```

Key points:
- `kickoff_async()` is CrewAI's async kickoff — returns a coroutine
- `asyncio.Semaphore(_MAX_PARALLEL)` caps concurrent API calls
- `return_exceptions` is handled per-unit via try/except (not `gather(..., return_exceptions=True)`) so each failure produces a warning rather than an exception tuple
- Results are sorted by original index before accumulation so OTM component ordering matches discovery order

### Semaphore tuning

| Provider | Recommended `MAX_PARALLEL` |
|---|---|
| NVIDIA Build free tier | 3 |
| AWS Bedrock on-demand | 5–10 |
| OpenAI | 5–10 |

Set via config key `flow.max_parallel_components` (future); hardcoded to 3 for now.

---

## Combined single-pass task (threats + mitigations)

The previous two-phase approach forced Phase 3 to wait for all Phase 2 calls to complete before beginning. Since a component's mitigations only need that same component's threats (generated in Phase 2), the two phases can be collapsed:

```
Sequential (before):
  Phase 2: comp-A threats → comp-B threats → comp-C threats
  Phase 3: comp-A mits   → comp-B mits   → comp-C mits

Combined + parallel (after):
  Round 1 (parallel): comp-A, comp-B, comp-C → each outputs threats + mits
```

The task file (`threat_component.md`) asks the agent to output `threats:` first, then `mitigations:` for those same threats. This is self-consistent: the agent can reference T-NNN IDs it just wrote in the same generation window.

**Output format contract:**
```yaml
threats:
  - id: T-001
    ...

mitigations:
  - id: M-001
    mitigatedThreats: [T-001, T-002]
    ...

COMPONENT COMPLETE
```

Python extracts both sections with `_parse_yaml_section(result.raw, "threats")` and `_parse_yaml_section(result.raw, "mitigations")`.

---

## ID management across parallel units

Threat IDs must be globally sequential in the assembled OTM (T-001 through T-NNN across all components). With parallel execution, IDs cannot be assigned dynamically (each unit doesn't know how many threats the preceding units will generate).

**Solution: pre-assign ID ranges, renumber at assembly.**

Each component is pre-assigned a `threat_id_start` offset with a generous stride (e.g. 10 per component). After all parallel units complete, `assemble_otm_yaml` renumbers threats and mitigations sequentially and updates all cross-references (`mitigatedThreats`, `targetedComponents`).

```python
# Pre-assign starts (generous stride)
starts = [1 + i * 10 for i in range(len(components))]

# Assembly renumbers: T-001, T-002, ... regardless of per-unit IDs
yaml_text = assemble_otm_yaml(project, zones, components, all_threats, all_mitigations, stacks, today)
```

This means within-unit `mitigatedThreats` references (e.g. `M-001 → T-003`) are correct at generation time, and `assemble_otm_yaml` updates them to final global IDs.

---

## Engineering agents in parallel

The same pattern applies to engineering tasks (implementation, scaffold, test authoring) where work can be partitioned by module or file set.

### Preconditions

The **Architect must partition the task** during sprint planning or task decomposition, producing explicit non-overlapping assignments:

```yaml
partitions:
  - engineer: A
    files: [auth/, shared/types.go]
  - engineer: B
    files: [billing/, shared/billing_types.go]
```

Rules:
- Partitions must be **file-disjoint** — no two engineers write to the same path
- Shared interfaces (e.g. `shared/types.go`) go to exactly one engineer; others get a read-only copy injected as context
- Files that don't exist yet (new feature) are safe to partition freely

### Merge step

After all parallel engineers complete, a **merge agent** (or Python-level file concatenation for non-overlapping changes) integrates the output:

```
Parallel engineers → individual file changesets
Merge agent        → resolves shared type mismatches, updates imports
Gate               → code review on assembled result
```

The merge agent receives all changesets and the original task context. Its only job is consistency: ensure types referenced across partitions match, update import paths, and flag conflicts for human review.

### When NOT to parallelize engineering tasks

- The task modifies a single central file (e.g. a monolithic route handler)
- Module B's implementation genuinely depends on the types module A will introduce
- The codebase uses code generation (protobuf, OpenAPI) — generated files create hidden dependencies

For these cases, use the standard sequential implementation task.

---

## Implementation checklist

When adding a new parallel phase to a flow:

- [ ] Units satisfy the three parallelism requirements (no cross-dependency, idempotent context, independent output)
- [ ] Combined single-pass task file outputs both sections + completion marker
- [ ] `asyncio.Semaphore(_MAX_PARALLEL)` bounds concurrent calls
- [ ] Per-unit errors are caught and logged; they do not abort `asyncio.gather()`
- [ ] Results sorted by original index before accumulation
- [ ] `assemble_*` function renumbers IDs and updates cross-references after collection
- [ ] OTM written once after all units complete (not per-unit)
- [ ] Gate receives fully assembled output
