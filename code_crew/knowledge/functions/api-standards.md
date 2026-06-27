---
type: Process Guide
title: API Standards — OpenAPI 3.1
description: Conventions for designing, generating, and maintaining OpenAPI specs across all stacks
tags: [api, openapi, swagger, rest, versioning]
---

## Guiding principle

The OpenAPI spec is the contract. Code must match the spec; the spec is committed alongside code changes. Spec drift is a build failure.

---

## Spec location and format

| Stack | Spec file | Format |
|-------|-----------|--------|
| Go (swaggo) | `docs/swagger.json` + `docs/swagger.yaml` | auto-generated; do not edit by hand |
| Python (FastAPI) | `docs/openapi.json` | auto-exported; do not edit by hand |
| Standalone / shared | `openapi.yaml` at repo root or `docs/openapi.yaml` | hand-authored or auto-generated |

Always commit the generated spec file. CI must fail if the committed spec differs from a freshly generated one (`git diff --exit-code docs/swagger.json`).

---

## URL structure

```
/v{N}/{resource-plural}/{id}
/v{N}/{resource-plural}/{id}/{sub-resource}
```

Rules:
- **Version prefix**: always `/v1/`, `/v2/`, etc. — never omit
- **Resource names**: lowercase, hyphenated plural nouns (`/audit-events`, `/user-profiles`)
- **IDs**: path param `{id}` — UUID preferred; never expose sequential integers publicly
- **Actions that aren't CRUD**: use a noun, not a verb (`POST /v1/invoices/{id}/cancellation` not `/cancel`)
- **No trailing slash**
- **Query params**: `snake_case`; booleans as `true`/`false`; arrays as repeated params (`?tag=a&tag=b`)

---

## Standard error schema

All error responses use this envelope:

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Human-readable description",
    "details": [
      { "field": "email", "issue": "must be a valid email address" }
    ],
    "request_id": "req_01J..."
  }
}
```

| HTTP status | When to use |
|-------------|-------------|
| 400 | Validation failure, malformed request |
| 401 | Missing or invalid auth token |
| 403 | Authenticated but not authorised |
| 404 | Resource not found |
| 409 | Conflict (duplicate, state machine violation) |
| 422 | Semantically invalid input (passes schema, fails business rule) |
| 429 | Rate limited |
| 500 | Unexpected server error — never leak stack traces |

Error `code` values must be UPPER_SNAKE_CASE constants documented in the spec.

---

## Pagination

All list endpoints paginate. Default page size: 20. Maximum: 100.

```
GET /v1/users?page=2&per_page=50
```

Response envelope:

```json
{
  "data": [...],
  "pagination": {
    "page": 2,
    "per_page": 50,
    "total": 312,
    "total_pages": 7
  }
}
```

Cursor-based pagination for high-volume or real-time feeds:

```json
{
  "data": [...],
  "cursor": {
    "next": "eyJpZCI6MTIzfQ==",
    "has_more": true
  }
}
```

Use cursor when: total count is unavailable, dataset changes frequently, or `total > 10 000`.

---

## Auth headers

| Scheme | Header | Format |
|--------|--------|--------|
| Bearer token (OIDC/JWT) | `Authorization` | `Bearer <token>` |
| API key (service-to-service) | `X-API-Key` | raw key value |
| HMAC request signing | `X-Signature` + `X-Timestamp` | `sha256=<hex>` + Unix epoch |

Document the security scheme in the spec:

```yaml
components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
security:
  - BearerAuth: []
```

Unauthenticated endpoints must be explicitly listed with `security: []`.

---

## OpenAPI 3.1 structure checklist

Every spec must have:

- [ ] `openapi: "3.1.0"`
- [ ] `info.title`, `info.version` (semver), `info.contact.email`
- [ ] `servers[]` with at least `dev` and `prod` URLs
- [ ] All paths documented with at least one `2xx` and one `4xx` response
- [ ] All request body schemas use `$ref` to named components — no inline schemas on paths
- [ ] All response schemas use `$ref`
- [ ] Every `$ref`-ed schema has `description`
- [ ] Required fields marked with `required: [...]`
- [ ] No `additionalProperties: true` on request bodies (prefer explicit schemas)
- [ ] `operationId` on every operation (used by client generators)

---

## Versioning policy

- **Breaking changes** (removed fields, changed types, renamed paths) → new major version (`/v2/`)
- **Additive changes** (new optional fields, new endpoints) → no version bump; spec patch release
- Maintain previous major version for ≥ 6 months after `/vN+1/` GA
- Deprecation: add `deprecated: true` to the operation + `Sunset` response header

---

## Stack-specific generation

See the `api-spec` section in each stack guide:
- **Go:** `stacks/go-backend.md` → swaggo/swag
- **Python:** `stacks/python.md` → FastAPI auto-generation
- **TypeScript client:** `stacks/typescript-react.md` → openapi-typescript
