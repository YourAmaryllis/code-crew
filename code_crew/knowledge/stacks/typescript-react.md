---
type: Stack Guide
title: TypeScript / React Frontend
description: Conventions, layout, and patterns for the portal frontend
tags: [typescript, react, antd, vite, portal]
---

## Module layout

```
portal/frontend/
  src/
    components/<Component>/
      index.tsx               — exported component
      types.ts                — prop types and interfaces
      <Component>.test.tsx    — unit tests (React Testing Library)
    hooks/                    — custom React hooks
    pages/                    — route-level page components
    services/                 — API client functions
    utils/                    — pure utilities
  public/
  package.json / package-lock.json
  tsconfig.json
  vite.config.ts
```

## Framework and library versions

- **React 18** with functional components and hooks only (no class components)
- **TypeScript 5.x** — strict mode; no `any` without justification
- **Ant Design v6 (`antd ^6`)** — primary component library
- **`@ant-design/icons`** — icon set
- **`@auth0/auth0-react`** — authentication
- **Vite 5** — build tool; `VITE_*` env vars for build-time config
- **React Router** (`react-router-dom`) — routing

## Component conventions

Every new component must handle four data-fetching states:
- **Loading** — skeleton or spinner (use Ant Design `Skeleton` or `Spin`)
- **Error** — error message with retry affordance (`Alert` + retry button)
- **Empty** — empty state with guidance (`Empty` from antd)
- **Loaded** — primary state with real data

Every exported component has a one-line JSDoc linking Figma and the story:
```tsx
// Figma: https://figma.com/... | Story: PROJ-NNNNNN
export const MyComponent: React.FC<Props> = ({ ... }) => { ... }
```

## Ant Design v6 patterns

- Use `Form`, `Table`, `Select`, `Input`, `Button`, `Modal`, `Drawer` from `antd` before writing custom elements
- Use design tokens (`theme.useToken()`) for colors — no hardcoded hex values
- Use `Space`, `Row`, `Col` for layout — avoid raw CSS flexbox when Ant Design layout components suffice
- CSS modules (`.module.css`) only for layout overrides that Ant Design tokens can't handle

## Accessibility (WCAG 2.1 AA — mandatory)

- Semantic HTML: `<button>` not `<div onClick>`, `<nav>`, `<main>`, `<header>` landmarks
- ARIA labels on all interactive elements that lack visible text
- Keyboard navigation: every interactive element reachable and operable via Tab/Enter/Space
- Minimum tap target: 44×44 px for all touch targets
- Color contrast: text on background ≥ 4.5:1 (normal), ≥ 3:1 (large text)

## Testing

- **React Testing Library** — test behaviour, not implementation details
- Test file: `<Component>.test.tsx` alongside the component
- Run: `npm test` or `npx vitest run`
- TypeScript check: `npx tsc --noEmit`
- ESLint: `npx eslint src/`

## Commit and branch format

Same as backend:
- Branch: `feature/<JIRA-KEY>-<slug>`
- Commit: `<type>(portal): <description> [REQ:<REQ-ID>] <JIRA-KEY>`
  - Example: `feat(portal): data dictionary mandatory UI validation [REQ:UI-05] PROJ-NNN`

## API spec — openapi-typescript client generation

Generate a typed TypeScript client from the backend's OpenAPI spec:

```bash
npx openapi-typescript docs/openapi.json -o src/api/schema.d.ts
```

Or from a live server:

```bash
npx openapi-typescript http://localhost:8080/openapi.json -o src/api/schema.d.ts
```

Use the generated types with `openapi-fetch`:

```typescript
import createClient from "openapi-fetch";
import type { paths } from "@/api/schema";

const api = createClient<paths>({ baseUrl: process.env.VITE_API_URL });

const { data, error } = await api.GET("/v1/users/{id}", {
  params: { path: { id: userId } },
});
```

**Rules:**
- `src/api/schema.d.ts` is generated — never edit by hand
- Regenerate after every backend spec change: `npm run gen:api`
- Add to `package.json`: `"gen:api": "openapi-typescript ../docs/openapi.json -o src/api/schema.d.ts"`
- All API calls must use the typed client — no raw `fetch()` to backend routes
- Type errors from the generated schema are real API contract violations; fix the backend or the spec, not the TypeScript
