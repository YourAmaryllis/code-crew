---
type: CrewAI Task
title: Threat Mitigations — Per Component (Architect)
description: Architect produces mitigations for one component's threats. All context is provided by Python — no file reads.
tags: [threat, threat-model, otm, architect, mitigations]
agent: architect
expected_output: >
  A `mitigations:` YAML section with at least one mitigation per threat. IDs sequential
  from M-001. Ends with MITIGATIONS COMPLETE.
---

You are the Architect, producing security mitigations for the threats targeting ONE component (provided above).

**CRITICAL — READ BEFORE ACTING:**

1. **Do NOT call any tools.** Do NOT use `workspace_reader`, `code_index`, `platform_shell`,
   or `knowledge_reader`. ALL context is already provided in this task description.
   Calling any tool will time out the run.

2. **Produce at least one mitigation per threat.** One mitigation may cover multiple threats
   if the same control addresses them.

3. **Use `state: implemented` ONLY** if the context explicitly states the control is already
   in place (e.g. "mTLS confirmed in Terraform", "JWT validated in entry point").
   Otherwise use `state: planned`.

4. **Output ONLY the `mitigations:` YAML section — no prose, no other sections.**

5. **Use sequential IDs starting from M-001.**

6. **End with exactly:** `MITIGATIONS COMPLETE`

---

## Output format

```yaml
mitigations:
  - id: M-001
    name: "<control name>"
    description: "<what the control does — one sentence>"
    risk:
      likelihood: LOW|MEDIUM|HIGH
      impact: LOW|MEDIUM|HIGH
    state: implemented|planned
    mitigatedThreats: [T-001, T-002]
```

**Notes:**
- `risk` reflects **residual** risk after the mitigation is applied
- `mitigatedThreats` is always a list; minimum one entry
- A single mitigation can address multiple threats — prefer this for related controls

**YAML rules:**
- Strings containing `:`, `#`, `[`, `]`, `{`, `}` MUST be quoted
- `likelihood` and `impact` are always `key: VALUE` — never bare scalars

---

## When you finish

After the last mitigation entry, output exactly:

```
MITIGATIONS COMPLETE
```

No other text after this line.
