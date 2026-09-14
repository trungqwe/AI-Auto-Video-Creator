# M2-P3 migration and stream oracle RED observations

- Run: `run-m2-p3-20260914154500`; PostgreSQL Docker 18.6; `CREATEDB=true`.
- Runtime: Python 3.13.15, psycopg 3.3.5, psycopg-pool 3.3.1, `psycopg_pool.ConnectionPool`.
- Exact collection: 11. Full execution: 11 failed. Orphans: 0. Architecture: 6 passed.

All 11 tests are `VALID_BEHAVIORAL_RED`: P3-001 fails because production `0003` is absent; P3-002..P3-011 fail directly at their structural P3 seams (`OutboxWriter`, `OutboxPublisher`, `EventConsumer`, or `OperationStreamProjector`). Totals: VALID=11; all other classifications=0.
