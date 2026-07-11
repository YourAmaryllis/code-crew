---
name: SDLC-Architect-CodeArchitecture
description: Clean architecture standards, layering, patterns, and code structure requirements enforced by the architect
metadata:
  type: process
  role: architect
  phase: "5, 11, 19"
---

# Code Architecture

The architect defines and enforces the code structure across all services. Engineers implement it; architects verify adherence in code review.

---

## Clean Architecture

All services follow a layered clean architecture:

```
┌─────────────────────────────────────┐
│  Delivery / Transport Layer          │  HTTP handlers, CLI, Lambda entry points
├─────────────────────────────────────┤
│  Application Layer                  │  Use cases, orchestration, DTOs
├─────────────────────────────────────┤
│  Domain Layer                       │  Entities, value objects, domain events
├─────────────────────────────────────┤
│  Infrastructure Layer               │  DB adapters, external API clients, queues
└─────────────────────────────────────┘
```

- Dependencies flow **inward only** — infrastructure depends on domain, never the reverse
- Domain layer has **zero external dependencies** (no framework imports)
- Use cases are **pure functions or structs** — no global state, no side effects hidden in constructors

---

## Bounded Contexts

Services map to bounded contexts from the domain model. Each bounded context owns its data; cross-context communication is via events or explicit APIs, never shared database tables.

See: [domain-model.md`](domain-model.md)

---

## Repository Structure (`platform` monorepo)

```
platform/
  portal/               # React SPA (Ant Design v6)
  services/
    <service>/
      cmd/              # Entry points
      internal/
        domain/         # Entities, value objects
        usecase/        # Application logic
        repo/           # Repository interfaces + implementations
        handler/        # HTTP/gRPC/Lambda handlers
      pkg/              # Shared public packages
  infra/                # Terraform modules
  .code-crew/           # AI crew execution context
  designs/              # Git submodule → designs repo
```

---

## Language Standards

### Go (backend services)
- Standard project layout (`cmd/`, `internal/`, `pkg/`)
- Errors as values — no panics except truly unrecoverable
- `context.Context` propagated through all I/O calls
- Interface-driven — depend on interfaces, not concrete types
- Table-driven tests; no global state in tests

### TypeScript / React (portal)
- Ant Design v6 component library — no custom component library
- Functional components + hooks only
- State: React Query for server state, Zustand for local UI state
- No inline styles — use Ant Design tokens or CSS modules

### Python (AI tooling, scripts)
- Type hints on all public functions
- Pydantic for data validation at system boundaries
- No `print()` in library code — use `logging`

---

## Hardcoding Prohibitions

The following must **never** be hardcoded in application code:

| Category | Must come from |
|----------|---------------|
| Configuration values (URLs, timeouts, feature flags) | Environment variables |
| Secrets (API keys, tokens, passwords) | AWS Secrets Manager / SSM |
| Prompts, agent instructions | External `.md` files (OKF format) |
| Model IDs, endpoint names | Environment variables |
| Infrastructure ARNs | Terraform outputs / SSM parameters |

Code review must reject any PR that hardcodes these values. See [coding-standards.md`](coding-standards.md).

---

## Architecture Decision Records (ADRs)

When a significant architectural decision is made:

1. Create an ADR in `designs/ADR/` using OKF format
2. Record: context, decision, consequences, alternatives rejected
3. ADR is immutable once merged — supersede with a new ADR if the decision changes
4. Reference ADR number in commit messages and PRs

ADR format:
```markdown
---
name: ADR-NNN-Title
description: One-line summary of the decision
metadata:
  type: adr
  status: accepted | superseded | deprecated
  superseded-by: ADR-NNN (if applicable)
---

## Context
## Decision
## Consequences
## Alternatives Considered
```

See: [architecture-decisions.md`](architecture-decisions.md)

---

## Architecture Design Documents (ADDs)

For significant features, the architect writes an ADD:

- Describes component design, data flow, API contracts
- Referenced from Jira ticket description or comments
- Stored in `designs/ADD/` as OKF `.md` files
- Code-crew agents read ADD refs from Jira tickets automatically

---

## Solution Architecture Document (SAD)

The SAD is the living architecture overview for the entire platform. It must be updated when:

- A new service is introduced
- A significant integration is added or changed
- An ADR changes an architectural decision reflected in the SAD

See: [sad-maintenance.md`](sad-maintenance.md)

---

## Code Review Enforcement

The architect (or tech lead) enforces these in code review:

- Layer violations (infrastructure importing domain)
- Hardcoded values (config, secrets, prompts)
- Missing interface abstractions on external dependencies
- Business logic in delivery layer (handlers)
- Missing error handling on external calls
- Branch/commit/PR naming convention violations

See: [code-quality.md`](code-quality.md), [github-conventions.md`](github-conventions.md)
