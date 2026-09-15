# M2-P5A correction RED observations

The corrected five-identity oracle collected under Python 3.13.15 against PostgreSQL 18.6 with `CREATEDB=true`; its disposable-database setup, imports, UoW ownership, DSN, and teardown all succeeded.

| Identity | Observed defect | Classification |
|---|---|---|
| P5A-001 | Persisted current revision was 2 but `RevisionConflictError.current_revision` was 1. | `VALID_BEHAVIORAL_RED` |
| P5A-002 | Metadata-only secret-handle path passed. | unaffected |
| P5A-003 | Redacted event-factory path passed. | unaffected |
| P5A-004 | `0004` added `cp_schema_migrations_prune_future` and `cp_prune_future_schema_migrations` to the shared ledger. | `VALID_BEHAVIORAL_RED` |
| P5A-005 | Importing P5A globally added `_p5a_original_execute` to `psycopg.Connection`. | `VALID_BEHAVIORAL_RED` |

Runtime: Python 3.13.15; psycopg 3.3.5; psycopg-pool 3.3.1; PostgreSQL 18.6. `UV_RUNTIME_OBSERVED=unavailable`; `UV_LOCK_VERSION=0.12.13`.
