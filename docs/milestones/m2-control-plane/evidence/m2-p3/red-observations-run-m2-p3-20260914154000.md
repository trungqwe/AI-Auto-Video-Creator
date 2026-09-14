# M2-P3 final hardened RED observations

- Run ID: `run-m2-p3-20260914154000`; Docker PostgreSQL 18.6; `CREATEDB=true`.
- Runtime: Python 3.13.15, psycopg 3.3.5, psycopg-pool 3.3.1, `psycopg_pool.ConnectionPool`.
- Collection: exact 11. Full execution: 11 failed; orphan database count: 0; architecture: 6 passed.

| Testcase | Observed RED | Classification |
|---|---|---|
| P3-001 | Production `0003` absent | VALID_BEHAVIORAL_RED |
| P3-002 | `OutboxWriter.enqueue()` raises `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-003 | `OutboxPublisher.dispatch()` raises `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-004 | `EventConsumer.process()` raises `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-005 | Concurrent workers reach `EventConsumer.process()` `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-006 | `EventConsumer.process()` raises `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-007 | `EventConsumer.process()` raises `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-008 | `EventConsumer.process()` raises `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-009 | `EventConsumer.process()` raises `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-010 | Eight concurrent workers reach `OperationStreamProjector.append()` `NotImplementedError` | VALID_BEHAVIORAL_RED |
| P3-011 | `OperationStreamProjector.append()` raises `NotImplementedError` | VALID_BEHAVIORAL_RED |

Totals: `VALID_BEHAVIORAL_RED=11`, all other classifications `0`.
