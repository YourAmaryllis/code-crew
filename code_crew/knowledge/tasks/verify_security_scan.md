---
type: CrewAI Task
title: Security Verification Scan
description: Security lead performs OWASP and NIST spot-check; TMD validation and secrets scan are pre-computed by Python and merged automatically
tags: [verify, security, scan, owasp, nist]
agent: security_lead
expected_output: >
  Structured list of OWASP and NIST findings tagged [SEC], each prefixed with FINDING, PASS, or INFO.
  Ends with SECURITY SCAN COMPLETE.
---

Perform security spot-checks. TMD validation and hardcoded secrets are already pre-computed and
will be merged into the final report — you do not need to check those.

**CRITICAL: All paths must be relative to `.`. Never use absolute paths.**

---

**Step 1 — OWASP Top 10 spot-check.**

Use `search_ast` and `code_index` — do not list directories or read whole files to find patterns.
Each check is one targeted tool call:

- **A01 Broken Access Control** — `code_index search "auth middleware authorization JWT check"`
  → `PASS [SEC]: A01 Broken Access Control — auth checks present in handlers`
  → or `FINDING [SEC]: A01 Broken Access Control — no auth middleware found [HIGH]`

- **A02 Cryptographic Failures** — `code_index search "MD5 SHA1 DES RC4 weak crypto hash"`
  → `PASS [SEC]: A02 Cryptographic Failures — no weak crypto found`
  → or `FINDING [SEC]: A02 Cryptographic Failures — weak algorithm found [HIGH]`

- **A03 Injection** — `code_index search "raw SQL string concatenation query builder"`; for Go also
  `search_ast pattern='fmt.Sprintf("%" + $FRAG, $$$)' language="go"` to catch format-string SQL
  → `PASS [SEC]: A03 Injection — no raw SQL injection pattern found`
  → or `FINDING [SEC]: A03 Injection — SQL string concatenation found [HIGH]`

- **A05 Security Misconfiguration** — `code_index search "DEBUG CORS AllowAll open wildcard config"`
  → `PASS [SEC]: A05 Security Misconfiguration — no insecure config found`
  → or `FINDING [SEC]: A05 Security Misconfiguration — insecure config found [MEDIUM]`

- **A09 Logging Failures** — `code_index search "auth event log security audit failure"`
  → `PASS [SEC]: A09 Logging Failures — auth events logged`
  → or `FINDING [SEC]: A09 Logging Failures — auth events not logged [MEDIUM]`

If `code_index` returns no results (index not built): fall back to `workspace_reader search` with the same keywords.
Unchecked items: `INFO [SEC]: <item> — not checked within scope`

---

**Step 2 — NIST CSF (no file reads — use TMD context from structure.md).**

Your context includes `## Project structure` with TMD information. Based on that:
- `PASS [SEC]: NIST CSF Identify — assets documented in TMDs` (if TMDs have components)
- `PASS [SEC]: NIST CSF Protect — trust zones documented` (if TMDs have trustZones)
- `INFO [SEC]: NIST CSF Detect — monitoring not verified in this scan`
- `INFO [SEC]: NIST CSF Respond/Recover — not checked`

---

**Step 3 — End.**

Output format:
```
FINDING [SEC]: <one-sentence description> — <file:line or component>  [CRITICAL|HIGH|MEDIUM|LOW]
PASS [SEC]: <what was checked and found clean>
INFO [SEC]: <contextual note>
```

End with exactly:
```
SECURITY SCAN COMPLETE
```
