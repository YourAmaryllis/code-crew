---
type: CrewAI Task
title: Compliance Verification Scan
description: Compliance officer audits PII handling, audit trail, and regulatory framework coverage using at most 4 file reads with immediate per-file output
tags: [verify, compliance, gdpr, hipaa, soc2, scan]
agent: compliance_officer
expected_output: >
  Structured list of findings tagged [COMP], each prefixed with FINDING, PASS, or INFO.
  Every checked item — whether clean or not — gets a line. Ends with COMPLIANCE SCAN COMPLETE.
---

Scan for compliance issues. Use `workspace_reader` throughout.

**CRITICAL: All paths must be relative to `.`. Never use absolute paths.**
**CRITICAL: At most 4 file reads total. Output a FINDING or PASS line IMMEDIATELY after
reading each file — do not accumulate results and output them all at the end.**
**CRITICAL: Do not make another tool call after you have output all findings from the last
file you read. If you have nothing more to read, write your summary and stop.**

---

**Step 1 — Standards in scope (no tool calls needed).**

Your task context includes `## Compliance standards` from `.code-crew/structure.md`.
Use those standards. If the section is absent, assume: HIPAA, SOC 2, GDPR, CCPA.

Output one line per standard:
```
INFO [COMP]: Compliance standard in scope — <standard>
```

---

**Step 2 — PII model check (1 file read).**

Read this exact file: `portal/backend/internal/user/user.go`

After reading it, immediately scan the content for struct fields or db/json tags containing:
`email`, `phone`, `name`, `address`, `dob`, `ssn`, `ip_address`, `first_name`, `last_name`

For EACH PII field found, output ONE line immediately:
- No encryption or deletion logic visible in file: `FINDING [COMP]: PII field '<field>' collected without documented encryption or retention — portal/backend/internal/user/user.go [MEDIUM]`
- Encryption/deletion logic visible: `PASS [COMP]: PII field '<field>' has protection controls — portal/backend/internal/user/user.go`

If file does not exist or has no PII fields: `INFO [COMP]: No PII model fields found in portal/backend/internal/user/user.go`

Then output this line immediately: `INFO [COMP]: PII model check done`

---

**Step 3 — Audit trail check (1 file read).**

Read this exact file: `portal/backend/internal/auditevent/event.go`

After reading it, immediately output:
- File exists and defines audit event types: `PASS [COMP]: Audit event system present — portal/backend/internal/auditevent/event.go`
- File exists but appears minimal/empty: `FINDING [COMP]: Audit event file exists but appears minimal — may not cover all sensitive operations [LOW]`
- File does not exist: `FINDING [COMP]: No audit event system found in portal/backend/internal/ — sensitive operation logging not verified [MEDIUM]`

Then output: `INFO [COMP]: Audit trail check done`

---

**Step 4 — Regulatory framework documentation (1 file read).**

Read this exact file: `designs/SOP/SOP-8-Compliance.md`

After reading it, for each standard that was in scope (from Step 1), output ONE line:
- SOP addresses the standard: `PASS [COMP]: <standard> controls documented in designs/SOP/SOP-8-Compliance.md`
- SOP does not address the standard: `FINDING [COMP]: <standard> controls not documented in compliance SOP [MEDIUM]`
- If file does not exist: `FINDING [COMP]: No compliance SOP found at designs/SOP/SOP-8-Compliance.md [HIGH]`

Then output: `INFO [COMP]: SOP documentation check done`

---

**Step 5 — Data subject rights check (1 file read).**

If GDPR or CCPA is in scope, read `designs/ADD/` directory listing (not individual files).
Check whether any ADD filename mentions: `data-subject`, `right-to-delete`, `erasure`,
`right-to-know`, `privacy`, `opt-out`, `data-export`.

- ADD found: `PASS [COMP]: Data subject rights ADD documented — <filename>`
- No ADD found: `FINDING [COMP]: No data subject rights design document found in designs/ADD/ — GDPR/CCPA right-to-erasure not documented [MEDIUM]`

If GDPR and CCPA both not in scope: `PASS [COMP]: Data subject rights check — not in scope`

---

**Step 6 — Stop and format.**

Do NOT read any more files after Steps 2–5. Write your final output:

```
FINDING [COMP]: <one-sentence description> — <file or component>  [CRITICAL|HIGH|MEDIUM|LOW]
PASS [COMP]: <what was checked and found compliant>
INFO [COMP]: <contextual note>
```

End with exactly:
```
COMPLIANCE SCAN COMPLETE
```
