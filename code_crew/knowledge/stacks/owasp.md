---
name: Compliance-OWASP
description: OWASP ASVS L2 and Top 10 detailed checklist for code review — verification requirements by category with specific test patterns
metadata:
  type: compliance
  framework: OWASP
  references:
    - "OWASP Top 10 2021"
    - "OWASP ASVS 4.0 Level 2"
    - "OWASP API Security Top 10 2023"
  activate: explicitly — recommended for all web/API projects; set in CODE_CREW_STACKS or stacks: in .code-crew/config.yaml
---

# Compliance: OWASP

OWASP Top 10 and ASVS (Application Security Verification Standard) Level 2 are the baseline for web application and API security. ASVS L2 is appropriate for most applications handling sensitive data. L3 (hardware-backed security) is for high-value targets.

Add `owasp` to `stacks:` for any web application or API. This provides a more detailed checklist than the baseline OWASP check built into the security_lead agent.

---

## A01 — Broken Access Control

- [ ] Every endpoint that returns or mutates data checks authorization server-side (do not rely on client-side checks or URL obscurity)
- [ ] IDOR (Insecure Direct Object Reference) prevented: ownership checked before returning `GET /resource/:id`; user can only access their own resources
- [ ] Path traversal prevented: file path inputs sanitized; no `../` sequences reach the filesystem
- [ ] CORS policy explicit and restrictive: `Access-Control-Allow-Origin` is not `*` on authenticated endpoints
- [ ] Privilege escalation: users cannot change their own role, group, or permission level
- [ ] Force browsing prevented: authenticated pages return 401/403, not a redirect to login (which leaks page existence)
- [ ] JWT / session tokens validated on every request: not just checked for format but verified signature and expiry

## A02 — Cryptographic Failures

- [ ] No sensitive data transmitted over HTTP (enforce HSTS; all redirects to HTTPS)
- [ ] No sensitive data in browser URL, query string, or referrer header
- [ ] Passwords hashed with bcrypt, scrypt, Argon2, or PBKDF2 — never MD5, SHA-1, or unsalted SHA-256
- [ ] Sensitive data (PII, health data, financial data) encrypted at rest
- [ ] Encryption keys not stored alongside encrypted data or in source code
- [ ] TLS 1.2+ enforced; no fallback to older protocols (see `fips-140-3` for algorithm specifics)
- [ ] No deprecated crypto: no MD5, RC4, DES, 3DES in any path

## A03 — Injection

- [ ] SQL: parameterized queries or prepared statements everywhere; no string concatenation with user input
- [ ] NoSQL: queries use structured API (not string interpolation of filter objects)
- [ ] Command injection: `exec`, `system`, `subprocess` calls do not include unsanitized user input; prefer library calls over shell invocation
- [ ] LDAP injection: LDAP queries parameterized if applicable
- [ ] XSS (output injection): all user-controlled output escaped for the output context (HTML, JS, CSS, URL, JSON)
- [ ] Template injection: no user-controlled input passed to template engines that execute code (`eval`, `render` with string interpolation)
- [ ] Log injection: user input sanitized before logging (strip newlines to prevent log forging)

## A04 — Insecure Design

- [ ] Threat model updated for any new trust boundary, data flow, or privilege boundary
- [ ] Business logic flaws: rate limiting on any action with economic value (purchase, coupon redemption, file upload)
- [ ] Anti-automation: CAPTCHA or token bucket on account creation, login, password reset
- [ ] Workflow enforcement: multi-step processes cannot be short-circuited (e.g. skip payment step)

## A05 — Security Misconfiguration

- [ ] No debug mode, stack traces, or verbose error messages in production responses
- [ ] Default credentials changed on all services (databases, admin interfaces, message brokers)
- [ ] Unnecessary features, ports, and services disabled in production containers/instances
- [ ] Security headers present: `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options` (or `Content-Security-Policy` with `frame-ancestors`), `Referrer-Policy`
- [ ] `Content-Security-Policy` defined and does not include `unsafe-eval` or `unsafe-inline`
- [ ] Directory listing disabled on web server; no `.env`, `.git`, or config files accessible at web root
- [ ] `OPTIONS` method returns only the methods in actual use

## A06 — Vulnerable and Outdated Components

- [ ] All new dependencies checked for known CVEs before inclusion (npm audit, pip-audit, govulncheck, Trivy)
- [ ] No dependency with a Critical or High CVE included without explicit documented exception
- [ ] No dependency with no releases in > 2 years without documented rationale
- [ ] Container base image pinned to a digest (not `latest`); scanned for vulnerabilities
- [ ] Transitive dependency graph reviewed for any new indirect dependency pulling in known-bad packages

## A07 — Identification and Authentication Failures

- [ ] Password requirements meet NIST 800-63B: minimum 8 chars; no complexity requirements that reduce entropy; check against breached password list
- [ ] Account lockout or exponential backoff after repeated failed authentication
- [ ] Password reset: tokens are time-limited (≤ 15 min), single-use, and sent to verified address only
- [ ] Multi-factor authentication available (required for privileged users)
- [ ] Session tokens: cryptographically random, ≥ 128 bits entropy, invalidated on logout and password change
- [ ] Remember-me tokens: separate long-lived token (not the session ID), rotated on use, revocable

## A08 — Software and Data Integrity Failures

- [ ] Dependencies fetched from authoritative sources with integrity verification (lock files, checksums, signed packages)
- [ ] CI pipeline code (GitHub Actions, GitLab CI) uses pinned action versions with SHA; no `@latest`
- [ ] Deserialization of untrusted data uses safe parsers: JSON only (no pickle, no Java serialization, no YAML with tags on untrusted input)
- [ ] Auto-update mechanisms verify signatures before applying

## A09 — Security Logging and Monitoring Failures

- [ ] Authentication events logged: success, failure (with reason), account lockout
- [ ] Authorization failures logged: user, resource, action, timestamp
- [ ] High-value transactions logged: financial operations, account changes, permission changes
- [ ] Log entries do not contain passwords, tokens, or full PAN/SSN
- [ ] Logs are shipped to a centralized store the application cannot modify
- [ ] Alerts configured for: repeated authentication failures, access pattern anomalies, critical error spikes

## A10 — Server-Side Request Forgery (SSRF)

- [ ] Any feature that fetches a URL supplied by user input validates the target against an allowlist of hosts/schemes
- [ ] Internal network addresses (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16, localhost) blocked for user-supplied URLs
- [ ] Cloud metadata endpoints (169.254.169.254 for AWS/GCP/Azure) explicitly blocked
- [ ] Redirect following disabled or checked against allowlist after each hop

---

## OWASP API Security Top 10 (2023) — for REST/GraphQL/gRPC APIs

- [ ] **API1 Broken Object Level Authorization**: every API endpoint verifies the caller owns or has access to the requested object ID
- [ ] **API2 Broken Authentication**: API tokens validated on every call; no long-lived tokens without rotation
- [ ] **API3 Broken Object Property Level Auth**: API does not expose fields the caller shouldn't see; no mass assignment of protected fields
- [ ] **API4 Unrestricted Resource Consumption**: rate limiting, request size limits, and pagination enforced on all public endpoints
- [ ] **API5 Broken Function Level Auth**: admin-only endpoints return 403 (not 404) for unauthorized callers; no hidden admin paths discoverable by enumeration
- [ ] **API6 Unrestricted Access to Sensitive Business Flows**: business-logic-sensitive flows (checkout, verification, password reset) rate-limited and monitored
- [ ] **API7 SSRF**: covered above
- [ ] **API8 Security Misconfiguration**: see A05 above; additionally: no GraphQL introspection in production
- [ ] **API9 Improper Inventory Management**: new API version or endpoint added to API inventory; deprecated endpoints removed or access-restricted
- [ ] **API10 Unsafe Consumption of APIs**: third-party API responses validated and sanitized; error handling does not leak third-party data to callers

---

## Common Violations (flag as CRITICAL or HIGH)

- Missing server-side authorization check on any data endpoint (IDOR)
- SQL query using string concatenation with user input
- User-controlled output rendered without escaping (XSS)
- MD5 or SHA-1 for password hashing
- Debug error messages or stack traces in production responses
- Dependency with Critical CVE included
- User-supplied URL fetched without allowlist validation (SSRF)
- Authentication token not invalidated on logout

---

## Review Output Format

```
OWASP REVIEW
Surface area: [Web App / REST API / GraphQL / gRPC / CLI / other]

A01 Broken Access Control:     PASS / FAIL — [detail]
A02 Cryptographic Failures:    PASS / FAIL — [detail]
A03 Injection:                 PASS / FAIL — [detail]
A04 Insecure Design:           PASS / FAIL / N/A
A05 Security Misconfiguration: PASS / FAIL — [detail]
A06 Vulnerable Components:     PASS / FAIL — [dependencies checked]
A07 Auth Failures:             PASS / FAIL — [detail]
A08 Integrity Failures:        PASS / FAIL — [detail]
A09 Logging/Monitoring:        PASS / FAIL — [detail]
A10 SSRF:                      PASS / FAIL / N/A

API Security (if applicable):  PASS / FAIL — [detail]

OWASP: COMPLIANT or NON-COMPLIANT — [list of blocking findings]
```
