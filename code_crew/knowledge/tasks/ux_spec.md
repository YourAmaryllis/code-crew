---
type: CrewAI Task
title: UX Specification
description: UX Lead fetches the Figma design, extracts a component spec and design tokens, and writes them to disk for the engineer
tags: [ux, figma, spec, design-tokens, components]
agent: ux_lead
expected_output: >
  Confirmation that spec.md and tokens.json have been written to
  .code-crew/ux/<ISSUE-KEY>/, followed by a summary of the component hierarchy,
  variant count, token count, and any open questions requiring clarification.
---

Produce a complete, implementation-ready specification from the Figma design.

**Step 1 — Get the Figma URL.**

Check the ticket context for `figma_url`. If it is present, use it.
If it is absent or empty, call `ask_human`:
```
The Figma URL for <ISSUE-KEY> is not in the ticket.
Please paste the Figma link for the component or screen to implement.
```

**Step 2 — Fetch the frame.**

Use `figma_reader` with `operation: get_frame` and the Figma URL.

If the URL does not include a `?node-id=` parameter, the response will be the top-level
page structure. Ask the human to provide the specific frame URL with node-id if the
top-level structure is too broad:
```
The Figma URL does not target a specific frame.
Please paste the URL with the exact frame selected (the address bar updates when you
click a frame in Figma).
```

**Step 3 — Fetch design tokens.**

Use `figma_reader` with `operation: get_tokens` and the same URL.

**Step 4 — Check for an existing design system.**

Use `workspace_reader` to look for:
- Token files: `tokens.json`, `design-tokens.json`, `theme.ts`, `theme.go`, `tokens/`
- Component primitives: `components/ui/`, `ui/`, `pkg/ui/`, `src/components/shared/`

Note any reusable primitives so the engineer uses them rather than recreating.

**Step 5 — Write the spec.**

Create `.code-crew/ux/<ISSUE-KEY>/` via `platform_shell`:
```bash
mkdir -p .code-crew/ux/<ISSUE-KEY>
```

Write `.code-crew/ux/<ISSUE-KEY>/spec.md` with the full UX spec following the format
in the ux_lead agent instructions:
- Component hierarchy
- Props/API table
- Variants and states table
- Design tokens used
- Accessibility requirements checklist
- Responsive behaviour

**Step 6 — Write design tokens.**

Write `.code-crew/ux/<ISSUE-KEY>/tokens.json` with the extracted token map:
```json
{
  "colors": {
    "primary": "#1a73e8",
    "surface": "#ffffff"
  },
  "typography": {
    "body": { "fontFamily": "Inter", "fontSize": "16px", "fontWeight": 400 }
  },
  "spacing": {
    "sm": "8px",
    "md": "16px",
    "lg": "24px"
  }
}
```

Map Figma style names to their resolved values. For colour fills, use the hex value
extracted from the node tree. For spacing, infer from layout gap and padding values.

**Completion:**

End with a summary:
```
UX SPEC WRITTEN: .code-crew/ux/<ISSUE-KEY>/spec.md
  Component: <name>
  Variants: <N> states
  Design tokens: <N> mapped
  Existing primitives found: <list or "none">
  Open questions: <list or "none">
```
