# M2-P2 Behavioral RED — Quan sát

**Run ID:** `run-m2-p2-20260914131500`
**Trạng thái phase:** `M2-P2_RED_READY_FOR_REVIEW`

## Raw evidence trước diễn giải

- `red-p2-runtime-run-m2-p2-20260914131500-prerequisite-stdout.txt`: PostgreSQL Docker 18.6, `CREATEDB=true`, Python 3.13.15, psycopg 3.3.5 và psycopg-pool 3.3.1.
- `red-p2-runtime-run-m2-p2-20260914131500-collect-stdout.txt`: exact 11 locked testcase identities collected.
- `red-p2-runtime-run-m2-p2-20260914131500-stdout.txt`: full exact-11 run không `-x`; 11 failures được ghi nguyên bản trước diễn giải.
- `red-p2-runtime-run-m2-p2-20260914131500-postrun-stdout.txt`: independent admin query xác nhận `DISPOSABLE_DB_ORPHANS=0`.

Toàn bộ raw run trước, gồm `011501`, `011618`, `012516`, `115219`, `115450`, `120642`, `122615`, `123753` và `130238`, giữ immutable như historical/superseded. Run `131500` là RED candidate authoritative hiện hành. Container Docker do run này tạo đã được xóa sau post-run query; credential/DSN chỉ tồn tại trong process và không xuất hiện trong evidence.

## Runtime và execution

- `POSTGRES_SOURCE=DOCKER`; `POSTGRESQL=18.6`; `CREATEDB=true`.
- `PYTHON=3.13.15`; `PSYCOPG=3.3.5`; `PSYCOPG_POOL=3.3.1`.
- Collection: `11 tests collected in 0.07s`.
- Full pytest: `11 failed in 2.02s`; không skipped, không unexpected pass.
- `DISPOSABLE_DB_ORPHANS=0`.

## Expected versus observed

| Testcase | Expected capability | Observed failure and location | Classification |
|---|---|---|---|
| `test_tst_m2_p2_001_envelope_required_fields_and_rfc3339_utc` | Envelope matrix/RFC3339 UTC validation. | `NotImplementedError` — `MessageEnvelope.create`, `contracts.py:7`. | `VALID_BEHAVIORAL_RED` |
| `test_tst_m2_p2_002_problem_detail_transport_neutral_safe_contract` | Safe transport-neutral ProblemDetail validation. | `NotImplementedError` — `ProblemDetail.create`, `contracts.py:13`. | `VALID_BEHAVIORAL_RED` |
| `test_tst_m2_p2_003_durable_command_receipt_persistence` | Durable receipt/idempotency persistence. | `NotImplementedError` — `IdempotencyCoordinator.submit`, `application/idempotency/ports.py:10`; disposable DB/bootstrap completed. | `VALID_BEHAVIORAL_RED` |
| `test_tst_m2_p2_004_same_key_same_canonical_payload_replays_same_receipt` | RFC 8785 JCS, logical request hash and replay. | `NotImplementedError` — `canonicalize_json`, `application/idempotency/canonicalization.py:5`; disposable DB/bootstrap completed. | `VALID_BEHAVIORAL_RED` |
| `test_tst_m2_p2_005_same_key_different_payload_rejected` | Same-key/different-payload rejection. | `NotImplementedError` on initial `IdempotencyCoordinator.submit`, `application/idempotency/ports.py:10`; prerequisite coordinator behavior blocks mismatch branch. | `UPSTREAM_PATH_RED` |
| `test_tst_m2_p2_006_concurrent_same_key_same_payload_one_logical_receipt` | Concurrent same-payload dedupe. | `NotImplementedError` from both worker calls to `IdempotencyCoordinator.submit`, `application/idempotency/ports.py:10`; thread execution reached the public coordinator path. | `UPSTREAM_PATH_RED` |
| `test_tst_m2_p2_007_concurrent_same_key_different_payload_rejects_loser` | Concurrent different-payload winner/loser semantics. | `NotImplementedError` from worker `IdempotencyCoordinator.submit`, `application/idempotency/ports.py:10`; prerequisite coordinator behavior blocks winner/loser branch. | `UPSTREAM_PATH_RED` |
| `test_tst_m2_p2_008_workspace_scoped_idempotency_isolation_and_restart` | Workspace-isolated durable replay after restart. | `NotImplementedError` on first `IdempotencyCoordinator.submit`, `application/idempotency/ports.py:10`; prerequisite durable command path blocks restart branch. | `UPSTREAM_PATH_RED` |
| `test_tst_m2_p2_009_successful_revision_update_increments_exactly_once` | Active-UoW PostgreSQL CAS success/rollback/race. | `NotImplementedError` — `PostgresRevisionedMutationAdapter.mutate`, `infrastructure/db/concurrency/postgres_cas.py:9`; active UoW and probe relation were created. | `VALID_BEHAVIORAL_RED` |
| `test_tst_m2_p2_010_stale_revision_conflict_zero_mutation_and_current_revision` | Stale CAS conflict/current revision/zero mutation. | `NotImplementedError` — `PostgresRevisionedMutationAdapter.mutate`, `infrastructure/db/concurrency/postgres_cas.py:9`; adapter prerequisite blocks stale-conflict branch. | `UPSTREAM_PATH_RED` |
| `test_tst_m2_p2_011_production_0002_forward_rollback_and_constraints` | Production P2 migration/schema and rollback semantics. | `AssertionError` — `test_p2_envelopes_and_idempotency.py:366`: P1 migration runner applied `0001`, P2 receipt/idempotency tables are absent (`(None, None)`). | `VALID_BEHAVIORAL_RED` |

**Tổng hợp:** `VALID_BEHAVIORAL_RED=6`; `UPSTREAM_PATH_RED=5`; `INVALID_SETUP_FAILURE=0`; `ORACLE_MISMATCH=0`; `UNEXPECTED_PASS=0`; `DISPOSABLE_DB_ORPHANS=0`.

Tất cả 11 oracle đã chạy trên prerequisite thật và thất bại trên capability P2 đang thiếu; không có setup/fixture/import mismatch. Đây là `M2-P2_RED_READY_FOR_REVIEW`, không phải `M2-P2_RED_CONFIRMED` và không ủy quyền implementation. Dừng để independent audit.
