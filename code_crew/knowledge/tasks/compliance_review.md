---
type: CrewAI Task
title: Compliance Review
description: Regulatory compliance review against active frameworks (HIPAA, SOC2, GDPR, CCPA, CFR Part 11, NIST) with CRD alignment and audit evidence check
tags: [compliance, hipaa, soc2, gdpr, ccpa, cfr-part-11, nist, crd, audit-evidence, phase-19]
timestamp: 2026-06-26T00:00:00Z
agent: compliance_officer
context_agents:
  - engineer
  - security_lead
expected_output: >
  A Compliance Review Report with: per-framework scope assessment, per-section verdicts
  (PASS/FAIL with evidence), CRD alignment status, audit evidence gaps, and a final gate
  (COMPLIANT / NON-COMPLIANT with full blocker list per framework). Technical security
  findings are reported separately by the security lead.
---

Review the implementation for regulatory compliance against all active frameworks.
Technical security (OWASP, FIPS 140-3, IAM, Threat Dragon) is covered by the security
lead — your scope is regulatory obligations.

**Step 1 — Determine active compliance frameworks**

Use `knowledge_reader` to identify active stacks. Load each active framework's checklist:

| Stack | Document |
|-------|---------|
| `hipaa` | `hipaa` |
| `soc2` | `soc2` |
| `gdpr` | `gdpr` |
| `ccpa` | `ccpa` |
| `cfr-part-11` | `cfr-part-11` |
| `nist` | `nist` |

Also load:
- Feature ADD (from Jira ticket references) for data flow context
- Any CRD from `designs/CRD/` relevant to this feature area
- `jira_view` to understand what data the feature handles and its regulatory scope

If no regulatory stacks are active: output **COMPLIANT — no regulatory frameworks configured**.

**Step 2 — Scope assessment**

State clearly:
- What data does this feature handle? (personal data, PHI, regulated records, etc.)
- Which jurisdictions/regulations apply?
- Is this feature part of a regulated workflow?
- Does this change affect existing compliance posture in a CRD?

**Step 3 — Framework checks**

For each active framework, work through its checklist section by section.
For every FAIL record:
- Framework and section reference (e.g. HIPAA §164.312(b))
- Severity: Critical / High (block merge) or Medium (advisory)
- File and location, or which document/config is missing
- The specific requirement and how the implementation falls short
- Required fix

**Step 4 — CRD alignment**

If a CRD applies to this feature:
- Does the implementation satisfy all CRs in scope for this story?
- Flag any CR this feature touches that is unaddressed
- Flag any CR marked "not implemented" that should have been satisfied here

**Step 5 — Audit evidence check**

- Jira ACs trace to compliance requirements (or flag gap)
- CI artefacts include test results and dependency scan for this PR
- If CFR Part 11 active: change control record exists for this change
- If SOC2 active: change is traceable to ticket and was code-reviewed

**Final gate**: COMPLIANT (no Critical/High findings) or NON-COMPLIANT (list each: framework, section, severity, location, required fix).

If no frameworks active: **COMPLIANT — no regulatory frameworks configured**.
If tools unavailable: `INCOMPLETE: <reason>`.
