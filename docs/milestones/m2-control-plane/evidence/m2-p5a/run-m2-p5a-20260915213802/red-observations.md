# M2-P5A RED immutable-race observations

Runtime thật là PostgreSQL 18.6 trong Docker, `CREATEDB=true`, loopback port 56280. Pool proof phân biệt public import `psycopg_pool.ConnectionPool`, runtime class `psycopg_pool.pool.ConnectionPool` và borrowed connection class `psycopg.Connection`. `UV_RUNTIME_OBSERVED=unavailable` phản ánh không có executable uv project-local được quan sát; `UV_LOCK_VERSION=0.12.13` là version bị khóa trong `uv.lock`.

| ID | Observed failure | Classification |
|---|---|---|
| P5A-001 | `ConfigRevisionService.create_revision` raises `NotImplementedError` after the explicit active-UoW create path is established. The oracle retains equivalent-payload and changed-payload durable hash proofs. | `VALID_BEHAVIORAL_RED` |
| P5A-002 | `SecretHandleStore.register` raises `NotImplementedError` on the positive metadata path with an explicit active-UoW connection. | `VALID_BEHAVIORAL_RED` |
| P5A-003 | `ConfigEventFactory.publish_event` raises `NotImplementedError`; both event paths and payload-safety canaries remain in the oracle. | `VALID_BEHAVIORAL_RED` |
| P5A-004 | Production `0004_config_and_secrets.sql` and its rollback are absent before the production migration and constraint probes. | `VALID_BEHAVIORAL_RED` |
| P5A-005 | Production-facing seed raises `NotImplementedError` before the foreign-workspace, dedicated rollback, race-winner/conflict, stale-retry and duplicate-unique probes. The post-race oracle now requires the legitimate revision/status mutation while preserving all immutable facts by name. | `VALID_BEHAVIORAL_RED` |

Exact result: 5 collected, 5 failed, 0 errors, 0 skipped. No import, setup, DSN, closed-connection, or UoW misuse failure occurred. P4 regression is 9/9, architecture regression is 6/6, domain-to-application import count is 0, disposable database orphan count is 0, and secret scan is CLEAN/0.
