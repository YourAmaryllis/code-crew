---
type: skill
name: strict
description: Maximum review rigor — every gate requires explicit evidence, no rubber-stamping
---

## Review rules — strict mode

You are in strict mode. Gates are real blockers, not formalities.

**Approval requires:**
- Explicit PASS or FAIL for every checklist item — "looks good" is not evidence
- For PASS: state what you checked and what you found (e.g., "No raw SQL concatenation — all queries use parameterized statements via sqlx at db/user.go:34")
- Minimum evidence threshold: one specific code location per checklist item

**Every BLOCKED finding must include:**
1. Severity: CRITICAL / HIGH / MEDIUM
2. Location: `path/file:line` or `path/file:function`
3. Description: what the vulnerability or violation is (one sentence)
4. Required fix: exactly what must change before APPROVED

**Forbidden:**
- APPROVED with generic phrases like "the code looks clean", "no obvious issues", "generally good"
- Deferring a CRITICAL or HIGH finding to a follow-up ticket
- APPROVED when any finding is unresolved

**Security standard in strict mode:**
- Apply OWASP ASVS Level 3 (not Level 2)
- Every new dependency must have an explicit CVE check result
- Threat model must cover all new data flows — no "stub to be completed"

**Gate thresholds:**
- CRITICAL: always blocks, no exceptions
- HIGH: blocks unless explicitly exempted by the Chief Architect with a written justification in the task output
- MEDIUM: must be logged as a follow-up ticket before APPROVED
