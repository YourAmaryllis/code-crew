---
type: CrewAI Task
title: Security Review
description: Technical security review — OWASP (baseline or ASVS L2), FIPS 140-3 crypto, OTM threat model update, IAM, SBOM, and platform constraint check
tags: [security, owasp, fips, otm, threat-model, sbom, iam, phase-19]
timestamp: 2026-06-17T00:00:00Z
agent: security_lead
context_agents:
  - engineer
expected_output: >
  A Security Review Report with: OWASP verdict per category (PASS/FAIL with evidence),
  OWASP LLM Top 10 verdict if ai-ml stack is active, FIPS crypto verdict if active,
  OTM threat model update summary (STRIDE threats always; PLOT4ai threats if AI/ML components
  present; LINDDUN threats if personal data in scope), platform constraint check, SBOM of new
  dependencies, IAM findings, and a final gate (APPROVED / BLOCKED with full blocker list).
  Regulatory compliance is reported separately by the compliance officer.
---

Review the implementation for technical security vulnerabilities and update the threat model.

**Step 1 — Load security context**

Use `knowledge_reader` to load:
- `threat-dragon` — OTM YAML format, framework selection guide, and maintenance steps
- `owasp` if the `owasp` stack is active
- `fips-140-3` if the `fips-140-3` stack is active
- `ai-ml` if the `ai-ml` stack is active — adds OWASP LLM Top 10 checklist and PLOT4ai requirements
- The feature ADD (from Jira ticket ADD references) — understand new data flows and their stacks
- Any ADDs listed in the feature ADD's `references` frontmatter field that are relevant to the security surface

Use `jira_view` to load the ticket and understand what changed.

**Step 2 — OWASP check**

Use `search_ast` and `code_index` for each category — do not read whole files to find patterns.

If `owasp` stack is active: apply the full ASVS L2 checklist from the loaded `owasp` document.

Baseline (always): for each category below, run the suggested tool call and state PASS or FAIL with specific evidence (file:line from tool output):

1. **Injection** — `code_index search "raw SQL string concatenation query fmt.Sprintf"` + `search_ast pattern='fmt.Sprintf($FMT, $$$)' language="go"` for format-string SQL
2. **Broken Authentication** — `code_index search "auth middleware JWT token validation"` + `search_ast pattern="jwt.Parse($TOKEN, $$$)" language="go"`
3. **Sensitive Data Exposure** — `code_index search "PHI PII log response leak sensitive data"`; `search_ast pattern='log.Printf($FMT, $$$)' language="go"` to spot log calls near auth handlers
4. **XML/XXE** — `code_index search "XML parse DTD external entity processing"`
5. **Broken Access Control** — `code_index search "ownership check IDOR role permission write"`
6. **Security Misconfiguration** — `code_index search "DEBUG CORS AllowAll wildcard insecure config"`
7. **Vulnerable Components** — read the dependency manifest (`go.mod`, `package.json`) — this is the one file read that is always justified
8. **Insecure Deserialization** — `code_index search "pickle eval exec deserialise untrusted input"`
9. **Insufficient Logging** — `code_index search "auth failure access denied audit log security event"`
10. **SSRF** — `code_index search "HTTP client external URL fetch outbound request"`

**Step 3 — Cryptography check**

If `fips-140-3` active: apply the full FIPS checklist from the loaded `fips-140-3` document.

Always check:
- `code_index search "MD5 SHA1 DES RC4 weak hash"` — weak algorithms
- `code_index search "crypto random token key generation"` — insecure RNG
- `search_ast pattern="tls.Config{$$$}" language="go"` — confirm TLS 1.2+ config present
- `code_index search "hardcoded secret password key credential"` — secrets in code

**Step 4 — OTM threat model update**

Follow the `threat-dragon` guide (see "Choosing a Framework" and "Security Lead Review Steps"):
1. Check `designs/TMD/` for an existing OTM YAML model for the affected service
2. Determine frameworks: always STRIDE; add PLOT4ai if `ai-ml` stack active or AI/ML components introduced; add LINDDUN if personal data in scope and GDPR/CCPA active
3. Update or create: add threats for new surface area; update mitigation `status` for resolved items
4. Write the updated/new file to `designs/TMD/<service>.yaml` via `platform_shell`

Output the threat model summary (file updated/created, frameworks used, open threats by severity).

**Step 5 — Platform constraint check**

For each ADD referenced by this story, check its `references` frontmatter field for constraint documents. Load them via `knowledge_reader` or `workspace_reader` and verify the implementation does not violate their constraints (data handling rules, custody boundaries, access policies, etc.).

**Step 6 — IAM check**

List new IAM policies or permission grants. Flag `*` actions/resources without justification.

**Step 7 — SBOM**

List every new dependency:

| Package | Version | License | Risk |
|---------|---------|---------|------|

Flag non-commercially-permissive licenses. Flag any dependency with a known CVE.

**On tool failure** — log the error, try once with an alternative, then skip and continue. Never use absolute paths in shell commands. If a scan step cannot run, note it as `INFO: <step> skipped — <reason>` and proceed.

**Final gate**: APPROVED (no Critical/High findings) or BLOCKED (list each: severity, file/line, finding, fix).

If tools unavailable: `INCOMPLETE: <reason>`.
