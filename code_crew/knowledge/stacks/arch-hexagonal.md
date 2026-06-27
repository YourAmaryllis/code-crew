---
type: Architecture Guide
title: Hexagonal Architecture (Ports & Adapters)
description: Port/adapter conventions, domain isolation, and driving/driven adapter rules
tags: [architecture, hexagonal, ports-and-adapters]
activate: explicitly — set architecture.style: hexagonal in config or ARCHITECTURE_STYLE=hexagonal
---

## Core principle

The domain (application hexagon) communicates with the outside world only through named ports. Adapters implement ports. The domain never knows what adapter is plugged in.

```
                  ┌──────────────────────┐
  [REST API]  ──▶ │   Driving Adapter    │
  [CLI]       ──▶ │  (primary/left side) │
                  │         ↓            │
                  │    Driving Port      │
                  │   (interface in app) │
                  │         ↓            │
                  │      Domain          │  ← no external imports
                  │         ↓            │
                  │    Driven Port       │
                  │  (interface in app)  │
                  │         ↓            │
                  │   Driven Adapter     │
                  │  (secondary/right)   │
                  └──────────────────────┘
                       ↑           ↑
              [PostgreSQL]     [S3 / SQS]
```

## Directory conventions

```
<service>/
  domain/           — pure domain model; no I/O, no framework imports
  ports/
    driving/        — interfaces the domain exposes to callers (use case interfaces)
    driven/         — interfaces the domain calls out through (repo, mailer, queue)
  adapters/
    driving/        — HTTP handlers, gRPC, CLI, event consumers
    driven/         — DB repos, S3 clients, SQS publishers, email senders
  app/              — wires ports to adapters; orchestration / application services
  cmd/              — entrypoints
```

## Driving vs driven

| Direction | Also called | Examples |
|-----------|-------------|---------|
| Driving (primary) | left-side, inbound | REST controller, GraphQL resolver, CLI command, test harness |
| Driven (secondary) | right-side, outbound | SQL repository, message queue publisher, email adapter, external API client |

## Dependency rule

- `domain/` has no outward imports — it only uses types it owns
- `ports/` imports `domain/` only
- `adapters/driving/` imports `ports/driving/` and `domain/`
- `adapters/driven/` imports `ports/driven/` and `domain/`
- `app/` imports everything and wires it together

## Rules for implementation tasks

1. Every new external integration (DB table, queue, third-party API) requires a driven port interface first
2. Every new entry point (route, CLI flag, event) requires a driving port (use case interface) first
3. Domain types cross port boundaries freely; HTTP/DB types must not cross into `domain/` or `ports/`
4. Swap test: if you can replace the driven adapter with an in-memory fake by only changing `app/`, the boundary is correct
5. Constructor injection only — no service locators or global adapters

## Code review checklist

- [ ] New integration has a `ports/driven/` interface before the adapter
- [ ] New entry point calls through a `ports/driving/` interface, not directly into domain
- [ ] No SQL/HTTP/AWS types visible in `domain/` or `ports/`
- [ ] `app/` is the only place where adapters and ports are wired together
- [ ] In-memory fake adapter exists or is planned for driven ports used in tests
