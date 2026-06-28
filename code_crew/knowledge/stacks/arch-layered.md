---
type: Architecture Guide
title: Layered (Three-Tier) Architecture
description: Layer rules, dependency direction, and implementation conventions for classic layered / three-tier architecture
tags: [architecture, layered, three-tier]
activate: explicitly — set architecture.style: layered in config or ARCHITECTURE_STYLE=layered
---

## Core principle

Responsibilities are separated into horizontal layers. Each layer may only depend on the layer directly below it. No upward dependencies.

```
[ Presentation / API / Handlers ]     ← HTTP handlers, gRPC, CLI entry points
       ↓ depends on
[ Service / Business Logic ]          ← domain rules, orchestration, workflows
       ↓ depends on
[ Repository / Storage / Data ]       ← DB queries, external API calls, caching
```

## Directory conventions

```
<service>/
  handlers/ (or api/ or controllers/)  — HTTP/gRPC handlers; parse requests, call services
  services/ (or service/)              — business logic; no DB or HTTP concerns
  repository/ (or storage/ or repo/)   — DB queries, ORM models, external data access
  models/ (or types/ or domain/)       — shared data structures (not logic)
  middleware/                          — cross-cutting: auth, logging, rate-limit
  cmd/ (or main.go / main.py)          — entrypoint; wires everything together
```

Acceptable variation per language:

| Language | Handlers | Services | Repositories |
|----------|----------|----------|--------------|
| Go | `internal/handlers/` or `internal/api/` | `internal/services/` | `internal/repository/` or `internal/storage/` |
| Python | `api/` or `routes/` | `services/` | `repositories/` or `db/` |
| TypeScript | `controllers/` or `routes/` | `services/` | `repositories/` or `models/` |

## Dependency rule (enforced)

- `handlers/` **must not** contain business logic — only request parsing and response formatting
- `services/` **must not** import from `handlers/` or make direct HTTP calls
- `repository/` **must not** contain business rules — only data access
- `models/` (shared structs) may be imported by any layer
- `middleware/` may be imported only by `handlers/` and entrypoints

## What goes where

| Thing | Layer |
|-------|-------|
| Parse JSON body, validate content-type | handlers |
| Return HTTP 200/400/500 | handlers |
| Apply business rules (e.g. eligibility check) | services |
| Orchestrate multiple repo calls | services |
| SELECT / INSERT / UPDATE queries | repository |
| Redis get/set | repository |
| Shared data structs (User, Order) | models |
| Auth token validation middleware | middleware |
| DB connection pool setup | cmd / entrypoint |

## Rules for implementation tasks

1. Handlers call services; services call repositories — never skip a layer
2. Never put SQL or HTTP client calls directly in a handler or service (use repository)
3. Service methods accept and return domain structs from `models/`, not raw DB rows or HTTP types
4. Error translation (DB error → HTTP 404) happens at the handler layer, not in services
5. Repository interfaces defined in `services/`; implementations in `repository/`

## Code review checklist

- [ ] No SQL or external HTTP calls in `handlers/` or `services/`
- [ ] No HTTP status codes or request parsing in `services/` or `repository/`
- [ ] Service takes repository interface, not concrete implementation
- [ ] Business rules live in `services/`, not in handlers
- [ ] No circular imports across layers
