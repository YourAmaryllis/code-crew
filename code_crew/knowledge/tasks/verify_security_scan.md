---
type: CrewAI Task
title: Security Verification Scan
description: Security lead validates TMD files for all architectural components, checks for hardcoded secrets, and runs targeted OWASP/NIST checks
tags: [verify, security, scan, owasp, nist, secrets, tmds]
agent: security_lead
expected_output: >
  Structured list of findings tagged [SEC], each prefixed with FINDING, PASS, or INFO.
  Every checked item — whether clean or not — gets a line. Ends with SECURITY SCAN COMPLETE.
---

Scan the codebase for security issues. Use `workspace_reader` to inspect source files.

**CRITICAL: All paths must be relative to `.`. Never use absolute paths.**
**CRITICAL: If a tool call fails or returns an error, output `INFO [SEC]: <tool> failed on <path> — skipped` and
immediately move to the next step. Do NOT retry with a different path or pattern.**
**CRITICAL: The only valid base paths are: `.`, `designs/`, `portal/`, `attestation/`,
`fhir_proxy/`, `healthcare-calculator/`, `panome/`, `integration/`, `ops/`. Never use
`workspace`, `/workspace`, `workspace/`, or any absolute path.**

---

**Step 1 — OTM threat model validation (highest priority — do this first).**

Use `workspace_reader` with `list_directory` on `designs/TMD/` to get the file list.

Then read each `.yaml` file one by one. Immediately after reading each file, output ONE line:

A file is **valid** only if ALL of these are true:
- Contains `otmVersion:` as a real YAML key on a non-comment line (line does NOT start with `#`)
- Contains at least one of: `components:`, `threats:`, `dataFlows:`, `trustZones:`
- Is not a JSON dump (does not have a line starting with `{` or `{"`)
- Is not a placeholder (does not contain `<PROJECT_NAME>` or `<description>`)

If file is valid: `PASS [SEC]: TMD valid — designs/TMD/<filename>.yaml`
If file is invalid: `FINDING [SEC]: TMD file invalid — designs/TMD/<filename>.yaml [HIGH] (reason: <json dump / error message / placeholder / missing otmVersion>)`

After checking all files, compare against the `## Architectural components` table from your
context (structure.md). Only rows where Type = `deployable service` require a TMD.
Do NOT flag rows with Type = `test suite`, `infrastructure`, `external`, or `infrastructure + test fixtures`.

For each deployable-service component with no TMD file at all:
`FINDING [SEC]: No threat model found for component — <component-name> [MEDIUM]`

If `designs/TMD/` is empty or does not exist:
`FINDING [SEC]: No threat models found in designs/TMD/ — threat modelling not established [HIGH]`

---

**Step 2 — Hardcoded secrets scan (2 searches maximum, specific paths only).**

Do EXACTLY ONE search call per path below. Do not retry if a search returns errors.

Search 1: use `search` on path `portal/backend/internal/api/` with pattern:
`(secret|password|api_key|apikey|private_key)\s*=\s*["'][^"']{8,}["']`

After Search 1, immediately output what you found (PASS or FINDING) before doing Search 2.

Search 2: use `search` on path `healthcare-calculator/server/internal/` with the same pattern.

After Search 2, immediately output results (PASS or FINDING).

Then stop — do NOT do any more searches. If either path does not exist, output:
`INFO [SEC]: Path not found — <path> — secrets scan skipped for this service`

If clean across all searches: `PASS [SEC]: No hardcoded secrets found in scanned paths`
Report each hit as: `FINDING [SEC]: Hardcoded secret — <file>:<line> [HIGH]`

---

**Step 3 — OWASP spot-check (2 file reads).**

Read `portal/backend/internal/api/handlers.go` (or the first handler file you find via
`list_directory portal/backend/internal/api/` if handlers.go does not exist).

Read `portal/backend/internal/auth/` or the first auth-related file in portal/backend/.

Check from the two files only:
- **A01**: Auth middleware present in handler? `PASS [SEC]: A01 — auth middleware present in handlers`
- **A02**: No MD5/SHA1/DES/RC4? `PASS [SEC]: A02 — no weak crypto in reviewed files`
- **A03**: No raw SQL string concatenation? `PASS [SEC]: A03 — no raw SQL injection pattern`
- **A05**: No DEBUG=True or open CORS(*)? `PASS [SEC]: A05 — no insecure config in reviewed files`
- **A09**: Auth events have log statements? If log present: `PASS [SEC]: A09 — auth events logged`; If not: `FINDING [SEC]: A09 Logging Failures — auth events not logged [MEDIUM]`

If a file does not exist: `INFO [SEC]: OWASP check — <file> not found, check skipped`
Mark unchecked items as `INFO [SEC]: <OWASP item> — not checked within scope`

---

**Step 4 — NIST CSF check (no file reads — use Step 1 TMD content).**

Based only on the TMD files you already read in Step 1:
- **Identify**: TMDs have `components:` or `assets:` → `PASS [SEC]: NIST CSF Identify — assets documented in TMDs`
- **Protect**: TMDs have `trustZones:` → `PASS [SEC]: NIST CSF Protect — trust zones documented`
- **Detect**: TMDs mention monitoring → `PASS` or `INFO [SEC]: NIST CSF Detect — monitoring not in TMDs`
- **Respond/Recover**: `INFO [SEC]: NIST CSF Respond/Recover — not checked`

---

**Step 5 — Final format.**

Every check — whether passed or failed — must appear. Output format:
```
FINDING [SEC]: <one-sentence description> — <file:line or component>  [CRITICAL|HIGH|MEDIUM]
PASS [SEC]: <what was checked and found clean>
INFO [SEC]: <contextual note — not a violation>
```

End with exactly:
```
SECURITY SCAN COMPLETE
```
