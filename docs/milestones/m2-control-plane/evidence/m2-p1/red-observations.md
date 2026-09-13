# M2-P1 Behavioral RED — Quan sát ban đầu

**Trạng thái phase:** `M2-P1_BEHAVIORAL_RED_BLOCKED_EXTERNAL`
**Ngày:** 13-09-2026
**Quyền hiện hành:** M2-P1 Plan `ACCEPTED`; Behavioral RED `AUTHORIZED`; implementation chưa được phép.

## Điều kiện tiên quyết PostgreSQL

Kiểm tra thực hiện bằng `.venv\\Scripts\\python.exe` (Python 3.13.15, `psycopg` và `pytest` import được). Kết quả môi trường:

```text
M2_TEST_PG_DSN=MISSING
POSTGRES=BLOCKED_EXTERNAL_M2_TEST_PG_DSN_MISSING
```

Không có giá trị DSN nào được đọc ra stdout/evidence. Không sử dụng credential dự phòng, database giả lập, hoặc database thay thế.

Vì thiếu `M2_TEST_PG_DSN`, fixture không được phép tạo database disposable. Do đó không có runtime evidence về `m2_p1_test_<uuid>` trong lần chạy này, và 11 oracle hiện đều không được chạy hay tính là RED sau correction. Fixture đã được đổi sang function scope: khi prerequisite sẵn sàng, từng mandatory oracle tạo database `m2_p1_test_<uuid>` riêng; kiểm tra `current_database()` ở target đúng identity đó; đóng mọi target connection trước teardown; rồi dùng admin connection khác target để `DROP DATABASE` sau khi xác minh exact regex/identity.

Raw prerequisite output nằm tại `red-p1-prerequisite-stdout.txt`; nó xác nhận blocker được báo đúng ở setup, không bị ngụy trang thành RED:

```text
Command: .venv\Scripts\python.exe -m pytest tests\m2\test_p1_db_and_workspace.py::test_tst_m2_p1_001_migration_forward_and_rollback_on_disposable_db -vv
Observed: ERROR at setup — Failed: BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required for M2-P1 integration RED; no fallback credential or mock database is permitted.
```

## Raw evidence

- `red-p1-collect-stdout.txt`: raw `--collect-only` của exact 11 oracle sau correction.
- `red-p1-prerequisite-stdout.txt`: raw `BLOCKED_EXTERNAL` run sau correction.
- `red-p1-stdout.txt`: RED P1-008 lịch sử đã được independent audit tại commit `65af9f84f881e03e7be95d1dda44243030aca1f6` xác nhận hợp lệ. Vì P1-008 nay cũng dùng function-scoped disposable fixture, nó phải được rerun sau khi DSN có sẵn.
- Mỗi RED run trên PostgreSQL sau này sẽ lưu raw stdout riêng thành `red-p1-<run-id>-stdout.txt` trước mọi human interpretation.

## Kiểm tra collection

```text
Command: .venv\\Scripts\\python.exe -m pytest tests\\m2\\test_p1_db_and_workspace.py --collect-only -q
Result: 11 tests collected in 0.07s; raw output: `red-p1-collect-stdout.txt`.
```

Collection hoàn tất không có `ModuleNotFoundError`, syntax error, hay test bị skip. Các stub chỉ tồn tại để import thành công; mọi public method chưa hiện thực đều ném `NotImplementedError`.

## Expected vs. observed

| Test ID | Expected RED failure theo oracle khóa | Observed | Kết luận |
|---|---|---|---|
| `test_tst_m2_p1_001_migration_forward_and_rollback_on_disposable_db` | `MigrationRunner` chưa có forward/down trên disposable DB. | Chưa chạy: `BLOCKED_EXTERNAL` trước fixture vì thiếu `M2_TEST_PG_DSN`. | Không tính RED. |
| `test_tst_m2_p1_002_migration_checksum_tamper_rejected` | Không có SHA-256 tamper verification trên migration sandbox. | Chưa chạy: `BLOCKED_EXTERNAL` trước fixture. | Không tính RED. |
| `test_tst_m2_p1_003_migration_version_gap_and_duplicate_rejected` | Không có strict gap/duplicate validation trên migration sandbox. | Chưa chạy: `BLOCKED_EXTERNAL` trước fixture. | Không tính RED. |
| `test_tst_m2_p1_004_bounded_advisory_lock_and_timeout` | Không có bounded advisory-lock timeout. | Chưa chạy: `BLOCKED_EXTERNAL` trước fixture. | Không tính RED. |
| `test_tst_m2_p1_005_uow_transaction_atomicity_and_rollback` | Bootstrap test-only rồi chạm UoW/repository transaction boundary. | Chưa chạy: `BLOCKED_EXTERNAL` trước fixture. | Không tính RED. |
| `test_tst_m2_p1_006_workspace_isolation_and_composite_fk_enforcement` | Thiếu composite FK phải tạo RED `DID NOT RAISE ForeignKeyViolation`. | Chưa chạy: `BLOCKED_EXTERNAL` trước fixture. | Không tính RED. |
| `test_tst_m2_p1_007_cross_workspace_read_and_status_mutation_prevented` | Direct-SQL seed thật, rồi chạm scoped get/list/status/revoke/expire. | Chưa chạy: `BLOCKED_EXTERNAL` trước fixture. | Không tính RED. |
| `test_tst_m2_p1_008_destructive_guard_rejects_non_test_db` | Guard chưa reject non-fixture name hoặc `is_test_env=False`. | RED lịch sử hợp lệ ở `red-p1-stdout.txt`; bản function-scoped hiện tại chưa rerun vì thiếu DSN. | Không tính vào confirmation sau correction. |
| `test_tst_m2_p1_009_applied_migration_file_missing_rejected` | Không có applied-file-missing fail-closed trong sandbox. | Chưa chạy: `BLOCKED_EXTERNAL` trước fixture. | Không tính RED. |
| `test_tst_m2_p1_010_sql_migration_failure_rolls_back_without_applied_record` | Không có rollback toàn bộ side effect/applied row với broken sandbox SQL. | Chưa chạy: `BLOCKED_EXTERNAL` trước fixture. | Không tính RED. |
| `test_tst_m2_p1_011_uow_rollback_returns_clean_connection_to_pool` | Bootstrap test-only rồi chạm TransactionManager/UoW/pool cleanliness. | Chưa chạy: `BLOCKED_EXTERNAL` trước fixture. | Không tính RED. |

## Migration fault sandbox

Các oracle P1-002, P1-003, P1-009 và P1-010 chỉ copy `src/controlplane/infrastructure/db/migrations/` sang `tmp_path/migration-sandbox`. Mọi add/tamper/delete, gồm SQL lỗi có chủ đích, đều ở bản sao temporary. Fixture xóa sandbox trong `finally` và so sánh SHA-256 tree trước/sau để bảo đảm production migration source không đổi.

## Test-only downstream bootstrap

P1-005, P1-006, P1-007 và P1-011 dùng `bootstrap_identity_schema` chỉ trong `tests/m2/test_p1_db_and_workspace.py`. Fixture tạo object prerequisite trực tiếp trong exact function-scoped disposable DB và bị drop cùng DB. Nó không gọi hay thay đổi `MigrationRunner`, không có SQL migration production, và P1-006 cố ý thiếu composite FK để quan sát `DID NOT RAISE ForeignKeyViolation` đúng oracle invariant.

## Điểm tiếp tục

Cần cung cấp `M2_TEST_PG_DSN` có khả năng kết nối PostgreSQL và quyền `CREATEDB`. Khi đó chạy lại đủ 11 oracle trên database function-scoped, xác nhận từng failure là oracle failure (không phải fixture/setup), lưu raw stdout từng run trước khi cập nhật `red-observations.md`, và chỉ khi đủ 11 RED hợp lệ mới chuyển tới `M2-P1_RED_CONFIRMED`.
