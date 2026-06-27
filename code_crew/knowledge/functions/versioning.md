---
name: SDLC-ReleaseEngineer-Versioning
description: Semantic versioning rules, version bump decision tree, migration guide conventions, and version file locations
metadata:
  type: process
  role: release-engineer
  phase: "20"
---

# Versioning

## Semantic Versioning (semver)

All services follow `MAJOR.MINOR.PATCH`:

```
0.5.2
│ │ └── PATCH: bug fix, security patch, no new functionality
│ └──── MINOR: new feature, backward compatible
└────── MAJOR: breaking change (removed field, incompatible migration, changed contract)
```

### When versions are still `0.x`

`0.x` means the API is not yet stable — breaking changes may occur in MINOR bumps.
Once the API is declared stable, the next release is `1.0.0`.

---

## Version Bump Decision Tree

```
Does this release remove or rename any public API field, endpoint, or query parameter?
  YES → MAJOR bump (or MINOR if still 0.x)

Does this release add a new endpoint, new optional field, or new feature?
  YES → MINOR bump

Is this release only bug fixes, security patches, or internal refactoring?
  YES → PATCH bump
```

When a sprint contains stories of mixed bump types, take the highest:

- MINOR + PATCH stories in one sprint → MINOR release

---

## Version File Locations

| Service | Version file | Format |
|---------|-------------|--------|
| Go services | `portal/backend/go.mod` | `v0.N.N` module path (for breaking changes only) |
| Portal frontend | `portal/frontend/package.json` | `"version": "0.N.N"` |
| API contract | ADD document version field | Updated with every API change |

Go modules: only update the module path for MAJOR (`v2`, `v3`, ...). For MINOR/PATCH, the
module path stays the same — only the GitHub tag changes.

---

## Git Tagging

Every production release gets a signed git tag:

```bash
git tag -s v0.5.0 -m "Release 0.5.0 — mandatory data dictionary upload"
git push origin v0.5.0
```

Tag message format: `Release <version> — <one-line summary of the release>`

Hotfix tags follow the same convention: `v0.5.1 — hotfix: data dictionary bypass`

---

## Migration Guides

Required for any MAJOR bump (or 0.x MINOR bump that breaks a public contract):

```markdown
## Migration Guide: 0.N → 0.N+1

### Breaking Changes

**API**: `POST /datasets/register` — the `data_dictionary` field is now required.
Previously optional. Clients that omit this field will receive `422 Unprocessable Entity`.

**Database**: Migration `000042_make_data_dictionary_mandatory.sql` adds a `NOT NULL`
constraint on `datasets.data_dictionary_url`. Apply before deploying the new image.

### Migration Steps

1. Apply database migration: `migrate -path ./migrations -database $DATABASE_URL up`
2. Update all API clients to include `data_dictionary` in `POST /datasets/register`
3. Deploy new image
```

Migration guides live in `docs/migrations/v0.N-to-v0.N+1.md` and are linked from the
GitHub Release and CHANGELOG entry.
