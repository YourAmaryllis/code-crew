---
type: CrewAI Task
title: UX Review
description: UX Lead verifies the implemented component matches the Figma spec and meets WCAG 2.1 AA accessibility requirements
tags: [ux, review, accessibility, wcag, design-spec]
agent: ux_lead
expected_output: >
  A structured review verdict following the UX REVIEW format in the ux_lead agent
  instructions. Ends with either:
  APPROVED — component matches spec and meets WCAG 2.1 AA
  REVISION NEEDED: <itemised list of required changes>
---

Verify the implemented component against the UX spec and accessibility requirements.

**Step 1 — Load spec and implementation.**

Read:
- `.code-crew/ux/<ISSUE-KEY>/spec.md` — the source of truth (from ux_spec task)
- `.code-crew/ux/<ISSUE-KEY>/tokens.json` — expected token values
- The component file(s) listed in the COMPONENT COMPLETE output from ux_implementation

**Step 2 — Structure and props check.**

Compare the component's props/interface against the spec API table:
- Every documented prop is present with the correct type
- No undocumented required props (breaks callers)
- Default values match the spec

**Step 3 — Visual fidelity check.**

For each variant/state in the spec:
1. Verify the state is handled in the component logic
2. Check that colours, typography, and spacing use tokens from `tokens.json` — not hardcoded values
3. Use `figma_reader` with `operation: get_image` to get the rendered PNG if visual comparison is needed

**Step 4 — Accessibility audit.**

Check the implementation against the WCAG 2.1 AA checklist from the ux_lead agent instructions:
- 1.1.1 Non-text content: accessible names present
- 1.4.3 Colour contrast: check declared colour values vs WCAG ratios
- 2.1.1 Keyboard: all interactions reachable via Tab/Enter/Space/Arrow
- 2.4.7 Focus visible: no bare `outline: none` without a replacement
- 4.1.2 ARIA: correct role, `aria-expanded`, `aria-selected`, etc. per component type

**Step 5 — Output the verdict.**

Follow the review output format from the ux_lead agent instructions.

If APPROVED: no further action needed.

If REVISION NEEDED: itemise each required change with:
- Which spec requirement is violated
- Where in the code the issue is (file, line or component section)
- What the fix should be

End with exactly:
```
APPROVED
```
or:
```
REVISION NEEDED: <itemised list>
```
