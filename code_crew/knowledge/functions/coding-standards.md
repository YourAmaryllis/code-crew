---
name: SDLC-Engineer-CodingStandards
description: Language-specific coding conventions for Go, TypeScript/React, and Python used across the platform
metadata:
  type: process
  role: engineer
  phase: "17, 18"
---

# Coding Standards

All code must follow these conventions. Code review rejects PRs that don't comply.

---

## General Principles

- **No hardcoding** — config, secrets, model IDs, prompts, ARNs come from environment or external files
- **Explicit error handling** — no silent error swallowing
- **Interface-driven design** — depend on interfaces/abstractions, not concrete types
- **Immutable by default** — prefer immutable data; mutation requires justification
- **No global state** in library code
- **Comments**: only when the WHY is non-obvious — no what-the-code-does comments

---

## Go

### Structure
- `cmd/` — entry points (one per binary)
- `internal/` — domain, usecase, repo, handler packages
- `pkg/` — shared public packages with stable APIs

### Error Handling
```go
// Wrap with context
if err != nil {
    return fmt.Errorf("fetching user %s: %w", id, err)
}

// Sentinel errors for callers to check
var ErrNotFound = errors.New("not found")
```

### Context
- Pass `context.Context` as the first argument to every I/O function
- Honour `ctx.Done()` in long-running operations

### Interfaces
```go
// Define interface where it is consumed, not where it is implemented
type UserRepository interface {
    GetByID(ctx context.Context, id string) (*User, error)
}
```

### Testing
- Table-driven tests using `t.Run()`
- Use `require` from `testify` for fatal assertions, `assert` for non-fatal
- Mock external dependencies via interfaces (never mock the DB in integration tests)
- Test file naming: `<file>_test.go` in the same package

### Formatting
- `gofmt` + `goimports` — enforced by pre-commit
- Max line length: 120 characters (soft limit)
- No init() functions in library code

---

## TypeScript / React

### Component Rules
- Functional components only — no class components
- Named exports — no default exports for components
- Props interface typed explicitly (no `any`)

```typescript
interface UserCardProps {
  userId: string;
  onSelect: (id: string) => void;
}

export function UserCard({ userId, onSelect }: UserCardProps) { ... }
```

### State Management
- **React Query** for all server state (fetching, caching, mutations)
- **Zustand** for local UI state (modals, selections, ephemeral state)
- No Redux — if you think you need it, use Zustand + React Query instead

### UI Components
- **Ant Design v6** — use Ant Design components; do not create custom component library
- Align all UI to Figma designs; deviation requires design sign-off
- Use Ant Design design tokens for spacing, colors, typography
- No inline styles; CSS Modules for custom styles when unavoidable

### Error Boundaries
- Wrap every page-level component in an error boundary
- Display user-friendly error message; log the technical error

### Testing
- **Jest** + **React Testing Library** for unit/component tests
- **Playwright** for E2E tests
- No snapshot tests (brittle and not meaningful)
- Test behaviour, not implementation

---

## Python

Used for AI tooling, scripts, data processing.

### Type Hints
```python
def fetch_ticket(key: str) -> JiraTicket:
    ...
```
- Type hints on all public functions
- Use `from __future__ import annotations` for forward references

### Data Validation
- **Pydantic** for all data at system boundaries (API inputs, config, LLM outputs)
- Never trust external data without validation

### Logging
```python
import logging
logger = logging.getLogger(__name__)

# Use logger, not print()
logger.info("Fetching ticket %s", key)
```

### Error Handling
- Use domain-specific exceptions, not bare `Exception`
- Let errors propagate unless you can meaningfully handle them

### Formatting
- **Black** + **isort** — enforced by pre-commit
- Line length: 100 characters

---

## SQL

- Parameterized queries only — never string concatenation
- Migrations tracked in `infra/migrations/` using a versioned migration tool
- Schema changes require migration script + rollback script
- No stored procedures unless explicitly justified by performance

---

## Terraform / Infrastructure as Code

- Modules live in `infra/modules/<name>/`
- Variables documented with `description` and `type`
- Outputs documented with `description`
- No hardcoded region, account ID, or resource ARN — use variables and data sources
- Resource names include environment prefix: `${var.env}-<service>-<resource>`
- Tags on all resources: `env`, `service`, `managed-by = terraform`
