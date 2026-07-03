---
type: CrewAI Task
title: OTM Threat Model Patch
description: Architect applies targeted fixes to an existing OTM YAML based on the manager's revision feedback, without re-reading all source files
tags: [threat, threat-model, otm, patch, revision]
agent: architect
expected_output: >
  The complete corrected OTM YAML with all manager-identified gaps fixed.
  Ends with OTM BUILD COMPLETE.
---

You are patching an existing OTM YAML to address specific gaps identified by the manager.

**Do not redo the full threat model from scratch.** Read only the files needed to fill
the specific gaps listed below. Fix those gaps, then output the complete corrected OTM.

**CRITICAL — same rules as before:**
1. Do NOT write any files. Do NOT use `platform_shell` to run `cat >`, `echo >`, `tee`,
   or any command that writes to disk. Output the YAML as plain text in your response.
2. Your only tools are `workspace_reader` (read source files) and `platform_shell` for
   `find`, `grep`, `ls`, `cat` discovery only — never to write files.

---

## What to fix

The manager's revision feedback is listed in the task context under
"## Manager revision feedback". Address every item.

The task context includes **pre-scanned files** and **Terraform deployment references**.
Use those first. Only call `workspace_reader` or `platform_shell` for specific files that
are not already in the context. Do NOT search `ops/` — Terraform information is pre-injected.
If you search for something twice and find nothing, accept the default and note `# inferred`.

For each gap:
- If it requires looking up a value (e.g., whether Redis is encrypted, what PHI flows through
  a component): check the pre-scanned context first. If not there, read ONE specific file that
  would confirm it. If still not determinable, use a reasonable default and note `# inferred`.
- If it's a naming issue: apply the new name throughout (component id, dataflow references,
  threat targetedComponents, mitigation references — keep everything consistent).
- If it's a missing attribute: add it in the correct YAML location.

---

## YAML quoting rules — violations cause parse errors

- Any string containing `:`, `#`, `[`, `]`, `{`, `}` MUST be quoted
- Use single quotes: `description: 'FHIR Proxy validates and merges FHIR R4 resources'`
- `description` fields almost always need quotes — they frequently contain colons
- `likelihood` and `impact` must always be `likelihood: HIGH` (key: value), never bare `HIGH`

---

## Output

Output the **complete** corrected OTM YAML (not just the changed sections).
End with exactly:
```
OTM BUILD COMPLETE
```
