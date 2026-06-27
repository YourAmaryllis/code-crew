---
type: Stack Guide
title: Go Backend
description: Conventions, module layout, and patterns for Go services in this platform
tags: [go, backend, portal, attestation, fhir-proxy]
---

## Module layout

Each service has its own `go.mod` — do not mix modules:

| Module root | Purpose |
|---|---|
| `portal/backend/` | Main portal API (gorilla/mux, pgx/v5, AWS SDK v2) |
| `attestation/` | Attestation + ARD service (Lambda + ECS paths) |
| `fhir_proxy/` | FHIR proxy (gorilla/mux, redis) |
| `portal/cli/` | CLI tooling (cobra) |
| `integration/` | BDD test harness (godog) — separate module, not part of app build |

## Portal backend internal layout

```
portal/backend/
  cmd/server/main.go          — entry point: wire DB, AWS, OIDC, routes
  internal/
    api/                      — HTTP handlers only (parse → call service → respond)
    ard/                      — Domain / service layer (business logic lives here)
    migrate/                  — Migration runner
    models/                   — Shared types and DTOs
    middleware/               — Auth, CORS, logging
  migrations/                 — SQL migration files (golang-migrate, sequential numbered)
  go.mod / go.sum
```

## Key dependencies

- **HTTP:** `github.com/gorilla/mux`
- **DB:** `github.com/jackc/pgx/v5` via `database/sql`
- **Migrations:** `github.com/golang-migrate/migrate/v4`
- **Auth:** `github.com/coreos/go-oidc/v3` + `golang.org/x/oauth2` (Auth0/OIDC)
- **AWS SDK v2:** s3, secretsmanager, ecr, iam, sts, eventbridge, acmpca, bedrockruntime

## Layering rules

- **HTTP handlers** (`internal/api/`) — parse input, call a service function, write response. No business logic.
- **Service / domain layer** (`internal/ard/`) — all business logic. Returns typed results or errors.
- **No cross-layer imports in the wrong direction** — api → ard is OK; ard → api is not.

## Coding conventions

- **Go 1.24** target for portal/backend, attestation; fhir_proxy is on 1.23
- Idiomatic Go: short variable names in short scopes, named returns only when they clarify
- Error handling at system boundaries only: validate user input and external API responses; trust internal calls
- No `fmt.Println` in production — use structured logging
- All config via env vars; no hardcoded URLs, ports, credentials, or timeouts
- `go vet ./...` and `gofmt` enforced by pre-commit hook

## Testing

- Unit tests: `*_test.go` files alongside production code
- Run: `go test ./... -count=1` from the module root
- Build check: `go build ./...` must pass before committing
- BDD: lives in `integration/` module (separate `go.mod`); see `bdd-authoring` guide

## New file conventions

When creating a new feature area (e.g. `data_dictionary_mandatory`):

```
internal/api/register_validation_<feature>.go        — handler
internal/api/register_validation_<feature>_test.go   — handler unit test
internal/ard/<feature>.go                             — service logic
internal/ard/<feature>_test.go                        — service unit test
```

## Commit and branch format

- Branch: `feature/<JIRA-KEY>-<slug>` (trunk-based, max one business day)
- Commit: `<type>(<scope>): <description> [REQ:<REQ-ID>] <JIRA-KEY>`
  - Example: `feat(portal): data dictionary mandatory validation [REQ:DATA-05] PROJ-NNN`
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
swag init -g cmd/server/main.go -o docs/
```

This writes `docs/swagger.json`, `docs/swagger.yaml`, `docs/docs.go`.

**Rules:**
- Run `swag init` after every handler change that adds, removes, or alters a route
- Commit `docs/swagger.json` and `docs/swagger.yaml` alongside the handler change
- CI check: `swag init ... && git diff --exit-code docs/` — fails on drift
- Serve Swagger UI in dev: `github.com/swaggo/http-swagger` middleware on `GET /swagger/*`
- Do not edit `docs/swagger.json` by hand — it is fully generated

## DB schema — goose

Install: `go install github.com/pressly/goose/v3/cmd/goose@latest`

**Create a new migration:**

```bash
goose -dir migrations create add_user_preferences_table sql
```

This writes `migrations/YYYYMMDDHHMMSS_add_user_preferences_table.sql` with `-- +goose Up` and `-- +goose Down` sections.

Fill in the SQL:

```sql
-- +goose Up
CREATE TABLE user_preferences (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_user_preferences_user_id ON user_preferences(user_id);

-- +goose Down
DROP TABLE user_preferences;
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
- Note: this project also uses `golang-migrate` in older services — check which runner is wired in `cmd/server/main.go` before picking a tool
