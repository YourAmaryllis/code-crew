---
type: Stack Guide
title: Go Backend
description: Conventions, module layout, and patterns for Go backend services
tags: [go, backend]
---

## Module layout

Each service has its own `go.mod` — do not mix modules. Module root is the service directory.

BDD test harness (`integration/`) is a separate module and is not part of the application build.

## Typical internal layout

```
<service>/
  cmd/<entry-point>/main.go   — entry point: wire dependencies, register routes
  internal/
    api/                      — HTTP handlers only (parse → call service → respond)
    <domain>/                 — Service / domain layer (business logic lives here)
    migrate/                  — Migration runner
    models/                   — Shared types and DTOs
    middleware/               — Auth, CORS, logging
  migrations/                 — SQL migration files (sequential numbered)
  go.mod / go.sum
```

## Key dependency categories

- **HTTP router**: `github.com/gorilla/mux`, `net/http` ServeMux, `github.com/go-chi/chi`, etc.
- **DB**: `github.com/jackc/pgx/v5` via `database/sql`, or `database/sql` with another driver
- **Migrations**: `github.com/golang-migrate/migrate/v4` or `github.com/pressly/goose/v3`
- **Auth**: OIDC library (e.g. `github.com/coreos/go-oidc/v3`)
- **AWS SDK v2**: used for S3, Secrets Manager, and other AWS services

## Layering rules

- **HTTP handlers** (`internal/api/` or similar) — parse input, call a service function, write response. No business logic.
- **Service / domain layer** — all business logic. Returns typed results or errors.
- **No cross-layer imports in the wrong direction** — handlers call services; services do not import handlers.

## Coding conventions

- Idiomatic Go: short variable names in short scopes, named returns only when they clarify
- Error handling at system boundaries only: validate user input and external API responses; trust internal calls
- No `fmt.Println` in production — use structured logging
- All config via env vars; no hardcoded URLs, ports, credentials, or timeouts
- `go vet ./...` and `gofmt` enforced by pre-commit hook

## Testing

- Unit tests: `*_test.go` files alongside production code
- Run: `go test ./... -count=1` from the module root
- Build check: `go build ./...` must pass before committing
- BDD: lives in `integration/` module (separate `go.mod`); see `bdd-testing` stack

## New file conventions

When creating a new feature area:

```
internal/api/<feature>.go         — handler
internal/api/<feature>_test.go   — handler unit test
internal/<domain>/<feature>.go    — service logic
internal/<domain>/<feature>_test.go  — service unit test
```

## Commit and branch format

- Branch: `feature/<issue-key>-<slug>` (trunk-based, max one business day)
- Commit: `<type>(<scope>): <description> [REQ:<REQ-ID>] <issue-key>`
- Rebase from `main` before every push: `git fetch origin && git rebase origin/main`
- No merge commits on feature branches

## API spec — swaggo/swag

Install once: `go install github.com/swaggo/swag/cmd/swag@latest`

Annotate handlers with swaggo comments:

```go
// @Summary      Get user by ID
// @Tags         users
// @Produce      json
// @Param        id   path      string  true  "User UUID"
// @Success      200  {object}  models.User
// @Failure      404  {object}  models.ErrorResponse
// @Router       /v1/users/{id} [get]
func (h *UserHandler) GetByID(w http.ResponseWriter, r *http.Request) {
```

Generate / update spec:

```bash
swag init -g cmd/<entry-point>/main.go -o docs/
```

This writes `docs/swagger.json`, `docs/swagger.yaml`, `docs/docs.go`.

**Rules:**
- Run `swag init` after every handler change that adds, removes, or alters a route
- Commit `docs/swagger.json` and `docs/swagger.yaml` alongside the handler change
- CI check: `swag init ... && git diff --exit-code docs/` — fails on drift
- Do not edit `docs/swagger.json` by hand — it is fully generated

## DB schema — goose

Install: `go install github.com/pressly/goose/v3/cmd/goose@latest`

**Create a new migration:**

```bash
goose -dir migrations create <description> sql
```

This writes `migrations/YYYYMMDDHHMMSS_<description>.sql` with `-- +goose Up` and `-- +goose Down` sections.

Fill in the SQL:

```sql
-- +goose Up
CREATE TABLE <table> (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- +goose Down
DROP TABLE <table>;
```

**Apply** (CI / human only — never run from crew):

```bash
goose -dir migrations postgres "$DATABASE_URL" up
```

**Verify status:**

```bash
goose -dir migrations postgres "$DATABASE_URL" status
```

**Rules:**
- Always fill both `-- +goose Up` and `-- +goose Down` sections
- Never edit a migration that has been applied in any environment
- Use `TIMESTAMPTZ` not `TIMESTAMP`; use `UUID` not `SERIAL` for primary keys
- Commit migration file alongside handler + model changes in the same PR
