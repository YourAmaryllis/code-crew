---
type: CrewAI Task
title: Compliance Verification Scan
description: Compliance officer scans for data retention, consent flows, audit trails, and regulatory checklist items
tags: [verify, compliance, gdpr, hipaa, soc2, scan]
agent: compliance_officer
expected_output: >
  Structured list of findings tagged [COMP], each prefixed with FINDING, PASS, or INFO.
  Ends with COMPLIANCE SCAN COMPLETE.
---

Scan the codebase and designs for compliance issues. Use `workspace_reader` to inspect source files and `knowledge_reader` to load active compliance stack guides (gdpr, hipaa, soc2, ccpa, fips-140-3, etc. from `CODE_CREW_STACKS`).

**CRITICAL: All paths must be relative to the project root (`.`). Never use absolute paths. Never navigate above the current working directory.**

**Step 1 — Identify active compliance stacks.**
Check `CODE_CREW_STACKS` env. Load each active compliance stack guide from `knowledge/stacks/`. If no compliance stacks are active, note this and perform a baseline check only.

**Step 2 — Personal data handling.**
Search for models or database columns that likely contain personal data (fields named `email`, `phone`, `name`, `address`, `dob`, `ssn`, `ip_address`, `user_id` in DB schemas or ORM models). For each:
- Is it encrypted at rest? (check migration for column-level encryption or notes in ADD/ADR)
- Is there a retention policy? (check for delete/archive logic tied to a schedule or user request)
- Is there a consent record for collection? (check for consent table or consent flag)

Flag gaps as FINDING.

**Step 3 — Audit trail check.**
For each sensitive operation visible in the codebase (auth events, data exports, admin actions, config changes, financial transactions):
- Verify a log or audit record is written before or after the operation
- Check the log does not contain raw PII (phone, email, SSN in log messages)

**Step 4 — Data subject rights (if GDPR/CCPA active).**
Look for endpoints or handlers that implement:
- Right to access (export user data)
- Right to erasure (delete or anonymise user data)
- Right to portability (data export in machine-readable format)

Flag missing implementations.

**Step 5 — Stack-specific checklist.**
For each active compliance stack:
- **gdpr**: consent records, DPA/DPIA documentation in designs/, lawful basis per data type
- **hipaa**: PHI encryption, BAA documentation, minimum necessary access, breach notification handler
- **soc2**: access control reviews, change management logs, incident response runbook in designs/
- **fips-140-3**: approved cipher suites only (AES-256-GCM, RSA-4096, ECDSA P-384); no MD5/SHA1/DES

**Step 6 — Handle tool failures.**
If any tool call fails: log `ERROR: <tool>(<args>) → <error>`, try once with an alternative, then skip. Never use absolute paths in shell commands. Include a `TOOL FAILURES:` block before the final line if any step was skipped.

**Step 7 — Format findings.**

```
FINDING [COMP]: <one-sentence description> — <file, endpoint, or data field>
PASS [COMP]: <what was checked and found compliant>
INFO [COMP]: <contextual note — not a violation, but relevant>
```

End your output with exactly:
```
COMPLIANCE SCAN COMPLETE
```
