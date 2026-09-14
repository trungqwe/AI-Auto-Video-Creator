# M2-P3 complete migration-oracle RED observations

- Run `run-m2-p3-20260914155000`: Python 3.13.15, psycopg 3.3.5, psycopg-pool 3.3.1, Docker PostgreSQL 18.6, `CREATEDB=true`.
- Exact collection: 11; full execution: 11 failed; orphan databases: 0; architecture: 6 passed.
- P3-001 remains direct RED because production migration `0003` is absent. P3-002..011 remain direct structural-seam RED. All 11 classifications are `VALID_BEHAVIORAL_RED`; all other classifications are 0.
