---
type: Architecture Guide
title: Onion Architecture
description: Concentric ring rules, domain model core, service layers, and infrastructure outer ring
tags: [architecture, onion, domain-driven]
activate: explicitly — set architecture.style: onion in config or ARCHITECTURE_STYLE=onion
---

## Core principle

The domain model is the bull's-eye. Rings grow outward. Each ring depends only on rings closer to the centre. The outer infrastructure ring is replaceable.

```
┌──────────────────────────────────────────┐
│           Infrastructure                 │  ← DB, HTTP, queues, filesys
│  ┌────────────────────────────────────┐  │
│  │       Application Services         │  │  ← orchestration, use cases, workflows
│  │  ┌──────────────────────────────┐  │  │
│  │  │      Domain Services         │  │  │  ← domain logic that spans entities
│  │  │  ┌────────────────────────┐  │  │  │
│  │  │  │     Domain Model       │  │  │  │  ← entities, value objects, aggregates
│  │  │  └────────────────────────┘  │  │  │
│  │  └──────────────────────────────┘  │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

## Directory conventions

```
<service>/
  domain/
    model/          — entities, value objects, aggregates, domain errors
    services/       — domain services (logic spanning multiple aggregates)
    repositories/   — repository interfaces (defined here, implemented in infra)
  application/
    services/       — application services / use cases (orchestrate domain + repos)
    dtos/           — input/output DTOs for application services
  infrastructure/
    persistence/    — repository implementations (SQL, NoSQL, in-memory)
    http/           — controllers, middleware, route wiring
    messaging/      — queue consumers and publishers
    config/         — env, secrets loading
  cmd/              — entrypoints, DI wiring
```

## Ring rules

| Ring | Imports allowed | Imports forbidden |
|------|----------------|------------------|
| Domain Model | nothing | everything |
| Domain Services | Domain Model | Application, Infrastructure |
| Application Services | Domain (model + services + repo interfaces) | Infrastructure |
| Infrastructure | Everything | (outermost — no restriction except no circular deps) |

## Repository pattern

Repository interfaces live in `domain/repositories/`. Infrastructure implementations in `infrastructure/persistence/`. Application services receive repository interfaces via constructor injection.

```python
# domain/repositories/user_repo.py
class UserRepository(Protocol):
    def find_by_id(self, user_id: UserId) -> User | None: ...
    def save(self, user: User) -> None: ...

# infrastructure/persistence/pg_user_repo.py
class PgUserRepository:
    def find_by_id(self, user_id: UserId) -> User | None:
        ...  # SQL here
```

## Rules for implementation tasks

1. New aggregate → domain model first; no constructor args from infra types
2. Logic that spans two aggregates → domain service, not application service
3. Application service coordinates the flow: load aggregate → call domain method → persist → publish event
4. Infrastructure layer may depend on application DTOs for serialisation, not on domain internals
5. Never put validation logic in infrastructure; it belongs in domain model or domain services

## Code review checklist

- [ ] New entity has no import from `application/` or `infrastructure/`
- [ ] Repository interface is in `domain/repositories/`, implementation in `infrastructure/persistence/`
- [ ] Application service does not reach into aggregate internals — calls domain methods
- [ ] Domain service has no I/O (no DB calls, no HTTP)
- [ ] DTOs used at application boundary, not domain types leaked to HTTP layer
- [ ] All infra implementations injected, not instantiated inside application services
