---
type: CrewAI Task
title: Draft Architecture Design Document
description: Architect creates or updates an ADD based on the requirements analysis, covering components, data flows, interfaces, and tech stack choices
tags: [design, architecture, add, pre-implementation]
agent: architect
expected_output: >
  A complete draft ADD in OKF YAML format covering: component structure, data flows,
  API contracts (if applicable), tech stack choices, trust boundaries, and open questions
  flagged for security/compliance review. Includes the full OKF frontmatter (type, title,
  description, stacks, references) and body sections.
---

Draft the Architecture Design Document for this requirement.

**Step 1 — Review requirements analysis.**

Your context includes the requirements analysis from the previous task. Use it to:
- Know which ADD number to assign or which existing ADD to update
- Understand the key decisions to resolve
- Know which existing ADDs/ADRs are relevant constraints

**Step 2 — Load existing constraints.**

Use `knowledge_reader` to load any referenced ADDs (from the requirements analysis). These are hard constraints — the draft ADD must conform to them.

Use `workspace_reader` to inspect the existing code structure and understand current component boundaries.

**Step 3 — Draft the ADD.**

Produce a complete ADD document following OKF format. Include all sections:

```yaml
---
type: ADD
title: "ADD-NNN: Short Title"
description: One-sentence summary of what this document specifies
tags:
  - add
  - short-slug
stacks:
  - go-backend        # list only the stacks this ADD applies to
references:
  - ADD-NNN           # internal references
  - https://...       # external specs
status: Draft
date: YYYY-MM-DD
resource: designs/ADD/ADD-NNN-Short-Title.md
---
```

Then write the body sections:
- **Context** — why this design decision is needed
- **Components** — new or changed services, their responsibilities
- **Data Flows** — key data paths, API contracts, message formats
- **Tech Stack Choices** — which technology and why (reference existing ADRs when following established patterns)
- **Trust Boundaries** — new trust boundaries introduced; flag for threat modeling
- **Open Questions** — decisions deferred to security or compliance review
- **Constraints** — must-conform rules from referenced ADDs/ADRs

**Step 4 — Flag for specialist review.**

At the end, list:
- SECURITY REVIEW NEEDED: [specific concern] — for the security lead
- COMPLIANCE REVIEW NEEDED: [specific concern] — for the compliance officer
- HUMAN DECISION NEEDED: [specific option question] — items requiring chief architect judgment
