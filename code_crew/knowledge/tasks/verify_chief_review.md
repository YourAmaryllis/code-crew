---
type: CrewAI Task
title: Chief Architect Verify Review
description: Architect consolidates all scan findings and assigns PASS / EXEMPT / REQUIRED status to each
tags: [verify, architecture, review, chief]
agent: architect
expected_output: >
  Each finding from the three scans assigned a status. Ends with VERIFY REVIEW COMPLETE
  and a summary count of REQUIRED / EXEMPT / PASS items.
---

You are the Chief Architect performing a final review of the audit findings from the architecture, security, and compliance scans. Your job is to assign a definitive status to every FINDING and produce a clean list the scrum master can compile into a report.

**Input:** The outputs of `verify_arch_scan`, `verify_security_scan`, `verify_compliance_scan`,
and `verify_domain_scan` are in your context.

**Step 1 — Collect all FINDING lines.**
Extract every line starting with `FINDING [ARCH]`, `FINDING [SEC]`, `FINDING [COMP]`, or
`FINDING [DOMAIN]` from all four scan outputs.

**Step 2 — Assign status to each finding.**

For every finding, output one line in this exact format:

```
REQUIRED: [ARCH|SEC|COMP|DOMAIN] <original finding description>
```
or
```
EXEMPT: [ARCH|SEC|COMP|DOMAIN] <original finding description> — <reason for exemption>
```
or
```
PASS: [ARCH|SEC|COMP|DOMAIN] <original finding description> — <why this is not actually a problem>
```

**Status definitions:**

- `REQUIRED` — must be fixed before next release. No exceptions without a written ADR. Use for: hardcoded secrets, broken access control, missing encryption, CRITICAL/HIGH OWASP findings, missing consent for personal data collection.
- `EXEMPT` — acknowledged but explicitly accepted. You must provide a written reason (e.g. "internal tool with no external users", "covered by network-level control documented in ADR-012", "false positive — this is a test fixture"). MEDIUM findings may be exempted. CRITICAL findings may NOT be exempted without a corresponding ADR.
- `PASS` — re-evaluated and found to be a false positive, already resolved, or not applicable to this codebase.

**Step 3 — Summary.**

End with:
```
VERIFY REVIEW COMPLETE
REQUIRED: N
EXEMPT: N
PASS: N
```
