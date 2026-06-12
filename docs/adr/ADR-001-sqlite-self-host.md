# ADR-001: PostgreSQL only (SQLite self-host mode dropped)

**Date:** 2026-05-06 · **Superseded:** 2026-05-30
**Status:** Superseded — PostgreSQL is the only supported database

## Context

The original plan was to support **SQLite** for self-hosted single-tenant
deployments and **PostgreSQL** for the SaaS, selecting the driver via
`DATABASE_URL`. In practice the code came to depend on PostgreSQL-specific
features that have no SQLite equivalent:

- `ARRAY(String)` columns (`app/models/rules.py` — keyword rules)
- `INSERT ... ON CONFLICT DO NOTHING` (`app/repositories/cycle.py`, billing dedup)
- `postgresql.UUID` and server-side defaults across all migrations

Maintaining a portable schema would have meant giving up these features or
writing a second code path — cost not justified for the current stage.

## Decision

- **PostgreSQL is the only supported database** for both self-host and SaaS.
- Self-host gets PostgreSQL out of the box via `docker compose` (the `postgres`
  service), so "one command" still holds — no external dependency for the user.
- The original SQLite mode and the SQLite→Postgres migration scripts are **not
  implemented** and are removed from the docs.

## Consequences

+ One schema, one tested code path; full use of PG features (ARRAY, upserts).
+ Self-host stays one-command (Postgres ships in the compose file).
- No "zero-dependency single-file DB" option. Revisit only if there is real
  community demand for an embedded mode.
