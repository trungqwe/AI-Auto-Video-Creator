# M2-P5A RED hardening observations

Prerequisites succeeded against the disposable PostgreSQL 18.6 runtime: Python 3.13.15, psycopg 3.3.5, psycopg-pool 3.3.1, actual `psycopg_pool.pool.ConnectionPool`, `CREATEDB=true`, port 56280, and orphan count 0. Every durable oracle operation receives an explicit active `SqlUnitOfWork.connection`; no global connection, database lookup, admin DSN business use, or repository-owned pool is used.

| ID | Observed failure | Classification |
|---|---|---|
| P5A-001 | `ConfigRevisionService` raises `NotImplementedError` after the explicit UoW connection path is established | `VALID_BEHAVIORAL_RED` |
| P5A-002 | `SecretHandleStore` raises `NotImplementedError` on the positive metadata registration path with an explicit UoW connection | `VALID_BEHAVIORAL_RED` |
| P5A-003 | `ConfigEventFactory.publish_event` raises `NotImplementedError`; invalidation coverage and accepted payload-safety canaries remain present | `VALID_BEHAVIORAL_RED` |
| P5A-004 | Production `0004_config_and_secrets.sql` and rollback are absent before migration constraint probes | `VALID_BEHAVIORAL_RED` |
| P5A-005 | Production-facing seed raises `NotImplementedError` with an explicit UoW connection before concurrent per-worker publish paths | `VALID_BEHAVIORAL_RED` |

Exact result: 5 collected, 5 failed, 0 errors, 0 skipped. No import, setup, DSN, closed-connection, or UoW misuse failure occurred.
