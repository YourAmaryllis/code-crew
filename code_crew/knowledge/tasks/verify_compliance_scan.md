---
type: CrewAI Task
title: Compliance Verification Scan
description: Compliance officer reads detected standards from structure.md then audits the codebase against each applicable framework
tags: [verify, compliance, gdpr, hipaa, soc2, scan]
agent: compliance_officer
expected_output: >
  Structured list of findings tagged [COMP], each prefixed with FINDING, PASS, or INFO.
  Every checked item — whether clean or not — gets a line. Ends with COMPLIANCE SCAN COMPLETE.
---

Scan the codebase and designs for compliance issues. Use `workspace_reader` to inspect source
files and designs documents.

**CRITICAL: All paths must be relative to the project root (`.`). Never use absolute paths.**

---

**Step 1 — Identify applicable compliance standards.**

Read the `## Compliance standards` section from the project structure in your context (loaded
from `.code-crew/structure.md`). This section was produced by `/explore` and lists which
regulatory frameworks were detected in designs/ and docs/.

If the structure context does not contain a `## Compliance standards` section, scan yourself:
use `workspace_reader` to read `designs/SOP/` and `designs/ADR/` files and look for mentions of:
HIPAA, PHI, SOC 2, GDPR, CCPA, PCI-DSS, FIPS.

For each standard detected, run the checklist in Step 5.
If **no** standards are detected after checking, output:
```
INFO [COMP]: No compliance frameworks detected in designs/ or docs/ — running baseline check only
```
Then run Step 2 and Step 3 only.

---

**Step 2 — Personal data handling (all projects).**

Search for models or database columns that likely contain personal data (fields named `email`,
`phone`, `name`, `address`, `dob`, `ssn`, `ip_address`, `user_id` in DB schemas or ORM models).
For each:
- Is it encrypted at rest? (check migration for column-level encryption or ADD/ADR notes)
- Is there a retention policy? (delete/archive logic tied to a schedule or user request)
- Is there a consent record for collection? (consent table or consent flag)

Output a FINDING for each gap, or a PASS if all checks are clean.

---

**Step 3 — Audit trail check (all projects).**

For each sensitive operation visible in the codebase (auth events, data exports, admin actions,
config changes, financial transactions):
- Verify a log or audit record is written before or after the operation
- Check the log does not contain raw PII (phone, email, SSN in log messages)

---

**Step 4 — Data subject rights (GDPR or CCPA).**

If GDPR or CCPA is in scope, look for endpoints or handlers implementing:
- Right to access / right to know (export user data)
- Right to erasure (delete or anonymise user data)
- Right to portability (data export in machine-readable format)

Check designs/ADD/ for documented data subject request flows.
If GDPR/CCPA not in scope: output `PASS [COMP]: Data subject rights check — not in scope (GDPR/CCPA not detected)`.

---

**Step 5 — Per-standard checklists.**

Run only the checklists for standards detected in Step 1.

### HIPAA checklist
1. **PHI encryption at rest** — grep for encryption at column or field level for health data
2. **PHI in transit** — check that HTTPS is enforced and no health data flows over plain HTTP
3. **Minimum necessary access** — check that health data queries include scoping (e.g. by patient/provider)
4. **BAA documentation** — check designs/ for a Business Associate Agreement or BAA reference
5. **Breach notification handler** — look for incident response or breach notification code/SOP
6. **Audit log for PHI access** — verify access to health records is logged

Output one PASS or FINDING line per item.

### SOC 2 checklist
1. **Access control reviews** — check designs/SOP/ for access review SOP
2. **Change management** — check for PR-based deployment gates or approved change management SOP
3. **Incident response runbook** — check designs/SOP/ for an IR runbook
4. **Monitoring / alerting** — look for references to alerting tools (PagerDuty, OpsGenie, CloudWatch alarms)
5. **Vendor/third-party risk** — check designs/ for third-party risk assessment or BAA/DPA list

Output one PASS or FINDING line per item.

### GDPR checklist
1. **Consent records** — look for consent table, consent flag, or consent API
2. **Lawful basis documentation** — check designs/ for documented lawful basis per data category
3. **DPA/DPIA** — check designs/ for a Data Processing Agreement or Data Protection Impact Assessment
4. **Data retention policy** — look for scheduled deletion or archival jobs with documented retention periods
5. **Data breach notification procedure** — check designs/SOP/ for breach notification within 72 hours

Output one PASS or FINDING line per item.

### CCPA checklist
1. **Right to know / access endpoint** — does a data export endpoint exist?
2. **Right to delete endpoint** — does a user data deletion endpoint exist?
3. **Opt-out of sale** — if data is shared with third parties, is there an opt-out mechanism?
4. **Privacy policy reference** — check for privacy policy link or documentation in designs/

Output one PASS or FINDING line per item.

### PCI-DSS checklist
1. **No raw card data stored** — grep for `card_number`, `cvv`, `ccv`, `pan` in source code and DB schema
2. **Payment data in scope** — check designs/ for PCI scope documentation
3. **Tokenisation or third-party PSP** — verify card data handling is delegated to a PCI-certified PSP

### FIPS checklist
1. **No weak ciphers** — grep for `MD5`, `SHA1`, `DES`, `RC4` in cryptographic contexts
2. **Approved algorithms** — look for AES-256, RSA-4096, ECDSA P-384 usage

---

**Step 6 — Handle tool failures.**

If any tool call fails: log `ERROR: <tool>(<args>) → <error>`, try once with an alternative,
then skip. Include a `TOOL FAILURES:` block before the final line if any step was skipped.

---

**Step 7 — Format all findings.**

Every check that was performed — whether it passed or failed — must appear in the output.
Do not omit checks that passed.

```
FINDING [COMP]: <one-sentence description> — <file, endpoint, or data field>  [CRITICAL|HIGH|MEDIUM]
PASS [COMP]: <what was checked and found compliant>
INFO [COMP]: <contextual note — not a violation, but relevant>
```

End your output with exactly:
```
COMPLIANCE SCAN COMPLETE
```
