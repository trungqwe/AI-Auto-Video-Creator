# M2-P3 Behavioral RED observations

- Run ID: `run-m2-p3-20260914153500`
- Runtime: Python 3.13.15; psycopg 3.3.5; psycopg-pool 3.3.1; `psycopg_pool.ConnectionPool`.
- PostgreSQL: Docker `postgres:18.6`; `CREATEDB=true`.
- Collection: exact 11 tests. Full run: 11 failed, 0 setup/import/fixture failures. Disposable database orphans: 0.

| Testcase | Expected RED | Observed failure | Classification |
|---|---|---|---|
| P3-001 | Production `0003` absent | Assertion that `0003_outbox_and_projections.sql` exists | VALID_BEHAVIORAL_RED |
| P3-002 | UoW-bound outbox seam absent | `OutboxWriter.enqueue()` `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-003 | Publisher seam absent | `OutboxPublisher.dispatch()` `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-004 | Consumer dedupe seam absent | `EventConsumer.process()` `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-005 | Concurrent consumer seam absent | `EventConsumer.process()` `NotImplementedError` from real concurrent workers | VALID_BEHAVIORAL_RED |
| P3-006 | Transactional consumer seam absent | `EventConsumer.process()` `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-007 | Quarantine consumer seam absent | `EventConsumer.process()` `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-008 | Ordering consumer seam absent | `EventConsumer.process()` `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-009 | Epoch consumer seam absent | `EventConsumer.process()` `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-010 | Stream projector seam absent | `OperationStreamProjector.append()` `NotImplementedError` from real concurrent workers | VALID_BEHAVIORAL_RED |
| P3-011 | Safe stream projector seam absent | `OperationStreamProjector.append()` `NotImplementedError` | VALID_BEHAVIORAL_RED |

Classification totals: `VALID_BEHAVIORAL_RED=11`; `UPSTREAM_PATH_RED=0`; `INVALID_SETUP_FAILURE=0`; `ORACLE_MISMATCH=0`; `UNEXPECTED_PASS=0`.
