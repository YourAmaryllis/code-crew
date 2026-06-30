---
type: CrewAI Task
title: Security Verification Scan
description: Security lead reports pre-validated TMD and secrets facts, then does OWASP/NIST spot-check
tags: [verify, security, scan, owasp, nist, secrets, tmds]
agent: security_lead
expected_output: >
  Structured list of findings tagged [SEC], each prefixed with FINDING, PASS, or INFO.
  Every checked item — whether clean or not — gets a line. Ends with SECURITY SCAN COMPLETE.
---

Scan the codebase for security issues. Use `workspace_reader` to inspect source files.

**CRITICAL: All paths must be relative to `.`. Never use absolute paths.**
**CRITICAL: Steps 1 and 2 use pre-computed facts from your context — do NOT read files
for those steps. Report the pre-computed results directly.**

---

**Step 1 — Report TMD validation results.**

Your context has `## Pre-computed security facts` with TWO subsections to use:

**From `### TMD file validation`** — output one line per file:
- Entry says VALID: `PASS [SEC]: TMD valid — <path>`
- Entry says INVALID: `FINDING [SEC]: TMD file invalid — <path> [HIGH] (reason: <reason from context>)`

**From `### Component TMD coverage (deployable services only)`** — output one line per component:
- Entry says "TMD VALID": `PASS [SEC]: Threat model present and valid — <component name>`
- Entry says "TMD INVALID": `FINDING [SEC]: Threat model invalid for component — <component name> [HIGH]`
- Entry says "NO TMD FILE FOUND": `FINDING [SEC]: No threat model found for component — <component name> [MEDIUM]`

If `designs/TMD/` does not exist: `FINDING [SEC]: No threat models found [HIGH]`

---

**Step 2 — Report secrets scan results.**

Your task context includes `### Hardcoded secrets scan` results. Report them:

- If the entry says "No hardcoded secrets found": `PASS [SEC]: No hardcoded secrets found in scanned Go source files`
- For each finding line (format `- <path>:<line>: <snippet> [HIGH/LOW]`):
  `FINDING [SEC]: Hardcoded secret — <path>:<line> [HIGH]` (or LOW if noted as test file)

Do NOT do any additional file reading or search for this step.

---

**Step 3 — OWASP spot-check (2 file reads max).**

Use `list_directory` on `portal/backend/internal/api/` to find a handler file.
Read that handler file. Then read one auth-related file from the same directory or
`portal/backend/internal/auth0mgmt/`.

Check from the two files only:
- **A01**: Auth middleware or auth check present? → `PASS [SEC]: A01 — auth checks present in handlers`
- **A02**: No MD5/SHA1/DES/RC4? → `PASS [SEC]: A02 — no weak crypto in reviewed files`
- **A03**: No raw SQL string concat? → `PASS [SEC]: A03 — parameterised queries used`
- **A05**: No DEBUG=True or open CORS(*)? → `PASS [SEC]: A05 — no insecure config in reviewed files`
- **A09**: Auth events have log statements? → `PASS [SEC]: A09 — auth events logged` or
  `FINDING [SEC]: A09 Logging Failures — auth events not logged [MEDIUM]`

If a file is not found: `INFO [SEC]: OWASP check — <file> not found, check skipped`
Unchecked items: `INFO [SEC]: <OWASP item> — not checked within scope`

---

**Step 4 — NIST CSF (no file reads — use TMD validation results from Step 1).**

Based only on what Step 1 revealed about valid TMD files:
- Valid TMDs have `components:` → `PASS [SEC]: NIST CSF Identify — assets documented in TMDs`
- Valid TMDs have `trustZones:` → `PASS [SEC]: NIST CSF Protect — trust zones documented`
- Monitoring not evident → `INFO [SEC]: NIST CSF Detect — monitoring not in TMDs`
- `INFO [SEC]: NIST CSF Respond/Recover — not checked`

---

**Step 5 — Format and end.**

Every check — whether passed or failed — must appear. Output format:
```
FINDING [SEC]: <one-sentence description> — <file:line or component>  [CRITICAL|HIGH|MEDIUM|LOW]
PASS [SEC]: <what was checked and found clean>
INFO [SEC]: <contextual note — not a violation>
```

End with exactly:
```
SECURITY SCAN COMPLETE
```
