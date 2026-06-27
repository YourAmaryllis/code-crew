---
type: CrewAI Task
title: Verify Report
description: Scrum master compiles all scan findings and chief review decisions into a markdown report and saves it to .code-crew/
tags: [verify, report, scrum-master]
agent: scrum_master
expected_output: >
  Confirmation that the report was written to .code-crew/verify-report-YYYYMMDD.md,
  followed by the full report content. Ends with REPORT SAVED: <path>.
---

Compile the verification audit into a structured markdown report and save it to `.code-crew/`.

**Step 1 — Collect inputs.**
Your context contains the outputs of `verify_arch_scan`, `verify_security_scan`, `verify_compliance_scan`, and `verify_chief_review`. Extract:
- All `REQUIRED:` lines from the chief review
- All `EXEMPT:` lines from the chief review
- All `PASS:` lines from the chief review (optional — include in appendix)

**Step 2 — Write the report.**

Use `platform_shell` to write the file. Report format:

```markdown
# Verification Report

**Date:** YYYY-MM-DD  
**Project:** <project name from .code-crew/config.yaml or cwd name>  
**Scans run:** Architecture · Security · Compliance  

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

<collapsible or plain list of PASS lines>
```

Save to: `.code-crew/verify-report-<YYYYMMDD>.md` (use today's date).

**Step 3 — Output.**

Print the full report content, then end with exactly:
```
REPORT SAVED: .code-crew/verify-report-<YYYYMMDD>.md
```
