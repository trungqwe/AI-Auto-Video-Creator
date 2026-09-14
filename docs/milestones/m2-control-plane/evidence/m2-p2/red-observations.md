# M2-P2 Behavioral RED — Quan sát

**Run ID:** `run-m2-p2-20260914130238`
**Trạng thái phase:** `M2-P2_BEHAVIORAL_RED_BLOCKED_EXTERNAL`

## Raw evidence trước diễn giải

- `red-p2-runtime-run-m2-p2-20260914130238-prerequisite-stdout.txt`: Python/driver lock đạt; DSN absent và Docker daemon unavailable, nên PostgreSQL/`CREATEDB`/orphan không thể kiểm tra.
- Không có collection hay full pytest stdout cho run `130238`: prerequisite external fail buộc STOP trước các bước đó, không tạo raw artifact giả.
- Không có full-run stdout: PostgreSQL thật/`CREATEDB` chưa sẵn sàng, nên full run không được khởi động và không tạo evidence giả.

Toàn bộ raw run trước, gồm `011501`, `011618`, `012516`, `115219`, `115450`, `120642`, `122615` và `123753`, giữ immutable như historical/superseded. Run `130238` là prerequisite evidence hiện hành.

## Expected versus observed

| Testcase | Expected RED capability | Observed | Classification |
|---|---|---|---|
| `test_tst_m2_p2_001_envelope_required_fields_and_rfc3339_utc` | Envelope matrix/RFC3339 UTC validation. | Historical run `120642`: `NotImplementedError` từ structural `MessageEnvelope.create`, đúng capability envelope còn thiếu. | `VALID_BEHAVIORAL_RED` |
| `test_tst_m2_p2_002_problem_detail_transport_neutral_safe_contract` | ProblemDetail safe transport-neutral validation. | Historical run `120642`: `NotImplementedError` từ structural `ProblemDetail.create`, đúng capability ProblemDetail còn thiếu. | `VALID_BEHAVIORAL_RED` |
| `test_tst_m2_p2_003_durable_command_receipt_persistence` | Durable receipt/idempotency persistence. | Không chạy: DSN absent và Docker daemon unavailable trước PostgreSQL prerequisite. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_004_same_key_same_canonical_payload_replays_same_receipt` | RFC 8785 JCS bytes/hash and replay. | Không chạy: DSN absent và Docker daemon unavailable trước PostgreSQL prerequisite. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_005_same_key_different_payload_rejected` | Reject hash mismatch for same key. | Không chạy: DSN absent và Docker daemon unavailable trước PostgreSQL prerequisite. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_006_concurrent_same_key_same_payload_one_logical_receipt` | One accepted + one duplicate; one durable pair. | Không chạy: DSN absent và Docker daemon unavailable trước PostgreSQL prerequisite. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_007_concurrent_same_key_different_payload_rejects_loser` | Winner receipt/hash and loser mismatch rejection. | Không chạy: DSN absent và Docker daemon unavailable trước PostgreSQL prerequisite. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_008_workspace_scoped_idempotency_isolation_and_restart` | Workspace isolation plus persisted restart replay. | Không chạy: DSN absent trước PostgreSQL prerequisite. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_009_successful_revision_update_increments_exactly_once` | Active-UoW PostgreSQL CAS, rollback and one race winner. | Không chạy: DSN absent trước PostgreSQL prerequisite. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_010_stale_revision_conflict_zero_mutation_and_current_revision` | Stale CAS conflict/current revision/no mutation. | Không chạy: DSN absent trước PostgreSQL prerequisite. | `INVALID_SETUP_FAILURE` |
| `test_tst_m2_p2_011_production_0002_forward_rollback_and_constraints` | Production `0002` up, constraints and direct transactional rollback. | Không chạy: DSN absent trước PostgreSQL prerequisite. | `INVALID_SETUP_FAILURE` |

**Tổng hợp:** `VALID_BEHAVIORAL_RED=2`; `UPSTREAM_PATH_RED=0`; `INVALID_SETUP_FAILURE=9`; `ORACLE_MISMATCH=0`; `UNEXPECTED_PASS=0`; `DISPOSABLE_DB_ORPHANS=NOT_CHECKED`.

P2-001/002 đã có RED hợp lệ. P2-003..011 phải chờ PostgreSQL thật với `M2_TEST_PG_DSN` và `CREATEDB`; prerequisite failure của run này là `INVALID_SETUP_FAILURE`, không phải Behavioral RED. Khi có DSN, phải tạo run mới, collect exact 11, chạy full file không `-x`, lưu raw stdout trước diễn giải, và xác minh teardown orphan bằng 0.
