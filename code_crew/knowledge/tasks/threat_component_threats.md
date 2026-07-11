---
type: CrewAI Task
title: Threat Identification — Single Component (Architect)
description: Architect identifies all threats for ONE component. All context is provided by Python — no file reads.
tags: [threat, threat-model, otm, architect, stride, linddun, die, plot4ai]
agent: architect
expected_output: >
  A `threats:` YAML section covering the specified component, with sequential IDs
  starting from the value in `## Threat ID start`. Ends with THREATS COMPLETE.
---

You are the Architect, analysing ONE component for security threats.

**CRITICAL — READ BEFORE ACTING:**

1. **Do NOT call any tools.** Do NOT use `workspace_reader`, `code_index`, `platform_shell`,
   or `knowledge_reader`. ALL context is already provided in this task description.
   If you call any tool, you will time out before producing output.

2. **Focus ONLY on the component named in `## Component to analyse`.**
   Do not analyse other components — they are listed for context only.

3. **Use sequential threat IDs starting from the value in `## Threat ID start`.**
   If the start value is 5, your IDs are T-005, T-006, T-007, etc.

4. **Output ONLY the `threats:` YAML section — no prose, no other sections.**

5. **End with exactly:** `THREATS COMPLETE`

---

## Framework selection

Apply ALL frameworks that match this component's type — do not limit to one:

| Framework | Apply when |
|-----------|-----------|
| **STRIDE** | Always — for every component |
| **LINDDUN** | `phi_involved: true` in component attributes |
| **DIE** | type is `ecs-task` or `lambda` |
| **PLOT4ai** | Component description or dependency manifest mentions AI/LLM/ML libraries |

---

## Minimum coverage (REQUIRED)

You must include at least these categories. Missing any is a gate-rejection reason.

| Component type | Required threat categories |
|---------------|---------------------------|
| Public-facing service (`service` with public trust zone) | Spoofing, Tampering, Information Disclosure, Denial of Service |
| Data store (`database`, `queue`) | Tampering, Information Disclosure, Repudiation |
| Container/serverless (`ecs-task`, `lambda`) | Distributed, Immutable, Ephemeral (DIE framework) |
| LLM/AI component | Output Control, Security Breach, Privacy Violation, Accountability (PLOT4ai) |
| PHI-handling component | LINDDUN: Unlawful retention, Inadequate audit log, Cross-border transfer, Re-identification |
| Actor (external user, system) | Spoofing, Repudiation |

---

## Output format

```yaml
threats:
  - id: T-NNN
    name: "<threat name>"
    description: "<what goes wrong and the impact — one or two sentences>"
    categories:
      - <Framework Category>
    risk:
      likelihood: HIGH|MEDIUM|LOW
      impact: HIGH|MEDIUM|LOW
    targetedComponents: [<component-id>]
    targetedAssets: [<asset-id>]
```

**YAML rules:**
- Strings containing `:`, `#`, `[`, `]`, `{`, `}` MUST be quoted
- `likelihood` and `impact` are always `key: VALUE` — never bare scalars
- `targetedComponents` and `targetedAssets` are always lists (use `[]` if empty)

---

## When you finish

After the last threat entry, output exactly:

```
THREATS COMPLETE
```

No other text after this line.
