---
type: CrewAI Task
title: Security Review
description: Technical security review — OWASP (baseline or ASVS L2), crypto (FIPS 140-3 if active), OTM threat model update, IAM, and SBOM
tags: [security, owasp, fips, otm, threat-model, sbom, iam, phase-19]
timestamp: 2026-06-17T00:00:00Z
agent: security_lead
context_agents:
  - engineer
expected_output: >
  A Security Review Report with: OWASP verdict per category (PASS/FAIL with evidence),
  OWASP LLM Top 10 verdict if ai-ml stack is active, FIPS crypto verdict if active,
  OTM threat model update summary (STRIDE always; PLOT4ai if AI/ML present; LINDDUN if
  personal data in scope), platform constraint check, SBOM of new dependencies, IAM
  findings, and a final gate (APPROVED / BLOCKED with full blocker list).
  Regulatory compliance is reported separately by the compliance officer.
---

Review the implementation for technical security vulnerabilities and update the threat model.

**Step 1 — Load security context.**
Use `knowledge_reader` to load:
- `threat-dragon` — OTM YAML format, framework selection guide, and maintenance steps
- `owasp` if the `owasp` stack is active — provides the full ASVS L2 checklist and search patterns to use
- `fips-140-3` if the `fips-140-3` stack is active
- `ai-ml` if the `ai-ml` stack is active — adds OWASP LLM Top 10 checklist and PLOT4ai requirements
- The feature ADD (from the issue tracker ticket's ADD references) — understand new data flows and stacks
- Any ADDs listed in the feature ADD's `references` field that are relevant to the security surface

Load the issue tracker ticket to understand what changed (use the issue tracker tool configured via `CODE_CREW_ISSUE_TRACKER`).

**Step 2 — OWASP check.**
Use `search_ast` and `code_index` for each category — do not read whole files to find patterns.

If `owasp` stack is active: apply the full ASVS L2 checklist from the loaded `owasp` document, using the search patterns it specifies.

Baseline (always): for each category, run the search patterns from the `owasp` stack document (or the generic patterns below if owasp stack is not active) and state PASS or FAIL with specific evidence (file:line from tool output):

1. **Injection** — search for raw SQL string concatenation; format-string SQL construction
2. **Broken Authentication** — search for auth middleware, token validation
3. **Sensitive Data Exposure** — search for PHI/PII in log output, sensitive data in response bodies
4. **XML/XXE** — search for XML parsing with DTD or external entity processing
5. **Broken Access Control** — search for ownership checks, IDOR patterns, role/permission gates
6. **Security Misconfiguration** — search for DEBUG flags, CORS wildcards, insecure config defaults
7. **Vulnerable Components** — read the dependency manifest (filename is in the active stack document)
8. **Insecure Deserialization** — search for deserialization of untrusted input
9. **Insufficient Logging** — search for security events: auth failures, access denied, data writes
10. **SSRF** — search for outbound HTTP calls with caller-controlled URLs

**Step 3 — Cryptography check.**
If `fips-140-3` active: apply its full checklist from the loaded document.

Always check for weak algorithms, insecure RNG, TLS configuration, and hardcoded credentials (use the search patterns from the `fips-140-3` stack document or the `security-privacy` function).

**Step 4 — OTM threat model update.**
Follow the `threat-dragon` guide ("Choosing a Framework" and "Security Lead Review Steps"):
1. Check the TMD directory for an existing OTM YAML model for the affected service
2. Determine frameworks: always STRIDE; add PLOT4ai if `ai-ml` stack active; add LINDDUN if personal data in scope
3. Update or create: add threats for new surface area; update mitigation `state` for resolved items
4. Write the updated file to the TMD directory via `platform_shell`

Output the threat model summary (file updated/created, frameworks used, open threats by severity).

**Step 5 — Platform constraint check.**
For each ADD referenced by this story, load any constraint documents from its `references` field and verify the implementation does not violate data handling rules, custody boundaries, or access policies.

**Step 6 — IAM check.**
List new IAM policies or permission grants. Flag wildcard actions or resources without justification.

**Step 7 — SBOM.**
List every new dependency:

| Package | Version | License | Risk |
|---------|---------|---------|------|

Flag non-commercially-permissive licenses and any dependency with a known CVE.

**On tool failure** — log the error, try once with an alternative, skip and continue. Note skipped steps as `INFO: <step> skipped — <reason>`.

**Final gate**: APPROVED (no Critical/High findings) or BLOCKED (list each: severity, file:line, finding, fix).
If tools unavailable: `INCOMPLETE: <reason>`.
