---
type: CrewAI Task
title: UX Implementation
description: Engineer implements the component from the UX spec, using existing design system primitives and tokens
tags: [ux, component, implementation, design-tokens, accessibility]
agent: engineer
expected_output: >
  Confirmation that the component file(s) have been written, including file paths and
  a brief summary of props implemented, states handled, and token usage.
  Ends with: COMPONENT COMPLETE: <comma-separated list of files written>
---

Implement the component from the UX spec produced by the UX Lead.

**Step 1 — Read the spec.**

Read `.code-crew/ux/<ISSUE-KEY>/spec.md` using `workspace_reader`.
Read `.code-crew/ux/<ISSUE-KEY>/tokens.json` for design token values.

**Step 2 — Check the stack and existing design system.**

Use `workspace_reader` to understand:
- The component pattern in this stack (look at 2-3 existing components for conventions)
- How design tokens are consumed (CSS vars, theme object, constants file)
- The testing pattern for components (unit test, Storybook story, or BDD)

Follow the stack conventions exactly — do not introduce a new pattern.

**Step 3 — Implement the component.**

Write the component in the appropriate location per the stack's scaffold pattern:
- `typescript-react`: `src/components/<ComponentName>/<ComponentName>.tsx` + `.test.tsx`
- `go-backend` (server-rendered): `internal/ui/<component>/` with template + handler
- `python`: `src/components/<component_name>.py` or Jinja template

Requirements (verify each against the spec before writing):
1. **Props**: implement all props from the spec API table with correct types
2. **Variants**: implement all states (hover, focus, disabled, error, loading)
3. **Tokens**: use design tokens from `tokens.json` — no hardcoded hex colours or magic pixel values
4. **Accessibility**: 
   - All interactive elements have an accessible name (`aria-label`, `alt`, or visible label)
   - Focus is visible and keyboard-navigable
   - ARIA roles and states match the component type
5. **Responsive**: implement responsive constraints from the spec

**Step 4 — Write a basic test.**

Write the minimum test that fails if the component's contract breaks:
- Renders without error
- Renders all documented variants/states
- Required props cause a type error if omitted (TypeScript) or a test failure (others)

**Completion:**

End with:
```
COMPONENT COMPLETE: <comma-separated list of files>
```
