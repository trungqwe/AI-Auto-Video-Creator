# M2-P2 Behavioral RED — Quan sát

**Run ID:** `run-m2-p2-20260914120642`
**Trạng thái phase:** `M2-P2_RED_HARNESS_ACCEPTED_BLOCKED_EXTERNAL`

## Raw evidence trước diễn giải

- `red-p2-runtime-run-m2-p2-20260914120642-collect-stdout.txt`: collect exact 11 testcase identity sau correction hiện hành.
- `red-p2-runtime-run-m2-p2-20260914120642-pure-contract-stdout.txt`: RED thật riêng cho P2-001/P2-002, không phụ thuộc PostgreSQL.
- `red-p2-runtime-run-m2-p2-20260914120642-prerequisite-stdout.txt`: `M2_TEST_PG_DSN=UNSET`; P2-003..011 vẫn không được chạy PostgreSQL.
- Không có full-run stdout: PostgreSQL thật/`CREATEDB` chưa sẵn sàng, nên full run không được khởi động và không tạo evidence giả.

Các raw run trước, bao gồm `run-m2-p2-20260914115450`, được giữ immutable như historical/superseded. Run `120642` là collection/prerequisite evidence hiện hành.

## Expected versus observed

| Testcase | Expected RED capability | Observed | Classification |
|---|---|---|---|
| `test_tst_m2_p2_001_envelope_required_fields_and_rfc3339_utc` | Envelope matrix/RFC3339 UTC validation. | `NotImplementedError` từ structural `MessageEnvelope.create`, đúng capability envelope còn thiếu. | `VALID_BEHAVIORAL_RED` |
| `test_tst_m2_p2_002_problem_detail_transport_neutral_safe_contract` | ProblemDetail safe transport-neutral validation. | `NotImplementedError` từ structural `ProblemDetail.create`, đúng capability ProblemDetail còn thiếu. | `VALID_BEHAVIORAL_RED` |
| `test_tst_m2_p2_003_durable_command_receipt_persistence` | Durable receipt/idempotency persistence. | Không chạy do DSN unset. | `BLOCKED_EXTERNAL` |
| `test_tst_m2_p2_004_same_key_same_canonical_payload_replays_same_receipt` | RFC 8785 JCS bytes/hash and replay. | Không chạy do DSN unset. | `BLOCKED_EXTERNAL` |
| `test_tst_m2_p2_005_same_key_different_payload_rejected` | Reject hash mismatch for same key. | Không chạy do DSN unset. | `BLOCKED_EXTERNAL` |
| `test_tst_m2_p2_006_concurrent_same_key_same_payload_one_logical_receipt` | One accepted + one duplicate; one durable pair. | Không chạy do DSN unset. | `BLOCKED_EXTERNAL` |
| `test_tst_m2_p2_007_concurrent_same_key_different_payload_rejects_loser` | Winner receipt/hash and loser mismatch rejection. | Không chạy do DSN unset. | `BLOCKED_EXTERNAL` |
| `test_tst_m2_p2_008_workspace_scoped_idempotency_isolation_and_restart` | Workspace isolation plus persisted restart replay. | Không chạy do DSN unset. | `BLOCKED_EXTERNAL` |
| `test_tst_m2_p2_009_successful_revision_update_increments_exactly_once` | Active-UoW PostgreSQL CAS, rollback and one race winner. | Không chạy do DSN unset. | `BLOCKED_EXTERNAL` |
| `test_tst_m2_p2_010_stale_revision_conflict_zero_mutation_and_current_revision` | Stale CAS conflict/current revision/no mutation. | Không chạy do DSN unset. | `BLOCKED_EXTERNAL` |
| `test_tst_m2_p2_011_production_0002_forward_rollback_and_constraints` | Production `0002` up, constraints and direct transactional rollback. | Không chạy do DSN unset. | `BLOCKED_EXTERNAL` |

**Tổng hợp:** `VALID_BEHAVIORAL_RED=2`; `BLOCKED_EXTERNAL=9`; `ORACLE_MISMATCH=0`; `UNEXPECTED_PASS=0`; `DISPOSABLE_DB_ORPHANS=NOT_CHECKED`.

P2-001/002 đã có RED hợp lệ, còn P2-003..011 chờ PostgreSQL thật với `M2_TEST_PG_DSN` và `CREATEDB`. Khi có DSN, phải collect lại, chạy 9 oracle PostgreSQL không `-x`, lưu raw stdout trước diễn giải, chỉ công nhận failure chạm đúng oracle, và xác minh teardown orphan bằng 0.
