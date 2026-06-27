---
type: Architecture Guide
title: Clean Architecture
description: Layer rules, dependency direction, and implementation conventions for Clean Architecture
tags: [architecture, clean, hexagonal-variant]
activate: explicitly — set architecture.style: clean in config or ARCHITECTURE_STYLE=clean
---

## Core principle

Dependencies point inward only. Inner layers know nothing about outer layers.

```
[ Frameworks / Drivers ]          ← outer: web, DB, CLI, external APIs
       ↓ depends on
[ Interface Adapters ]            ← controllers, presenters, gateways
       ↓ depends on
[ Application / Use Cases ]       ← business rules, orchestration
       ↓ depends on
[ Entities / Domain ]             ← core models, domain logic, no imports from outer rings
```

## Directory conventions

```
<service>/
  domain/           — entities, value objects, domain errors; zero external imports
  usecases/         — use case interfaces + implementations; imports domain only
  adapters/         — controllers, presenters, repo implementations; imports usecases
  infrastructure/   — DB clients, HTTP clients, config, DI wiring; imports adapters
  cmd/              — entrypoints (main, lambda handler); wires infrastructure
```

Acceptable variation per language:

| Language | Domain | Use cases | Adapters | Infra |
|----------|--------|-----------|----------|-------|
| Go | `internal/domain/` | `internal/app/` | `internal/adapters/` | `internal/infra/` |
| Python | `domain/` | `application/` | `adapters/` | `infrastructure/` |
| TypeScript | `src/domain/` | `src/usecases/` | `src/adapters/` | `src/infra/` |

## Dependency rule (enforced)

- `domain/` **must not** import from `usecases/`, `adapters/`, or `infrastructure/`
- `usecases/` **must not** import from `adapters/` or `infrastructure/`
- `adapters/` **must not** import from `infrastructure/`
- Interfaces defined in inner layers, implementations in outer layers

## What goes where

| Thing | Layer |
|-------|-------|
| User, Order, Invoice model | domain |
| CreateOrder, CancelOrder logic | usecases |
| HTTP handler, gRPC handler | adapters |
| SQL repo implementation | adapters |
| DB connection pool | infrastructure |
| AWS SDK client | infrastructure |
| `main()` / DI wiring | cmd / infrastructure |

## Rules for implementation tasks

1. New feature → start from domain entity or use case interface, work outward
2. Never put `http`, `sql`, `aws`, or framework imports inside `domain/` or `usecases/`
3. Use case methods accept and return domain types, not HTTP request/response structs
4. Repository interfaces defined in `usecases/`; SQL implementations in `adapters/`
5. DI wiring happens in `infrastructure/` or `cmd/`; use cases receive repos via constructor injection

## Code review checklist

- [ ] No framework imports in `domain/` or `usecases/`
- [ ] Use case takes interface, not concrete implementation
- [ ] Repository interface lives in `usecases/`, not `adapters/`
- [ ] Domain entities have no awareness of HTTP status codes or DB column names
- [ ] No circular imports across layers
