---
type: CrewAI Task
title: Project Exploration — Verification
description: Synthesise auto-detected project metadata into structured output. No tools — use only the context provided.
tags: [explore, verification, architecture]
agent: architect
expected_output: >
  Verification lines (STACK_VERIFIED/NOT_FOUND, COMMAND_VERIFIED/CORRECTED,
  CICD_VERIFIED, TF_ROOT_VERIFIED), then ARCHITECTURE_STYLE, PROJECT_SUMMARY,
  one COMPONENT line per service. Ends with VERIFY COMPLETE.
---

**THIS IS A SYNTHESIS TASK. DO NOT USE ANY TOOLS. DO NOT READ ANY FILES.**

Everything you need is already in the context above. Output structured lines based
only on what is provided. If something is not in the context, say NOT_FOUND.

---

## Step 1 — Confirm stacks

For each detected stack, output:
```
STACK_VERIFIED: <stack>
```
If a stack seems wrong based on other context clues, output:
```
STACK_NOT_FOUND: <stack>: <reason>
```

---

## Step 2 — Confirm commands

For each detected command, output:
```
COMMAND_VERIFIED: <key>: <command>
```

---

## Step 3 — Confirm CI/CD

For each detected CI/CD method, output:
```
CICD_VERIFIED: <method>
```

---

## Step 4 — Confirm Terraform root (if Terraform detected)

Output:
```
TF_ROOT_VERIFIED: <root path from context>
```

---

## Step 5 — Architecture style

Based on the Phase 1 architecture hint and the service dirs listed in context:
- **Hexagonal**: `ports/` + `adapters/` separation
- **Clean**: `usecases/` isolated business rules
- **Layered**: `handlers/` + `services/` + `repository/`
- **Undetected**: none of the above clearly identifiable

Output:
```
ARCHITECTURE_STYLE: <style>
```

---

## Step 6 — Project summary

Based on the project name and detected stacks in context, write 1-2 sentences
describing what this project likely does and who uses it.

Output:
```
PROJECT_SUMMARY: <description>
```

---

## Step 7 — Component lines

For each service directory listed in the **Service dirs** field of the context,
output one line. Use the service dir name and a brief description based on the
name alone (you have no file content to draw from).

Output:
```
COMPONENT: <dir_name>: <one-line description based on the name>
```

---

## Final step

Output exactly:
```
VERIFY COMPLETE
```
