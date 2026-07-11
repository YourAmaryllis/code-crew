---
type: CrewAI Task
title: Domain Summarization
description: Summarize one domain directory within a service based on pre-read context. No tools.
tags: [explore, summarize, domain]
agent: architect
expected_output: >
  Structured DOMAIN_SUMMARY block with PURPOSE, SENSITIVITY, SEPARATE_OTM, and REASON.
  Ends with DOMAIN_SUMMARY COMPLETE.
---

**DO NOT USE ANY TOOLS. All information needed is already in the context above.**

Read the provided domain module information and produce a concise structured summary.
A domain directory is a subdirectory inside a larger service that may represent a distinct
business capability or security boundary.

Output exactly this format:

```
DOMAIN_SUMMARY: <domain-name> (in <service-name>)
PURPOSE: <1-2 sentences — what this domain handles, what data it touches>
SENSITIVITY: phi | pii | financial | public | none
SEPARATE_OTM: yes | no
REASON: <one sentence explaining the decision>
DOMAIN_SUMMARY COMPLETE
```

**SEPARATE_OTM guidance** — answer `yes` only if the domain meets at least one of:
- Has its own deployment unit (its name appears in the infrastructure modules list in context)
- Has its own sub-executable / binary entry point
- Handles significantly different data sensitivity than the rest of the parent service
- Is called out as a distinct component in the architecture documentation

Answer `no` if it is an internal module, utility package, or adapter — even if it is large.
