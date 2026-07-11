---
type: CrewAI Task
title: Compliance Synthesis
description: Given component summaries and Python-detected compliance signals, confirm compliance standards. No tools.
tags: [explore, synthesis, compliance]
agent: architect
expected_output: >
  DISCOVERY_BEGIN/END compliance_standards block listing confirmed and unconfirmed standards.
  Ends with COMPLIANCE COMPLETE.
---

**DO NOT USE ANY TOOLS. All information needed is already in the context above.**

The context contains:
- **Component summaries** — SENSITIVITY fields (phi, pii, financial, public, none)
- **Python-detected compliance standards** — keyword scan results from designs/ and docs/

Use the sensitivity flags from summaries to confirm or add compliance standards.

---

## Rules

- `SENSITIVITY: phi` in any summary → HIPAA is applicable
- `SENSITIVITY: pii` in any summary → check if GDPR/CCPA are already detected; flag if not
- `SENSITIVITY: financial` in any summary → check if PCI-DSS is already detected; flag if not
- Python-detected standards take precedence — if Python found it in docs, it is confirmed
- Only add a standard if a summary sensitivity flag clearly supports it

---

## Output

```
DISCOVERY_BEGIN: compliance_standards
## Compliance standards

**Confirmed**:
- <STANDARD> — <reason: detected in designs/ OR inferred from PHI/PII sensitivity in <service>>

**Not applicable** (no evidence found):
- <STANDARD>
DISCOVERY_END: compliance_standards
```

Output exactly:
```
COMPLIANCE COMPLETE
```
