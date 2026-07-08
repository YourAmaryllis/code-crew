# ADD-011: Multi-Pass Threat Model Refinement

**Status:** Accepted
**Date:** 2026-07-07
**Related:**
- [ADD-008: Incremental Per-Unit LLM Decomposition](ADD-008-Incremental-Per-Unit-LLM-Decomposition.md)
- [ADD-009: Parallel Crew Execution](ADD-009-Parallel-Crew-Execution.md)
- [EVAL-003: InfosecOTB threat-dragon-ai-tool](../eval/EVAL-003-threat-dragon-ai-tool.md)

---

## Purpose

Extend the `/threat` flow with one or more refinement passes that run over the fully assembled OTM after the ADD-008 per-unit pipeline completes. Each refinement pass reads the complete OTM and outputs only the additional threats and mitigations missing from prior passes — closing the gap that per-component analysis leaves around cross-component threats and compound framework coverage.

---

## Problem

ADD-008's per-unit pattern keeps each LLM call small and bounded — one component per Phase 2 call, one component per Phase 3 call. This is the right design for avoiding context overflows and 504 timeouts. But it has a structural blind spot: **the agent analysing component A cannot see component B's threats** because B's output isn't injected into A's call context.

The threats that fall into this blind spot are systematically the highest-impact ones:

| Gap | Why it's missed |
|---|---|
| Trust boundary crossing threats | Require knowing both the source component's zone and the destination component's zone simultaneously |
| Threat chaining | Attacker exploits T-001 on component A to pivot to component B for T-019; each component's per-unit call sees only its own threats |
| Compound framework gaps | A component tagged `phi_involved: true` and `type: ecs-task` needs both LINDDUN and DIE coverage; the per-unit agent might produce STRIDE + one framework and miss the other |
| Missing dataflow threats | Zone-crossing dataflows that appear in both the source and destination component's context but aren't fully owned by either |

The gate (`threat_gate`) catches these as NEEDS REVISION items, which triggers `threat_patch` to fix them. But patching cross-component gaps requires reading the full OTM anyway — so the current design effectively does a second pass, just with the overhead of a gate failure and a patch delegation. Making this a deliberate first-class pass is cleaner and more reliable.

---

## Pattern

### Full flow with refinement

```
Python outer loop (/threat)
│
├── Phase 1 — Discovery  (threat_discover: trust zones + component inventory)
│
├── Phase 2 — Per-component threats  (threat_component_threats × N, ADD-008)
│
├── Phase 3 — Per-component mitigations  (threat_mitigations × N, ADD-008)
│
├── Assembly — Python renumbers IDs, writes initial OTM YAML to disk
│
├── Refinement passes  (threat_refine × max_refine_passes)
│     Input: complete assembled OTM from prior pass
│     Output: additional_threats: + additional_mitigations: YAML sections
│     Stopping criterion: "NO NEW THREATS" signal OR pass count reached
│     → Python merges additions, renumbers, overwrites OTM on disk
│
└── Gate  (threat_gate: completeness check on final OTM)
      Revision loop  (threat_patch if NEEDS REVISION — retries gate only)
```

### What a refinement pass does

The `threat_refine` task receives the **complete assembled OTM YAML** as context and outputs only what's missing. It does not regenerate existing threats or rewrite the OTM — it appends.

Focus areas for the refinement agent:

1. **Zone-boundary dataflow threats** — for every dataflow that crosses a trust boundary, verify at least one threat captures the crossing (Spoofing or Information Disclosure at the boundary). If missing, add it.

2. **Threat chaining** — identify any pair (T-X on component A, T-Y on component B) where T-X provides the attacker the access needed to execute T-Y. Document as a compound threat on the chain's entry point component.

3. **Compound framework gaps** — scan all components for missing framework coverage given their attributes:
   - `phi_involved: true` → LINDDUN threats required
   - `type: ecs-task | lambda` → DIE threats required
   - AI/LLM component (per component description or deployment) → PLOT4ai threats required

4. **Unconnected component threats** — components with `standalone_reason` are not threat-free; verify they have at least the minimum coverage for their type.

### Output contract

```yaml
additional_threats:
  - id: TR-001          # TR- prefix to avoid collision with T- IDs from pass 1
    name: <name>
    description: <what can go wrong and impact>
    categories:
      - <Framework Category>
    risk:
      likelihood: HIGH|MEDIUM|LOW
      impact: HIGH|MEDIUM|LOW
    targetedComponents: [<component-id>]
    targetedAssets: [<asset-id>]

additional_mitigations:
  - id: MR-001          # MR- prefix
    name: <name>
    description: <control>
    risk:
      likelihood: LOW|MEDIUM|HIGH
      impact: LOW|MEDIUM|HIGH
    state: implemented|planned|not-applicable
    mitigatedThreats: [TR-001]

REFINEMENT COMPLETE
```

If no new threats are found:

```
NO NEW THREATS
REFINEMENT COMPLETE
```

### Python merge step

After each refinement pass, Python:

1. Parses `additional_threats:` and `additional_mitigations:` sections using `_parse_yaml_section`
2. Renames IDs from `TR-NNN` / `MR-NNN` to sequential continuation of the existing `T-NNN` / `M-NNN` series
3. Updates all internal references (`mitigatedThreats`, `targetedComponents`) to match renamed IDs
4. Appends the new items to `threats:` and `mitigations:` in the OTM
5. Overwrites the OTM file on disk
6. Checks for the `NO NEW THREATS` signal — if present, stops early regardless of remaining passes

---

## Configuration

```yaml
# ~/.code-crew/config.yaml
threat:
  max_refine_passes: 2    # default: 2; set to 0 to disable refinement
```

`max_refine_passes: 1` is the minimum meaningful value. `max_refine_passes: 0` disables the feature entirely, reverting to the ADD-008 pipeline with gate-only quality control. Default of 2 balances coverage with token cost — the first refinement pass catches most cross-component gaps; the second catches chaining scenarios that only become visible after the first pass's additions are in place.

---

## `/threat refine` — manual refinement command

In addition to automatic passes after initial generation, a `/threat refine` command triggers a single additional refinement pass on the current OTM on disk. This supports the InfosecOTB-style workflow where the human reviews the output and asks for another pass without re-running the full pipeline.

```
/threat refine         # one additional pass over designs/TMD/<project>.otm.yaml
/threat refine 3       # three additional passes
```

The command reads the existing OTM, runs `threat_refine` once (or N times), merges the output, and overwrites the OTM. No re-discovery, no per-component re-analysis, no gate re-run unless explicitly requested.

---

## Token cost

Each refinement pass is a single LLM call with the complete OTM as input. OTM size scales with component count:

| Components | OTM size (approx) | Refinement call input |
|---|---|---|
| 5–10 | ~4k tokens | ~5k tokens (OTM + task) |
| 15–25 | ~10k tokens | ~12k tokens |
| 30–50 | ~20k tokens | ~22k tokens |

This is well within NVIDIA Build and Bedrock per-call limits and avoids the 504 timeout risk that prompted ADD-008's per-unit decomposition in the first place — because the refinement call is one bounded call on a fixed-size artifact, not an open-ended generative loop.

For `max_refine_passes: 2`, total refinement cost is 2 × (one call at OTM size). For a 20-component system this adds approximately 25k tokens across two passes — roughly the cost of two per-unit Phase 2 calls.

---

## New knowledge files

| File | Purpose |
|---|---|
| `code_crew/knowledge/tasks/threat_refine.md` | `threat_refine` task — reads full OTM, outputs `additional_threats:` + `additional_mitigations:` |

No new agent is required. The refinement task runs on the Security Lead agent (the same agent that owns the threat modeling session).

---

## Changes to existing files

| File | Change |
|---|---|
| `code_crew/flow.py` | Add `ThreatFlow._refinement_passes()` method; call after assembly, before gate |
| `code_crew/flow.py` | Add `ThreatFlow._merge_refinement()` static method for ID renaming + OTM merge |
| `code_crew/startup.py` | Wire `/threat refine [N]` command |
| `.config.example.yaml` | Document `threat.max_refine_passes` key |
| `CLAUDE.md` | Document refinement in the task sequence table |

The `threat_gate` and `threat_patch` tasks are unchanged — they operate on the final assembled OTM regardless of how many refinement passes ran.

---

## Implementation checklist

- [ ] Write `code_crew/knowledge/tasks/threat_refine.md` with the output contract above
- [ ] Add `threat.max_refine_passes` to `.config.example.yaml` (default: 2)
- [ ] Add `ThreatFlow._refinement_passes(otm_path, n)` in `flow.py`
  - Calls `threat_refine` task with full OTM text as context
  - Parses `additional_threats:` and `additional_mitigations:` via `_parse_yaml_section`
  - Stops early on `NO NEW THREATS`
  - Calls `_merge_refinement()` after each pass
- [ ] Add `ThreatFlow._merge_refinement(otm: dict, additions: dict) -> dict` in `flow.py`
  - Renames `TR-NNN` → continuation of existing `T-NNN` series
  - Renames `MR-NNN` → continuation of existing `M-NNN` series
  - Updates all cross-references
- [ ] Call `_refinement_passes()` after assembly and before gate in `ThreatFlow.run()`
- [ ] Wire `/threat refine [N]` in `startup.py` — reads existing OTM, runs N passes, writes back
- [ ] Update `CLAUDE.md` task sequence to show refinement step
