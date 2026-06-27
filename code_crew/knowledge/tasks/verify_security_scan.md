---
type: CrewAI Task
title: Security Verification Scan
description: Security lead scans for hardcoded secrets, OWASP violations, OTM coverage gaps, and dependency vulnerabilities
tags: [verify, security, scan, owasp, secrets]
agent: security_lead
expected_output: >
  Structured list of findings tagged [SEC], each prefixed with FINDING, PASS, or INFO.
  Ends with SECURITY SCAN COMPLETE.
---

Scan the codebase for security issues. Use `workspace_reader` to inspect source files and `knowledge_reader` to load `functions/security-privacy.md` and the active stack guides.

**Step 1 — Hardcoded secrets scan.**
Search for patterns that indicate hardcoded credentials in source files (not in `.env` or `.env.example`):
- Regex patterns: `(secret|password|token|api_key|apikey|private_key)\s*=\s*["'][^"']{8,}["']`
- AWS key patterns: `AKIA[0-9A-Z]{16}`, `aws_secret_access_key\s*=`
- Private key headers: `-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----`
- Skip: test files, example files, `*.example`, `*.sample`, mock data

Report each hit as a FINDING. If clean: one PASS line.

**Step 2 — OTM threat model coverage.**
Use `workspace_reader` to list files under `designs/TMD/`. For each service or component in the codebase (identified by `cmd/`, `services/`, `apps/` directories or top-level module names), check if a matching OTM YAML exists in `designs/TMD/`. Flag services with no threat model.

**Step 3 — OWASP Top 10 spot-check.**
For each category, do a targeted scan:
- **A01 Broken Access Control**: look for routes without auth middleware; check role enforcement
- **A02 Cryptographic Failures**: find `MD5`, `SHA1`, `DES`, `RC4` usage; HTTP (not HTTPS) hardcoded URLs
- **A03 Injection**: find raw string concatenation into SQL queries; unsanitised shell commands
- **A04 Insecure Design**: find `TODO: add auth`, `# FIXME security`, placeholder validation
- **A05 Security Misconfiguration**: find `DEBUG=True` or `debug: true` outside test files; open CORS (`*`)
- **A06 Vulnerable Components**: note if `pip-audit`, `go mod audit`, or `npm audit` output is available in workspace; flag if not
- **A09 Logging Failures**: check that auth events (login, logout, token issue) have log statements

**Step 4 — SBOM / dependency audit.**
Check if a lockfile (`requirements.txt`, `go.sum`, `package-lock.json`) is present and committed. Flag if absent.

**Step 5 — Format findings.**

```
FINDING [SEC]: <one-sentence description> — <file:line or component name>
PASS [SEC]: <what was checked and found clean>
```

Severity hint (append to FINDING lines where applicable): `[CRITICAL]`, `[HIGH]`, `[MEDIUM]`.

End your output with exactly:
```
SECURITY SCAN COMPLETE
```
