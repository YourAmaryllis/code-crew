---
type: CrewAI Task
title: Verify Report
description: Scrum master compiles all scan findings, pass items, and chief review decisions into a markdown report
tags: [verify, report, scrum-master]
agent: scrum_master
expected_output: >
  Full markdown report content compiled from all scan outputs and chief review decisions.
  Includes per-scan breakdown of findings AND pass items. Ends with REPORT SAVED: .code-crew/audit-YYYYMMDD-HHMMSS.md.
---

Compile the verification audit into a structured markdown report and output it.
The Python runner will write the file.

**Step 1 — Collect inputs.**

Your context contains the outputs of `verify_arch_scan`, `verify_security_scan`,
`verify_compliance_scan`, `verify_domain_scan`, and `verify_chief_review`. From each scan:
- Collect all `FINDING` lines (tagged [ARCH], [SEC], [COMP], [DOMAIN])
- Collect all `PASS` lines
- Collect all `INFO` lines

From the chief review:
- All `REQUIRED:` decisions
- All `EXEMPT:` decisions
- All `PASS:` decisions

**Step 2 — Output the full report in this format.**

```markdown
# Verification Report

**Date:** YYYY-MM-DD  
**Project:** <cwd name>  
**Scans run:** Architecture · Security · Compliance · Domain  

---

## Summary

| Status    | Count |
|-----------|-------|
| REQUIRED (must fix) | N |
| EXEMPT (accepted risk) | N |
| FINDING (open, not yet triaged) | N |
| PASS (clean checks) | N |
| INFO (notable, not a violation) | N |

---

## Required Fixes

> These must be resolved before the next production release.

- **[ARCH]** Description — file:line
- **[SEC]** Description — file:line  [SEVERITY]
- **[COMP]** Description — data field or endpoint

---

## Exemptions

| Finding | Reason |
|---------|--------|
| [ARCH] Description | Reason provided by Chief Architect |

---

## Scan Details

### Architecture

**Findings:**
- [ARCH] <finding text>

**Passed:**
- [ARCH] <pass text>

**Info:**
- [ARCH] <info text>

---

### Security

**Findings:**
- [SEC] <finding text>

**Passed:**
- [SEC] <pass text>

---

### Compliance

**Compliance standards in scope:** HIPAA, SOC 2  ← list from structure.md or INFO if none

**Findings:**
- [COMP] <finding text>

**Passed:**
- [COMP] <pass text>

**Info:**
- [COMP] <info text>

---

### Domain

**Findings:**
- [DOMAIN] <finding text>

**Passed / Info:**
- [DOMAIN] <pass or info text>

---
```

End your output with exactly:
```
REPORT SAVED: .code-crew/audit-<YYYYMMDD-HHMMSS>.md
```
