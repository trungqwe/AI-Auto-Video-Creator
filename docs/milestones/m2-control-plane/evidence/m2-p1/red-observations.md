# M2-P1 Behavioral RED — Quan sát

**Trạng thái phase:** `M2-P1_BEHAVIORAL_RED_CORRECTION_REQUIRED`
**Ngày:** 13-09-2026
**Quyền hiện hành:** M2-P1 Plan `ACCEPTED`; Behavioral RED `AUTHORIZED`; implementation chưa được phép.

## Kết luận hiện hành

Run PostgreSQL thật `ba8100a55e714332a3ebe41ca9d18944` đã collect đúng 11 oracle khóa và chạy đủ 11 oracle trên database disposable function-scoped riêng. Có 5 failure được phân loại `VALID_BEHAVIORAL_RED`; 6 failure là `ORACLE_MISMATCH` vì dừng tại structural stub chung trước capability chuyên biệt của oracle. Không có `INVALID_SETUP_FAILURE` hay `UNEXPECTED_PASS`.

Do chưa có 11/11 Behavioral RED hợp lệ, phase không được chuyển sang `M2-P1_RED_CONFIRMED`. Không được viết implementation P1, tự sửa production behavior, sửa P0, tự làm GREEN, hoặc mở P2. Việc hiệu chỉnh harness tiếp theo cần quyết định của independent audit.

## Runtime PostgreSQL thật — run `ba8100a55e714332a3ebe41ca9d18944`

Một PostgreSQL riêng biệt, disposable, dùng image đã khóa `postgres:18.6` được provision cục bộ với credential ngẫu nhiên chỉ tồn tại trong process/session. Không dùng container M1, database chia sẻ, credential fallback, mock, hoặc DSN được lưu trong repository/evidence. Raw prerequisite không chứa DSN/password và xác nhận:

```text
POSTGRES_PROVISION=PASS
POSTGRES_IMAGE=postgres:18.6
POSTGRES_BINDING=127.0.0.1:55433->5432
PREFLIGHT_POSTGRES_REACHABLE=PASS
PREFLIGHT_POSTGRES_VERSION=18.6 (Debian 18.6-1.pgdg13+2)
PREFLIGHT_CURRENT_DATABASE=postgres
PREFLIGHT_CURRENT_USER=m2p1_red
PREFLIGHT_CREATEDB=TRUE
PREFLIGHT_DSN=REDACTED
```

Fixture tạo một `m2_p1_test_<uuid>` cho từng oracle, xác minh target identity, đóng target connection trước khi admin connection drop đúng target database. Cuối run: `DISPOSABLE_DB_ORPHANS=0` và `POSTGRES_CONTAINER_CLEANUP_EXIT_CODE=0`.

Một lần thử provision trước run này đã bị loại khỏi evidence vì `repr` của fixture có thể đưa DSN vào pytest output. Không lưu raw output đó; container đã bị dừng/xóa và kiểm tra orphan đạt 0. Thay đổi test-only hẹp `dsn: str = field(repr=False)` loại khả năng lộ DSN; không thay đổi oracle hay production behavior. Run được ghi bên dưới diễn ra sau thay đổi này.

## Raw evidence

### Runtime PostgreSQL thật

- `red-p1-runtime-ba8100a55e714332a3ebe41ca9d18944-prerequisite-stdout.txt`: provision/preflight PostgreSQL thật, chỉ dữ liệu không bí mật.
- `red-p1-runtime-ba8100a55e714332a3ebe41ca9d18944-collect-stdout.txt`: raw `--collect-only` của exact 11 oracle; `11 tests collected in 0.07s`.
- `red-p1-runtime-ba8100a55e714332a3ebe41ca9d18944-stdout.txt`: raw full run không dùng `-x`; 11 failed, exit code 1, orphan 0 và container cleanup 0. Tệp này được lưu trước diễn giải trong tài liệu này.

### Lịch sử prerequisite bị chặn

- `red-p1-collect-stdout.txt`: raw `--collect-only` của exact 11 oracle sau correction trước runtime PostgreSQL.
- `red-p1-prerequisite-stdout.txt`: raw `BLOCKED_EXTERNAL` run đơn lẻ khi `M2_TEST_PG_DSN` chưa có.
- `red-p1-prerequisite-full-suite-stdout.txt`: raw full-suite historical: 11/11 setup lỗi `BLOCKED_EXTERNAL`, không oracle nào chạm behavior.
- `red-p1-stdout.txt`: RED P1-008 lịch sử đã được independent audit tại commit `65af9f84f881e03e7be95d1dda44243030aca1f6` xác nhận. Nó không thay thế runtime evidence function-scoped hiện hành.

## Kiểm tra collection runtime

```text
Command: .venv\Scripts\python.exe -m pytest tests\m2\test_p1_db_and_workspace.py --collect-only -q
Result: 11 tests collected in 0.07s.
```

Không có `ModuleNotFoundError`, syntax error, skipped test hay setup failure trong full runtime run. Structural stub chỉ để import thành công; chúng không tự động được tính là Behavioral RED nếu dừng trước capability chuyên biệt đã khóa.

## Expected vs. observed — runtime PostgreSQL thật

| Test ID | Expected oracle | Observed failure | Phân loại |
|---|---|---|---|
| `test_tst_m2_p1_001_migration_forward_and_rollback_on_disposable_db` | `MigrationRunner` chưa có forward/down trên disposable DB. | `NotImplementedError`: `MigrationRunner.migrate_up` (line 32), ngay tại entry point forward. | `VALID_BEHAVIORAL_RED` |
| `test_tst_m2_p1_002_migration_checksum_tamper_rejected` | SHA-256 tamper verification trên migration sandbox. | `MigrationRunner.migrate_up` chưa implement trước khi migration được apply/tamper. | `ORACLE_MISMATCH` |
| `test_tst_m2_p1_003_migration_version_gap_and_duplicate_rejected` | Strict gap/duplicate validation trên migration sandbox. | `MigrationRunner.migrate_up` chưa implement trước discovery/validation gap hoặc duplicate. | `ORACLE_MISMATCH` |
| `test_tst_m2_p1_004_bounded_advisory_lock_and_timeout` | Bounded advisory-lock timeout. | `MigrationRunner.acquire_advisory_lock` chưa implement trước lock thứ nhất/timeout lock thứ hai. | `ORACLE_MISMATCH` |
| `test_tst_m2_p1_005_uow_transaction_atomicity_and_rollback` | Bootstrap test-only rồi chạm UoW/repository transaction boundary. | `NotImplementedError`: `TransactionManager.unit_of_work` (line 44) sau bootstrap, tại UoW boundary. | `VALID_BEHAVIORAL_RED` |
| `test_tst_m2_p1_006_workspace_isolation_and_composite_fk_enforcement` | Thiếu composite FK phải tạo `DID NOT RAISE ForeignKeyViolation`. | `Failed: DID NOT RAISE ForeignKeyViolation` sau direct-SQL seed/insertion trên PostgreSQL thật. | `VALID_BEHAVIORAL_RED` |
| `test_tst_m2_p1_007_cross_workspace_read_and_status_mutation_prevented` | Direct-SQL seed thật, rồi chạm scoped get/list/status/revoke/expire. | `WorkspaceUseCases.get` chưa implement (line 30) sau seed A/B, Actor B và AuthSession B; failure tại operation scoped đầu tiên. | `VALID_BEHAVIORAL_RED` |
| `test_tst_m2_p1_008_destructive_guard_rejects_non_test_db` | Guard reject non-fixture name hoặc `is_test_env=False`. | `NotImplementedError`: `DestructiveRollbackGuard.assert_allowed` (line 13), tại guard entry point. | `VALID_BEHAVIORAL_RED` |
| `test_tst_m2_p1_009_applied_migration_file_missing_rejected` | Applied-file-missing fail-closed trong sandbox. | `MigrationRunner.migrate_up` chưa implement trước sandbox file delete/validation. | `ORACLE_MISMATCH` |
| `test_tst_m2_p1_010_sql_migration_failure_rolls_back_without_applied_record` | Broken sandbox SQL rollback, không để applied row. | `MigrationRunner.migrate_up` chưa implement trước khi chạy SQL lỗi/kiểm tra rollback. | `ORACLE_MISMATCH` |
| `test_tst_m2_p1_011_uow_rollback_returns_clean_connection_to_pool` | Bootstrap test-only rồi chạm UoW/pool max-size-one, backend PID và clean borrower. | Assertion expected `force rollback`, actual `TransactionManager.unit_of_work` chưa implement; không chạm return/borrow/PID pool behavior. | `ORACLE_MISMATCH` |

**Tổng hợp:** `VALID_BEHAVIORAL_RED=5`; `ORACLE_MISMATCH=6`; `INVALID_SETUP_FAILURE=0`; `UNEXPECTED_PASS=0`.

## Migration fault sandbox

Các oracle P1-002, P1-003, P1-009 và P1-010 chỉ copy `src/controlplane/infrastructure/db/migrations/` sang `tmp_path/migration-sandbox`. Mọi add/tamper/delete, gồm SQL lỗi có chủ đích, đều ở bản sao temporary. Fixture xóa sandbox trong `finally` và so sánh SHA-256 tree trước/sau để bảo đảm production migration source không đổi.

## Test-only downstream bootstrap

P1-005, P1-006, P1-007 và P1-011 dùng `bootstrap_identity_schema` chỉ trong `tests/m2/test_p1_db_and_workspace.py`. Fixture tạo object prerequisite trực tiếp trong exact function-scoped disposable DB và bị drop cùng DB. Nó không gọi hay thay đổi `MigrationRunner`, không có SQL migration production, và P1-006 cố ý thiếu composite FK để quan sát `DID NOT RAISE ForeignKeyViolation` đúng oracle invariant.

## Điểm tiếp tục

`M2-P1_BEHAVIORAL_RED_CORRECTION_REQUIRED`: independent audit cần đánh giá sáu mismatch và quyết định mọi test/harness correction. Chưa có quyền implementation P1 hoặc GREEN. Sau một correction được phê duyệt, phải rerun exact 11 oracle trên PostgreSQL thật, lưu raw stdout trước human interpretation và chỉ chuyển `M2-P1_RED_CONFIRMED` khi 11/11 là `VALID_BEHAVIORAL_RED`.
