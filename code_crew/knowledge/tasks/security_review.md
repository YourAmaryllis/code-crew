---
type: CrewAI Task
title: Security Review
description: OWASP Top 10 review, zero-custody check, SBOM generation, and approval gate
tags: [security, owasp, sbom, iam, zero-custody, phase-19]
timestamp: 2026-06-17T00:00:00Z
agent: security_reviewer
context_agents:
  - backend_developer
  - frontend_developer
expected_output: >
  A Security Review Report with: per-finding entries (severity, file/line, description,
  fix), a zero-custody alignment statement, an SBOM listing new dependencies with
  licenses, and a final gate decision (APPROVED / BLOCKED with blocker list).
---

Review the implementation outputs from the backend and frontend developers against
YourAmaryllis's security standards.

Use the `sop_reader` tool to load SOP-9-Security and ADD-009 (zero-custody) before
beginning. Do not rely on memory for policy details.

**OWASP Top 10 — check each category:**

1. **Injection**: Parameterized queries everywhere? No string concatenation in SQL/commands?
   XSS prevention in all rendered output? If yes for each → PASS.

2. **Broken Authentication**: Tokens and sessions handled per existing platform patterns?
   No custom auth logic (use platform middleware)? Credentials not stored client-side?

3. **Sensitive Data Exposure**: No PII, PHI, or health data in logs, error messages,
   or API responses beyond what the feature requires? HTTPS enforced?

4. **XML/XXE and Injection variants**: External XML/JSON parsed safely? No DTD processing?

5. **Broken Access Control**: Resource ownership checked on every write? No IDOR vectors?
   Role checks present and consistent with portal IAM model (ADR-023)?

6. **Security Misconfiguration**: No debug flags, verbose errors, or permissive CORS
   in production config? All new environment variables documented?

7. **Vulnerable Components**: Any new dependency with a known CVE? Check PyPI / npm
   advisory databases.

8. **Insecure Deserialization**: No `pickle`, `eval`, or `exec` on untrusted input?

9. **Insufficient Logging**: Are security-relevant events logged (auth failures,
   access denials, data write operations)?

10. **SSRF**: Any new HTTP client code? Does it restrict target URLs to expected hosts?

**Zero-custody check (ADD-009):**
Does any new code path write owner data to a YourAmaryllis-controlled bucket or service?
If yes, is it going through the S3 proxy with seller storage only (ADD-024)?
State explicitly: ZERO-CUSTODY PRESERVED or VIOLATION DETECTED.

**IAM check:**
List any new IAM policies or role modifications. Flag any `*` actions or resources
without explicit justification.

**SBOM:**
List every new dependency introduced by this change:
| Package | Version | License | Risk |
|---------|---------|---------|------|

Flag any non-commercially-permissive license (GPL, AGPL, SSPL, Commons Clause).

**Final gate**: APPROVED (no Critical/High findings) or BLOCKED (list blockers).
