---
type: Process Guide
title: DB Schema Management
description: Migration naming, rollback rules, review checklist, and per-tool conventions
tags: [database, migrations, alembic, goose, atlas, schema]
---

## Guiding principle

Agents generate migration files. Agents do NOT apply migrations to any environment. Applying migrations is a human or CI step — never autonomous.

---

## Migration tool per stack

| Stack | Default tool | Config key |
|-------|-------------|-----------|
| `python` | alembic | `db.migration_tool: alembic` |
| `go-backend` | goose | `db.migration_tool: goose` |
| any / polyglot | atlas | `db.migration_tool: atlas` |

Auto-detected by `/explore` from: `alembic.ini`, `migrations/*.sql` (goose header), `atlas.hcl` / `atlas.sum`.

Override with `DB_MIGRATION_TOOL` env var or `db.migration_tool` in config.

Schema path default: `migrations/`. Override with `DB_SCHEMA_PATH` env var or `db.schema_path` in config.

---

## Naming convention

```
YYYYMMDDHHMMSS_<description_in_snake_case>.sql
```

Examples:
```
20260619143000_add_user_preferences_table.sql
20260620090000_add_index_on_audit_events_created_at.sql
20260621120000_drop_legacy_session_tokens_table.sql
```

Rules:
- Timestamp must be the actual UTC time the migration was generated — never copied from another migration
- Description: lowercase, underscores, max 60 chars, no special characters
- One logical change per migration file (one table creation, one index, one column add)

---

## Ironclad rules

1. **Never edit an applied migration.** Once a migration has been applied in any environment (dev, staging, prod), it is immutable. Fix forward with a new migration.
2. **Every migration must be reversible.** Write the `down` section even if you never expect to use it. Exception: `DROP TABLE` down = restore from backup (document this explicitly).
3. **No raw DDL in application code.** Schema changes live in migration files only.
4. **No data migrations mixed with schema migrations.** If a column rename also needs a data backfill, create two files: one for the schema, one for the data.
5. **Agents generate, humans review, CI applies.** The crew produces the migration file. A human reviews the diff. CI runs `upgrade head` / `goose up` / `atlas migrate apply` in the deployment pipeline.

---

## Schema review checklist

Before committing a migration, verify:

- [ ] Column types match the domain (UUID not VARCHAR for IDs, TIMESTAMPTZ not TIMESTAMP for timestamps)
- [ ] Foreign key constraints have explicit `ON DELETE` and `ON UPDATE` actions
- [ ] Indexes exist on every foreign key column and every column used in `WHERE` / `ORDER BY`
- [ ] Text columns have an appropriate length constraint or are `TEXT` with an app-level validator
- [ ] No `NOT NULL` column added to a non-empty table without a `DEFAULT` or backfill migration
- [ ] `down` section tested (can be rolled back cleanly)
- [ ] No `DROP TABLE` or `DROP COLUMN` without verifying no application code reads from it
- [ ] Migration file name follows `YYYYMMDDHHMMSS_description` convention

---

## Per-tool conventions

### alembic (Python)

See `stacks/python.md` → "DB schema — alembic" section.

### goose (Go)

See `stacks/go-backend.md` → "DB schema — goose" section.

### atlas (cross-stack)

See `stacks/` → any stack that declares `db.migration_tool: atlas`.

Generate from current schema state:
```bash
atlas migrate diff <migration_name> \
  --dir "file://migrations" \
  --to "postgres://$DB_URL" \
  --dev-url "docker://postgres/15"
```

Apply (CI / human only):
```bash
atlas migrate apply --dir "file://migrations" --url "postgres://$DB_URL"
```

Validate:
```bash
atlas migrate validate --dir "file://migrations"
```
