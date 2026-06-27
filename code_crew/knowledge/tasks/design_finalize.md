---
type: CrewAI Task
title: Design Finalization and Publication
description: Chief Architect synthesizes all input into a final ADD (and optional ADR), writes files to designs/, commits, and updates the issue ticket
tags: [design, architecture, add, adr, publish, pre-implementation]
agent: architect
expected_output: >
  Confirmation of files written to designs/ADD/ and designs/ADR/ (if applicable),
  git commit SHA, and the comment posted to the issue ticket listing the created
  documents. Format: DESIGN COMPLETE: [list of files]. Or DESIGN BLOCKED: [reason]
  if security or compliance raised unresolved blocking concerns.
---

Synthesize all design input into final documents, commit them, and update the issue ticket.

**Step 1 — Review all previous task outputs.**

Your context includes:
- Requirements analysis (scope, ADD number, existing ADDs)
- Draft ADD (components, data flows, tech choices, open questions)
- Security addendum (data classification, controls, threat model path)
- Compliance addendum (retention, consent, audit trail, documentation obligations)

If any task concluded with SECURITY CONCERNS or COMPLIANCE CONCERNS, stop and output:
```
DESIGN BLOCKED: <list of unresolved concerns>
```
Do not proceed until these are resolved (they will require a human to clarify the requirement or adjust the design).

**Step 2 — Finalize the ADD.**

Merge the draft ADD with the security and compliance addenda. The final ADD must include all sections:
- Context
- Components
- Data Flows
- Tech Stack Choices
- Trust Boundaries
- Security Requirements (from security review)
- Compliance Requirements (from compliance review)
- Constraints
- Open Questions (any remaining items deferred to implementation)

Write the final ADD to `designs/ADD/ADD-NNN-Title.md` using `platform_shell`.

The OKF frontmatter `references` field must include all ADDs and ADRs cited in the body.

**Step 3 — Write ADR (if a new architectural decision was made).**

If the requirements analysis identified a key architectural decision that needs an ADR, write it:
```
designs/ADR/ADR-NNN-Decision-Title.md
```

ADR format:
```markdown
---
type: ADR
title: "ADR-NNN: Decision Title"
status: Accepted
date: YYYY-MM-DD
---

## Context
<why the decision was needed>

## Decision
<what was decided>

## Consequences
<what this means for the codebase going forward>
```

**Step 4 — Branch, commit, push, create PR, and merge.**

The Chief Architect has already approved this design in the code-crew session. Create a branch, commit, push, open a PR, and merge it.

```bash
# Create branch in designs repo
git checkout -b design/<ISSUE-KEY>
git add designs/ADD/ designs/ADR/
git commit -m "design(ADD-NNN): <short title> (<ISSUE-KEY>)"

# Push to origin
git push -u origin design/<ISSUE-KEY>

# Create PR — Chief Architect reviewed and approved in code-crew session
gh pr create \
  --title "design: ADD-NNN <short title> (<ISSUE-KEY>)" \
  --body "$(cat <<'EOF'
Reviewed and approved by Chief Architect in code-crew session.

**Documents:**
- designs/ADD/ADD-NNN-Title.md
- designs/ADR/ADR-NNN-Title.md (if applicable)
- designs/TMD/<service>.yaml (threat model stub)

**Issue:** <ISSUE-KEY>
EOF
)"

# Merge immediately — Chief Architect approval already granted
gh pr merge --merge --delete-branch
```

**Step 5 — Update the issue ticket.**

Post a comment to the issue with the list of created documents:

For Jira:
```bash
jira issue comment add <ISSUE-KEY> --body "Design docs created for this issue:

- [ADD-NNN: Title](designs/ADD/ADD-NNN-Title.md)
- [ADR-NNN: Decision](designs/ADR/ADR-NNN-Title.md) ← if applicable

Threat model stub: designs/TMD/<service>.yaml (to be populated during implementation)

Ready for implementation: /issue <ISSUE-KEY>"
```

For Linear or GitHub: use the equivalent CLI comment command.

**Completion signal:**

End with exactly one of:
- `DESIGN COMPLETE: <comma-separated list of files created/updated>`
- `DESIGN BLOCKED: <reason — must be resolved before implementation can begin>`
