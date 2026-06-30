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

**CRITICAL: All paths must be relative to the project root (`.`). Never use absolute paths.**
**SCOPE LIMIT: At most 12 file reads total. Prioritise TMD validation and secrets scan.**

---

**Step 1 — Hardcoded secrets scan.**

Search for patterns that indicate hardcoded credentials in source files (not in `.env` or
`.env.example`):
- Regex patterns: `(secret|password|token|api_key|apikey|private_key)\s*=\s*["'][^"']{8,}["']`
- AWS key patterns: `AKIA[0-9A-Z]{16}`, `aws_secret_access_key\s*=`
- Private key headers: `-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----`
- Skip: test files, example files, `*.example`, `*.sample`, mock data

If clean: `PASS [SEC]: No hardcoded secrets found in source files`.
Report each hit as a `FINDING [SEC]`.

---

**Step 2 — OTM threat model validation (read every TMD file).**

Use `workspace_reader` to list ALL files under `designs/TMD/`.

Then read **every** `.yaml` file in that list, one by one. Do not skip small files —
a 1-4 line file is almost certainly invalid.

For each file read, immediately output one line (before reading the next file):

A file is **valid** only if ALL of these are true:
- It contains the YAML key `otmVersion:` on a non-comment line (not preceded by `#`)
- It contains at least one of: `components:`, `threats:`, `dataFlows:`, `trustZones:`
- The content is actual YAML, not an error message, not a JSON dump (starts with `{` or `{"`)
  and not a placeholder (contains `<PROJECT_NAME>` or `<description>`)

If the file is just comments + a line starting with `{` or `{"`, it is a JSON dump — invalid.

Valid: `PASS [SEC]: TMD valid — designs/TMD/<filename>.yaml`
Invalid: `FINDING [SEC]: TMD file invalid — designs/TMD/<filename>.yaml [HIGH] (reason: <error message / JSON dump / placeholder / prose / only comments>)`

Then compare the TMD files against the `## Architectural components` table in the task context
(from structure.md). Only look at rows where the **Type** column is `deployable service`.
Do NOT expect TMDs for rows with Type = `test suite`, `infrastructure`, `external`, or
`infrastructure + test fixtures`.

For each `deployable service` component with no TMD file:
```
FINDING [SEC]: No threat model found for component — <component-name> [MEDIUM]
```

If `designs/TMD/` does not exist or is empty:
```
FINDING [SEC]: No threat models found in designs/TMD/ — threat modelling not established [HIGH]
```

---

**Step 3 — OWASP Top 10 spot-check (targeted, 2 file reads max).**

Read 1 handler and 1 auth-related file. Check:
- **A01 Broken Access Control**: routes checked for auth middleware
- **A02 Cryptographic Failures**: no MD5/SHA1/DES/RC4 in crypto contexts
- **A03 Injection**: parameterised queries used (no raw string SQL)
- **A05 Security Misconfiguration**: no `DEBUG=True` or open CORS (`*`) in production paths
- **A06 Vulnerable Components**: check `commands.audit` in structure.md; if no audit command,
  flag as FINDING that dependency auditing is not configured
- **A09 Logging Failures**: auth events (login, logout, token issue) have log statements

Output one PASS or FINDING per category checked.

---

**Step 4 — NIST CSF spot-check (documentation only, no file reads).**

Use what you already know from Step 2 (TMD files and architecture context) to assess:
- **Identify**: Do TMDs document assets and components? (PASS if TMD has `assets:` section)
- **Protect**: Is access control documented in any TMD? (check `trustZones:` section)
- **Detect**: Are monitoring/alerting mentions visible in structure.md or TMDs?
- **Respond**: Did Step 5 of compliance scan find an IR runbook? (note if unknown)
- **Recover**: Note if not checked (within scope limit)

One line per function. Use INFO if evidence is partial.

---

**Step 5 — SBOM / dependency audit.**

Check if a lockfile (`go.sum`, `package-lock.json`, `requirements.txt`, `poetry.lock`) exists.
Use `find_files` with pattern `**/go.sum` or `**/package-lock.json` — do not read contents.

If present: `PASS [SEC]: Lockfile committed — <filename>`.
If absent: `FINDING [SEC]: No lockfile committed — dependency versions unpinned [MEDIUM]`.

---

**Step 6 — Handle tool failures.**

If any tool call fails: log `ERROR: <tool>(<args>) → <error>`, try once with an alternative.
Never use absolute paths. Include a `TOOL FAILURES:` block before the final line if any step
was skipped.

---

**Step 7 — Format findings.**

Every check performed — whether it passed or failed — must appear in the output.

```
FINDING [SEC]: <one-sentence description> — <file:line or component name>  [CRITICAL|HIGH|MEDIUM]
PASS [SEC]: <what was checked and found clean>
INFO [SEC]: <contextual note — not a violation>
```

End with exactly:
```
SECURITY SCAN COMPLETE
```
