# Báo cáo PERSIST-J

## Tệp đã sửa/tạo

- `src/controlplane/infrastructure/db/config_security/stores.py` (mới)
- `src/controlplane/infrastructure/db/config_security/__init__.py`
- `tests/integration/persistence/j/test_persist_j_postgres.py` (mới)
- `docs/delivery-evidence/persist-j/report.md` (mới)

## Quyết định thiết kế và mục mở

1. Các kho PostgreSQL (`PostgresReservationStore`, `PostgresCostLedger`, `PostgresAuditSink`, `PostgresAccountTestReceiptStore`) đều nhận đối tượng connection do caller sở hữu và không tự commit giao dịch; quyền commit thuộc về Unit of Work của caller.
2. `PostgresReservationStore` và `PostgresAccountTestReceiptStore` nhận `(connection, workspace_id)` vì bảng `cp_capacity_reservations` và bản ghi audit receipt thuộc về một workspace xác định. `PostgresCostLedger` nhận `workspace_id` qua từng tham số gọi của port `CostLedgerPort`. `PostgresAuditSink` lấy `workspace_id` trực tiếp từ trường của `AuditRecord`.
3. GIẢ ĐỊNH: Migration 0009 không có bảng riêng lưu receipt cho `ReceiptStorePort` và việc thêm migration mới là ngoài phạm vi của task. Do đó, receipt kiểm thử tài khoản ngoài được lưu trữ trong bảng `cp_audit_records` (với `action='account_test'`, `audit_id` là `receipt_id` có tiền tố `acctest-`, `correlation_id` là `operation_key`, `resource_ref` là `external_account_id`, và JSON chi tiết trong `redacted_reason`). Cần chủ sở hữu migration xác nhận hoặc bổ sung bảng riêng ở slice sau.
4. `PostgresAuditSink` chỉ nhận revision dạng số (ánh xạ vào cột `BIGINT` của PostgreSQL); nếu `revision_before` hoặc `revision_after` là chuỗi không phải chữ số thì ném `ValueError` trước khi chạm vào cơ sở dữ liệu.
5. `PostgresCostLedger.append` có tính chất idempotent theo cặp khoá `(workspace_id, record_id)` nhờ mệnh đề `ON CONFLICT (workspace_id, record_id) DO NOTHING`.
6. Triển khai F1 (`list_effective_revisions`): đọc cột `effective_at` (kiểu `timestamptz`) từ bảng `cp_config_revisions` và đóng gói thành `EffectiveConfigRevision(revision, effective_at)` với `revision` là `ConfigRevision` 9 trường nguyên bản; không sửa đổi cấu trúc dataclass `ConfigRevision` hay hàm `_revision`.
7. `PostgresConfigSecurityRepository.register_secret_handle` tiếp nhận thêm `credential_version` và `revocation_version` (mặc định bằng 0) lưu vào `cp_secret_handles`, đồng thời cung cấp phương thức `secret_handle_versions` để đọc lại.
8. Tuyệt đối không tạo adapter PostgreSQL cho `SecretStorePort`; PostgreSQL không bao giờ lưu trữ giá trị bí mật (chỉ lưu handle và version).
9. Không thêm hoặc sửa đổi migration cơ sở dữ liệu.
10. Chưa ghi user checkpoint M2.

## RED trước implementation

Chứng kiến RED hợp lệ tại Bước 12 trên PostgreSQL 18.6 trước khi cài đặt adapter, hoàn toàn bằng `AssertionError` do các hàm stub gây ra; không có lỗi import, lỗi cú pháp hay lỗi setup/fixture:
- Lệnh: `python -m pytest tests/integration/persistence/j/test_persist_j_postgres.py -q -p no:cacheprovider`
- Tóm tắt: `13 failed, 5 passed in 7.60s` (exit code 1)
- Danh sách test fail:
  - `FAILED tests/integration/persistence/j/test_persist_j_postgres.py::test_reservation_store_round_trip_and_workspace_isolation`
  - `FAILED tests/integration/persistence/j/test_persist_j_postgres.py::test_reservation_operation_key_is_unique_per_workspace`
  - `FAILED tests/integration/persistence/j/test_persist_j_postgres.py::test_capacity_book_runs_on_postgres_store_with_expiry`
  - `FAILED tests/integration/persistence/j/test_persist_j_postgres.py::test_cost_ledger_round_trip_window_and_idempotent_append`
  - `FAILED tests/integration/persistence/j/test_persist_j_postgres.py::test_audit_sink_appends_and_rows_are_immutable`
  - `FAILED tests/integration/persistence/j/test_persist_j_postgres.py::test_audit_sink_rejects_duplicate_ids_and_non_numeric_revisions`
  - `FAILED tests/integration/persistence/j/test_persist_j_postgres.py::test_account_test_receipt_round_trip_and_idempotent_replay`
  - `FAILED tests/integration/persistence/j/test_account_test_failure_receipt_keeps_error_class`
  - `FAILED tests/integration/persistence/j/test_plain_audit_record_is_not_mistaken_for_receipt`
  - `FAILED tests/integration/persistence/j/test_receipt_store_requires_aware_tested_at_and_receipt_prefix`
  - `FAILED tests/integration/persistence/j/test_list_effective_revisions_builds_wrappers_with_aware_effective_at`
  - `FAILED tests/integration/persistence/j/test_resolve_bundle_uses_effective_at_read_from_postgres`
  - `FAILED tests/integration/persistence/j/test_secret_handle_versions_round_trip_and_defaults`

## GREEN sau implementation

Sau khi hoàn tất cài đặt các lớp trong `src/controlplane/infrastructure/db/config_security/stores.py` và phương thức trong `PostgresConfigSecurityRepository`, toàn bộ 18 test tích hợp chạy trên PostgreSQL 18.6 với cơ sở dữ liệu tạm riêng biệt cho từng bài test đều đạt tuyệt đối:
- Lệnh: `python -m pytest tests/integration/persistence/j/test_persist_j_postgres.py -q -p no:cacheprovider`
- Tóm tắt: `18 passed in 7.22s` (exit code 0)

## Lệnh đã chạy

| Bước | Lệnh | Exit code | Kết quả |
| --- | --- | --- | --- |
| 12 | `python -m pytest tests/integration/persistence/j/test_persist_j_postgres.py -q -p no:cacheprovider` | 1 | 13 failed, 5 passed in 7.60s (AssertionError do stub) |
| 20 | `python -m pytest tests/integration/persistence/j/test_persist_j_postgres.py -q -p no:cacheprovider` | 0 | 18 passed in 7.22s (toàn bộ 18 test đạt) |
| 21 | `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/config_security'); t = ' '.join(f.read_text(encoding='utf-8') for f in d.rglob('*.py')); assert 'EffectiveConfigRevision' in t and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t, 'adapter J'"` | 0 | Probe đạt: có EffectiveConfigRevision, không có DDL |
| 23 | `git diff --check` | 0 | Không có khoảng trắng thừa hoặc lỗi diff |
| 24 | `python -m pytest tests/integration/persistence/j/test_persist_j_postgres.py -q -p no:cacheprovider` | 0 | 18 passed in 6.51s (xác nhận trạng thái cuối cùng) |
