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

If `owasp` stack is active: apply the full ASVS L2 checklist from the loaded `owasp` document.

Baseline (always): for each of the 10 categories, state PASS or FAIL with specific evidence
(file, line, pattern found):

1. **Injection** — parameterized queries; no string concat in SQL; XSS prevention in output
2. **Broken Authentication** — per-platform patterns; no custom auth; no client-side credential storage
3. **Sensitive Data Exposure** — no PII/PHI in logs, errors, or responses beyond requirement; HTTPS enforced
4. **XML/XXE** — external data parsed safely; no DTD processing
5. **Broken Access Control** — ownership checked on every write; no IDOR; role checks present
6. **Security Misconfiguration** — no debug flags or permissive CORS in production; env vars documented
7. **Vulnerable Components** — new dependencies checked for CVEs
8. **Insecure Deserialization** — no `pickle`, `eval`, `exec` on untrusted input
9. **Insufficient Logging** — auth failures, access denials, data writes logged
10. **SSRF** — new HTTP client code restricts target URLs

**Step 3 — Cryptography check**

If `fips-140-3` active: apply the full FIPS checklist from the loaded `fips-140-3` document.

Always check: no MD5/SHA-1 for security-sensitive uses; no insecure RNG for tokens/keys;
TLS 1.2+ only; secrets not hardcoded.

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

**Final gate**: APPROVED (no Critical/High findings) or BLOCKED (list each: severity, file/line, finding, fix).

If tools unavailable: `INCOMPLETE: <reason>`.
