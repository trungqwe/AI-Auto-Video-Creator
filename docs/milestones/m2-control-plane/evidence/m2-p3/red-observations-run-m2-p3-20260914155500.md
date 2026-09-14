# M2-P3 final assertion RED observations

- Run `run-m2-p3-20260914155500`: exact runtime (Python 3.13.15, psycopg 3.3.5, psycopg-pool 3.3.1, ConnectionPool) and Docker PostgreSQL 18.6 with `CREATEDB=true`.
- Exact collection: 11; full execution: 11 failed; disposable orphans: 0; architecture: 6 passed.
- P3-001 fails only on absent production `0003`; P3-002..011 fail at their direct structural seams. All 11 are `VALID_BEHAVIORAL_RED`; all other classifications are 0.
