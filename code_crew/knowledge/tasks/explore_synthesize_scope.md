---
type: CrewAI Task
title: OTM Scope Synthesis
description: Given component summaries, decide what OTM files to produce. No tools.
tags: [explore, synthesis, scope, otm]
agent: architect
expected_output: >
  One PROJECT block per OTM file. Ends with OTM SCOPE COMPLETE.
---

**DO NOT USE ANY TOOLS. All information needed is already in the context above.**

The context contains:
- **Service summaries** — what each service does, its type, and sensitivity
- **Domain summaries** — subdomain capabilities and whether each warrants a separate OTM
- **Infrastructure modules** — deployment units (a domain matching a module has its own infra)
- **Git submodules** — directories managed as separate repos

Decide which OTM files to produce and output PROJECT blocks only — no narrative.

---

## Include

Services with `TYPE: deployable-service` get their own OTM, unless:
- They are a git submodule not owned by this project
- Their name suggests test/demo/tooling (`integration`, `bdd`, `demo`, `test`, `scripts`, `tools`)

Domains with `SEPARATE_OTM: yes` get their own OTM.

## Exclude

- `TYPE: test-suite`, `TYPE: infra-only`, `TYPE: library`
- Git submodule directories (listed in the `.gitmodules` section of context) unless
  their summary says they are a deployable service owned by this project
- Services whose PURPOSE summary says "pilot", "client", "data registration", "one-time", or "manual"

## Sub-executables

Assign each sub-executable to the PROJECT that owns its parent service directory.
List them under `COMPONENTS:`.

---

## Output format

```
PROJECT: <id>
DESCRIPTION: <1-2 sentence plain-English scope for a security auditor>
COMPONENTS: <comma-separated: service dirs, sub-executables, domain dirs in this OTM>
```

**id rules**: use the primary code directory name exactly. Lowercase, hyphens or underscores
only. For a domain OTM, use the domain directory name (not `service-domain`).

End with exactly:
```
OTM SCOPE COMPLETE
```
