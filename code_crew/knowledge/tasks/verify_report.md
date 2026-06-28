---
type: CrewAI Task
title: Verify Report
description: Scrum master compiles all scan findings and chief review decisions into a markdown report
tags: [verify, report, scrum-master]
agent: scrum_master
expected_output: >
  Full markdown report content compiled from all scan outputs and chief review decisions.
  Ends with REPORT SAVED: .code-crew/verify-report-YYYYMMDD.md.
---

Compile the verification audit into a structured markdown report and output it. The Python runner will write the file.

**Step 1 — Collect inputs.**
Your context contains the outputs of `verify_arch_scan`, `verify_security_scan`, `verify_compliance_scan`, `verify_domain_scan`, and `verify_chief_review`. Extract:
- All `REQUIRED:` lines from the chief review
- All `EXEMPT:` lines from the chief review
- All `PASS:` lines from the chief review

**Step 2 — Output the full report in this format.**

```markdown
# Verification Report

**Date:** YYYY-MM-DD  
**Project:** <cwd name>  
**Scans run:** Architecture · Security · Compliance · Domain  

---

## Summary

| Status | Count |
|--------|-------|
| REQUIRED (must fix) | N |
| EXEMPT (accepted risk) | N |
| PASS (clean or false positive) | N |

---

## Required Fixes

> These must be resolved before the next production release.

- **[ARCH]** Description — file:line
- **[SEC]** Description — file:line
- **[COMP]** Description — data field or endpoint

---

## Exemptions

| Finding | Reason |
|---------|--------|
| [ARCH] Description | Reason provided by Chief Architect |

---

## Appendix — All Pass Items

<plain list of PASS lines>
```

End your output with exactly:
```
REPORT SAVED: .code-crew/verify-report-<YYYYMMDD>.md
```
