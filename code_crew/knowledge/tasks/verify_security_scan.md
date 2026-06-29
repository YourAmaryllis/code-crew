---
type: CrewAI Task
title: Security Verification Scan
description: Security lead scans for hardcoded secrets, OWASP violations, OTM content validity, NIST gaps, and dependency vulnerabilities
tags: [verify, security, scan, owasp, nist, secrets]
agent: security_lead
expected_output: >
  Structured list of findings tagged [SEC], each prefixed with FINDING, PASS, or INFO.
  Every checked item — whether clean or not — gets a line. Ends with SECURITY SCAN COMPLETE.
---

Scan the codebase for security issues. Use `workspace_reader` to inspect source files and
`knowledge_reader` to load `functions/security-privacy.md` and active stack guides.

**CRITICAL: All paths must be relative to the project root (`.`). Never use absolute paths.**

---

**Step 1 — Hardcoded secrets scan.**

Search for patterns that indicate hardcoded credentials in source files (not in `.env` or
`.env.example`):
- Regex patterns: `(secret|password|token|api_key|apikey|private_key)\s*=\s*["'][^"']{8,}["']`
- AWS key patterns: `AKIA[0-9A-Z]{16}`, `aws_secret_access_key\s*=`
- Private key headers: `-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----`
- Skip: test files, example files, `*.example`, `*.sample`, mock data

Report each hit as a FINDING. If clean: `PASS [SEC]: No hardcoded secrets found in source files`.

---

**Step 2 — OTM threat model validity.**

Use `workspace_reader` to list files under `designs/TMD/`. For each service or component in
the codebase (identified by `cmd/`, `services/`, `apps/` directories or top-level module names),
check if a matching OTM YAML exists in `designs/TMD/`.

For **each TMD file that does exist**, read its content and validate it is an actual threat model:
- A valid OTM file must contain at least one of: `components:`, `threats:`, `dataFlows:`, `trustZones:`
- If a TMD file contains an error message, stack trace, Python exception, or is otherwise not a
  valid OTM YAML structure, flag it:
  ```
  FINDING [SEC]: TMD file is not a valid threat model — designs/TMD/<filename>.yaml [HIGH]
  ```
- If the file is valid OTM: `PASS [SEC]: TMD valid — designs/TMD/<filename>.yaml`

For services with **no TMD file**:
```
FINDING [SEC]: No threat model found for service — <service-directory> [MEDIUM]
```

If `designs/TMD/` does not exist or is empty:
```
FINDING [SEC]: No threat models found in designs/TMD/ — threat modelling not established [HIGH]
```

---

**Step 3 — OWASP Top 10 spot-check.**

For each category, do a targeted scan. Output a PASS or FINDING for each:

- **A01 Broken Access Control**: look for routes without auth middleware; check role enforcement.
  PASS if auth middleware is consistently applied; FINDING if unprotected routes found.
- **A02 Cryptographic Failures**: find `MD5`, `SHA1`, `DES`, `RC4` usage; HTTP (not HTTPS) hardcoded URLs.
  PASS if no weak ciphers found.
- **A03 Injection**: find raw string concatenation into SQL queries; unsanitised shell commands.
  PASS if parameterised queries used throughout.
- **A04 Insecure Design**: find `TODO: add auth`, `# FIXME security`, placeholder validation.
- **A05 Security Misconfiguration**: find `DEBUG=True` or `debug: true` outside test files; open CORS (`*`).
- **A06 Vulnerable Components**: check `commands.audit` in `.code-crew/structure.md`; if set, note
  whether audit output is available in workspace; if not set, emit a FINDING that dependency
  auditing is not configured.
- **A07 Authentication Failures**: check for rate limiting on login endpoints; token expiry handling.
- **A09 Logging Failures**: check that auth events (login, logout, token issue) have log statements.

---

**Step 4 — NIST CSF spot-check.**

Check alignment with NIST Cybersecurity Framework core functions (high-level only):

- **Identify**: Is there an asset inventory or component registry? (check designs/ADD/ or SAD)
  PASS if ADDs document all services and their data; INFO if partial.
- **Protect**: Is access control documented and enforced? (check auth middleware and ADR)
  PASS if IAM/auth policies documented in designs/.
- **Detect**: Is there monitoring/alerting for anomalous activity? (check for references to
  SIEM, CloudWatch alarms, or intrusion detection in designs/ or infrastructure code)
- **Respond**: Is there an incident response runbook? (check designs/SOP/)
  FINDING if no IR runbook exists.
- **Recover**: Is there a backup/restore procedure? (check designs/SOP/ or infrastructure)
  INFO if not found.

---

**Step 5 — SBOM / dependency audit.**

Check if a lockfile (`requirements.txt`, `go.sum`, `package-lock.json`) is present and committed.
Flag if absent: `FINDING [SEC]: No lockfile committed — dependency versions unpinned [MEDIUM]`.
If present: `PASS [SEC]: Lockfile present — <filename>`.

---

**Step 6 — Handle tool failures.**

If any tool call fails: log `ERROR: <tool>(<args>) → <error>`, try once with an alternative
approach, then skip. Never use absolute paths in shell commands — always relative to project root.
Include a `TOOL FAILURES:` block before the final line if any step was skipped.

---

**Step 7 — Format findings.**

Every check that was performed — whether it passed or failed — must appear in the output.
Do not omit checks that passed.

```
FINDING [SEC]: <one-sentence description> — <file:line or component name>  [CRITICAL|HIGH|MEDIUM]
PASS [SEC]: <what was checked and found clean>
INFO [SEC]: <contextual note — not a violation, but relevant>
```

End your output with exactly:
```
SECURITY SCAN COMPLETE
```
