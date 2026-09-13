# M2-P1 Behavioral RED — Quan sát

**Trạng thái phase:** `M2-P1_RED_CONFIRMED`
**Ngày:** 13-09-2026
**Quyền hiện hành:** M2-P1 Plan `ACCEPTED`; Behavioral RED `CONFIRMED`; implementation M2-P1 `AUTHORIZED`.

## Kết luận hiện hành

Independent audit đối chiếu raw PostgreSQL evidence với `docs/10-test-strategy.md` và xác nhận `M2-P1_RED_CONFIRMED`. Run `ba8100a55e714332a3ebe41ca9d18944` đã collect đúng 11 oracle khóa và chạy đủ 11 oracle trên database disposable function-scoped riêng; 11/11 fail trước implementation ở execution path của required production behavior. Có 5 `DIRECT_TARGET_RED` và 6 `UPSTREAM_PATH_RED` do prerequisite behavior cùng package chưa được implement. Không có `INVALID_SETUP_FAILURE` hay `UNEXPECTED_PASS`.

Phân loại direct/upstream chỉ là diagnostic lịch sử, không phải lý do tiếp tục chỉnh harness để ép oracle dependent đi sâu hơn trước implementation. Audit xác nhận điều đó sẽ tạo implementation-detail seams trái `TEST-PRINCIPLE-002`. M2-P1 implementation được ủy quyền; P0 không đổi và P2 vẫn không được mở.

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

Không có `ModuleNotFoundError`, syntax error, skipped test hay setup failure trong full runtime run. Structural stub chỉ để import thành công; independent audit xác nhận các failure trên execution path của required production behavior là RED hợp lệ ở cấp package, gồm cả upstream-path RED.

## Expected vs. observed — runtime PostgreSQL thật

| Test ID | Expected oracle | Observed failure | Phân loại |
|---|---|---|---|
| `test_tst_m2_p1_001_migration_forward_and_rollback_on_disposable_db` | `MigrationRunner` chưa có forward/down trên disposable DB. | `NotImplementedError`: `MigrationRunner.migrate_up` (line 32), ngay tại entry point forward. | `DIRECT_TARGET_RED` |
| `test_tst_m2_p1_002_migration_checksum_tamper_rejected` | SHA-256 tamper verification trên migration sandbox. | `MigrationRunner.migrate_up` chưa implement trước khi migration được apply/tamper. | `UPSTREAM_PATH_RED` |
| `test_tst_m2_p1_003_migration_version_gap_and_duplicate_rejected` | Strict gap/duplicate validation trên migration sandbox. | `MigrationRunner.migrate_up` chưa implement trước discovery/validation gap hoặc duplicate. | `UPSTREAM_PATH_RED` |
| `test_tst_m2_p1_004_bounded_advisory_lock_and_timeout` | Bounded advisory-lock timeout. | `MigrationRunner.acquire_advisory_lock` chưa implement trước lock thứ nhất/timeout lock thứ hai. | `UPSTREAM_PATH_RED` |
| `test_tst_m2_p1_005_uow_transaction_atomicity_and_rollback` | Bootstrap test-only rồi chạm UoW/repository transaction boundary. | `NotImplementedError`: `TransactionManager.unit_of_work` (line 44) sau bootstrap, tại UoW boundary. | `DIRECT_TARGET_RED` |
| `test_tst_m2_p1_006_workspace_isolation_and_composite_fk_enforcement` | Thiếu composite FK phải tạo `DID NOT RAISE ForeignKeyViolation`. | `Failed: DID NOT RAISE ForeignKeyViolation` sau direct-SQL seed/insertion trên PostgreSQL thật. | `DIRECT_TARGET_RED` |
| `test_tst_m2_p1_007_cross_workspace_read_and_status_mutation_prevented` | Direct-SQL seed thật, rồi chạm scoped get/list/status/revoke/expire. | `WorkspaceUseCases.get` chưa implement (line 30) sau seed A/B, Actor B và AuthSession B; failure tại operation scoped đầu tiên. | `DIRECT_TARGET_RED` |
| `test_tst_m2_p1_008_destructive_guard_rejects_non_test_db` | Guard reject non-fixture name hoặc `is_test_env=False`. | `NotImplementedError`: `DestructiveRollbackGuard.assert_allowed` (line 13), tại guard entry point. | `DIRECT_TARGET_RED` |
| `test_tst_m2_p1_009_applied_migration_file_missing_rejected` | Applied-file-missing fail-closed trong sandbox. | `MigrationRunner.migrate_up` chưa implement trước sandbox file delete/validation. | `UPSTREAM_PATH_RED` |
| `test_tst_m2_p1_010_sql_migration_failure_rolls_back_without_applied_record` | Broken sandbox SQL rollback, không để applied row. | `MigrationRunner.migrate_up` chưa implement trước khi chạy SQL lỗi/kiểm tra rollback. | `UPSTREAM_PATH_RED` |
| `test_tst_m2_p1_011_uow_rollback_returns_clean_connection_to_pool` | Bootstrap test-only rồi chạm UoW/pool max-size-one, backend PID và clean borrower. | Assertion expected `force rollback`, actual `TransactionManager.unit_of_work` chưa implement; không chạm return/borrow/PID pool behavior. | `UPSTREAM_PATH_RED` |

**Tổng hợp:** `BEHAVIORAL_RED_CONFIRMED=11/11`; `DIRECT_TARGET_RED=5`; `UPSTREAM_PATH_RED=6`; `INVALID_SETUP_FAILURE=0`; `UNEXPECTED_PASS=0`; `DISPOSABLE_DB_ORPHANS=0`.

## Migration fault sandbox

Các oracle P1-002, P1-003, P1-009 và P1-010 chỉ copy `src/controlplane/infrastructure/db/migrations/` sang `tmp_path/migration-sandbox`. Mọi add/tamper/delete, gồm SQL lỗi có chủ đích, đều ở bản sao temporary. Fixture xóa sandbox trong `finally` và so sánh SHA-256 tree trước/sau để bảo đảm production migration source không đổi.

## Test-only downstream bootstrap

P1-005, P1-006, P1-007 và P1-011 dùng `bootstrap_identity_schema` chỉ trong `tests/m2/test_p1_db_and_workspace.py`. Fixture tạo object prerequisite trực tiếp trong exact function-scoped disposable DB và bị drop cùng DB. Nó không gọi hay thay đổi `MigrationRunner`, không có SQL migration production, và P1-006 cố ý thiếu composite FK để quan sát `DID NOT RAISE ForeignKeyViolation` đúng oracle invariant.

## Điểm tiếp tục

`M2-P1_RED_CONFIRMED`: independent audit đã ủy quyền implementation P1. Thực hiện `RED → IMPLEMENT → RUN → TEST → FIX → VERIFY → EVIDENCE → COMMIT`; không hạ/đổi oracle, không sửa P0 và không mở P2. Sau P1 GREEN cùng evidence hoàn chỉnh, dừng tại `M2-P1_READY_FOR_REVIEW`.
