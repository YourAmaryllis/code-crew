---
type: CrewAI Task
title: Frontend Implementation
description: Build React + Ant Design v6 components with tests, loading/error/empty states, a11y
tags: [frontend, react, typescript, antd, a11y, phase-17]
timestamp: 2026-06-17T00:00:00Z
agent: frontend_developer
context_agents:
  - tech_lead
  - qa_engineer
expected_output: >
  React component implementation plan with: file paths, component structure,
  Ant Design components to use, state diagram (loading/error/empty/loaded),
  accessibility notes, and unit test stubs. If code generation is in scope,
  full component implementation with passing unit tests.
---

Implement the frontend feature for the user story in the sprint input.

**Step 1 — Confirm Figma link.** The Figma design link must be in the Jira story.
If it is missing, output a blocker and stop — do not guess at visual design.

**Step 2 — Plan the component structure.**
- List every React component needed (container, presentational, sub-components)
- Map each to its Figma frame
- Identify which Ant Design v6 components to use for each UI element
- Define state shape: what data is needed, where it comes from (API hook, props, context)

**Step 3 — Define states.** For each data-fetching component, define:
- **Loading**: what the user sees while data is fetching
- **Error**: what the user sees if the request fails (with retry affordance if appropriate)
- **Empty**: what the user sees if the data is empty
- **Loaded**: the primary state with real data

**Step 4 — Accessibility plan.**
- List all interactive elements and their ARIA roles/labels
- Confirm keyboard navigation path through the component
- Check color contrast of all text against background (WCAG 2.1 AA minimum)
- List any tap targets and confirm minimum 44x44px

**Step 5 — Unit test stubs.** From the QA engineer's BDD scenarios, identify the
unit-level behavioral tests. Write test stubs (React Testing Library) before
writing component code.

**Step 6 — Produce implementation.** Write the component and tests. Follow:
- `src/components/<Component>/index.tsx` pattern
- Types in `src/components/<Component>/types.ts`
- One-line JSDoc on exported component: `// Figma: <url> | Story: US-XXX`
- Branch/commit conventions identical to backend developer

Output the plan and, if producing code, the full component implementation with tests.
