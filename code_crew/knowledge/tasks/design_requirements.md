---
type: CrewAI Task
title: Design Requirements Analysis
description: Chief Architect reads the requirement ticket, loads existing ADDs/ADRs, and defines the design scope and decisions to be made
tags: [design, architecture, requirements, pre-implementation]
agent: architect
expected_output: >
  A structured requirements analysis covering:
  (1) What needs to be designed — new service, new feature, new integration, or existing component change;
  (2) Relevant existing ADDs and ADRs (by number and summary);
  (3) Key design decisions to be made — list each as a question;
  (4) Which ADD number to create (next available) or which existing ADD to update;
  (5) Any regulatory/compliance flags that need input from security or compliance.
---

Analyse the requirement and scope the design work.

**Step 1 — Read the requirement.**

Load the issue ticket with `jira_view`. Understand:
- What change is being requested?
- Who are the actors and what data is involved?
- What are the acceptance criteria?

**Step 2 — Load existing design documents.**

Use `knowledge_reader` to load:
- `architecture-decisions` — OKF structure and ADD/ADR guidelines
- `sad-maintenance` — when to update the SAD
- The ADD index (if available) to find the next ADD number

Search `designs/ADD/` and `designs/ADR/` with `workspace_reader` for any existing documents that cover:
- The affected service or component
- The data or domain being changed
- Any referenced ADD numbers in the ticket

**Step 3 — Identify design decisions.**

List each architectural decision point as a question, for example:
- "Should this be a new service or an extension of the existing X service?"
- "Should this data live in the existing PostgreSQL schema or a separate store?"
- "Does this require a new trust boundary in the threat model?"

**Step 4 — Determine ADD/ADR scope.**

Based on the above:
- Is a **new ADD** needed? → Propose the next ADD-NNN number.
- Should an **existing ADD be updated**? → Name it.
- Is a **new ADR** needed for a key architectural decision? → Name the decision.
- Does the **SAD** need updating? → Identify which section.

Output a clear scope statement: what documents will be created or updated.
