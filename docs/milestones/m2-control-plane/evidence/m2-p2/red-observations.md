# M2-P2 Behavioral RED — Quan sát

**Run ID:** `run-m2-p2-20260914011618`  
**Trạng thái phase:** `M2-P2_BEHAVIORAL_RED_BLOCKED_EXTERNAL`

## Raw evidence trước diễn giải

- `red-p2-runtime-run-m2-p2-20260914011618-collect-stdout.txt`: exact 11 testcase identities collected sau correction scope của harness.
- `red-p2-runtime-run-m2-p2-20260914011618-prerequisite-stdout.txt`: Python/driver đạt nhưng `M2_TEST_PG_DSN=UNSET`.
- Không có `red-p2-runtime-run-m2-p2-20260914011618-stdout.txt`: full run không được khởi động vì prerequisite PostgreSQL thật chưa có; không được tạo raw output giả.

## Expected versus observed

| Testcase | Expected RED | Observed failure/capability | Classification |
|---|---|---|---|
| `test_tst_m2_p2_001_envelope_required_fields_and_rfc3339_utc` | Envelope matrix/RFC3339 validation chưa implement. | Không chạy: prerequisite phase dừng trước full suite do DSN không có. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_002_problem_detail_transport_neutral_safe_contract` | ProblemDetail transport-neutral contract chưa implement. | Không chạy: prerequisite phase dừng trước full suite do DSN không có. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_003_durable_command_receipt_persistence` | Receipt durable chưa implement. | Không chạy: PostgreSQL DSN/CREATEDB không thể xác minh. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_004_same_key_same_canonical_payload_replays_same_receipt` | JCS/replay chưa implement. | Không chạy: PostgreSQL DSN/CREATEDB không thể xác minh. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_005_same_key_different_payload_rejected` | Hash mismatch reject chưa implement. | Không chạy: PostgreSQL DSN/CREATEDB không thể xác minh. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_006_concurrent_same_key_same_payload_one_logical_receipt` | Race cùng payload chưa implement. | Không chạy: PostgreSQL DSN/CREATEDB không thể xác minh. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_007_concurrent_same_key_different_payload_rejects_loser` | Race payload khác chưa implement. | Không chạy: PostgreSQL DSN/CREATEDB không thể xác minh. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_008_workspace_scoped_idempotency_isolation_and_restart` | Workspace/restart durability chưa implement. | Không chạy: PostgreSQL DSN/CREATEDB không thể xác minh. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_009_successful_revision_update_increments_exactly_once` | PostgreSQL CAS matching/race/rollback chưa implement. | Không chạy: PostgreSQL DSN/CREATEDB không thể xác minh. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_010_stale_revision_conflict_zero_mutation_and_current_revision` | PostgreSQL CAS stale-conflict chưa implement. | Không chạy: PostgreSQL DSN/CREATEDB không thể xác minh. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_011_production_0002_forward_rollback_and_constraints` | Production migration `0002` chưa implement. | Không chạy: PostgreSQL DSN/CREATEDB không thể xác minh. | `INVALID_SETUP_FAILURE` |

**Tổng hợp:** `VALID_BEHAVIORAL_RED=0`; `UPSTREAM_PATH_RED=0`; `INVALID_SETUP_FAILURE=11`; `ORACLE_MISMATCH=0`; `UNEXPECTED_PASS=0`; `DISPOSABLE_DB_ORPHANS=NOT_CHECKED`.

Không testcase nào được coi là Behavioral RED. Cần cung cấp `M2_TEST_PG_DSN` cho PostgreSQL 18.6 thật với `CREATEDB`, sau đó tạo run ID mới, collect lại, chạy full suite không `-x`, lưu raw full stdout trước interpretation và kiểm tra orphan = 0.
