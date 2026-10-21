# Báo cáo PERSIST-F

## Tệp đã sửa/tạo

- `src/render/persistence/__init__.py`
- `src/render/persistence/_sql.py`
- `src/render/persistence/_codec.py`
- `src/render/persistence/repository.py`
- `src/render/persistence/tables.py`
- `src/render/persistence/outbox.py`
- `src/render/persistence/unit_of_work.py`
- `tests/integration/persistence/f/test_persist_f_postgres.py`
- `docs/delivery-evidence/persist-f/report.md`

## Quyết định thiết kế và mục mở

1. `workspace_id` lấy từ tham số keyword của `PostgresRenderUnitOfWork` (port không có `workspace_id`), một UoW gắn một workspace; composition root cần dựng UoW theo workspace (mục mở cho gói hội tụ).
2. migration 0017 không có bảng trace nên traces ghi vào `controlplane.cp_audit_records` (audit_id 'render-trace:<12 chữ số>', toàn bộ trường trace trong `redacted_reason`, cột `outcome` ánh xạ `succeeded`/`failed`); đề xuất mục mở: thêm bảng trace riêng ở migration sau (không sửa migration trong slice này).
3. `cp_render_operation_receipts` không có cột command/receipt_ref/state/package: `idempotency_key = 'command:operation_key'`, `aggregate_ref` chứa JSON `{receipt_ref, state, render_package_id, package_fingerprint, report_id}`, `aggregate_revision = revision`.
4. `attempt_index` suy ra từ `cp_render_attempts` (revision 1, `payload.package_fingerprint`), không có bảng riêng.
5. package revision >= 2 cùng fingerprint được phép (unique index chỉ phủ revision 1; bản in-memory raise `DuplicateRecordError` ở trường hợp này, đây là khác biệt có chủ đích, đổi fingerprint vẫn là `ImmutableFieldError`); unique `package_fingerprint` và `render_attempt_id` là toàn cục theo migration.
6. `output_artifact_ref` duy nhất nhờ khóa chính `cp_video_outputs`, ghi đúng một hàng ở revision 1 của attempt.
7. quality report tách header (`cp_quality_reports`) và 13 gate (`cp_quality_gate_results`), đọc bằng JOIN.
8. `cp_render_preset_revisions` không dùng vì port chỉ có ba kind.
9. đọc ngoài khối with mượn kết nối đọc ngắn (`RenderPipeline.require_renderable` và `reconcile_render` đọc ngoài with); ghi bắt buộc UoW active.
10. Chưa ghi user checkpoint M2.

## RED trước implementation

Chứng kiến RED hợp lệ tại Bước 10 trên PostgreSQL 18.6 trước khi cài đặt adapter, hoàn toàn bằng `AssertionError`, `DID NOT RAISE` và `AttributeError` do các hàm stub no-op gây ra; không có lỗi import, lỗi cú pháp hay lỗi setup/fixture:
- Lệnh: `python -m pytest tests/integration/persistence/f/test_persist_f_postgres.py -q -p no:cacheprovider`
- Tóm tắt: `18 failed, 2 passed in 9.04s` (exit code 1)
- Danh sách test fail:
  - `FAILED tests/integration/persistence/f/test_persist_f_postgres.py::test_package_round_trip_and_reads_outside_uow` (AssertionError: assert None == StoredRecord(...))
  - `FAILED tests/integration/persistence/f/test_package_revision_two_keeps_history` (AssertionError: assert 0 == 2)
  - `FAILED tests/integration/persistence/f/test_package_input_validation` (Failed: DID NOT RAISE ValueError)
  - `FAILED tests/integration/persistence/f/test_package_fingerprint_unique_and_immutable` (Failed: DID NOT RAISE DuplicateRecordError)
  - `FAILED tests/integration/persistence/f/test_attempt_round_trip_through_states` (AttributeError: 'NoneType' object has no attribute 'record')
  - `FAILED tests/integration/persistence/f/test_attempt_key_and_uniques` (Failed: DID NOT RAISE ValueError)
  - `FAILED tests/integration/persistence/f/test_attempt_identity_fields_are_immutable` (Failed: DID NOT RAISE ImmutableFieldError)
  - `FAILED tests/integration/persistence/f/test_video_output_row_written_once_per_attempt` (AssertionError: assert 0 == 1)
  - `FAILED tests/integration/persistence/f/test_quality_report_round_trip` (AttributeError: 'NoneType' object has no attribute 'record')
  - `FAILED tests/integration/persistence/f/test_validation_reports_are_append_only_by_fingerprint` (AssertionError: assert None == 1)
  - `FAILED tests/integration/persistence/f/test_receipts_round_trip_and_unique` (Failed: DID NOT RAISE DuplicateRecordError)
  - `FAILED tests/integration/persistence/f/test_traces_get_a_sequence_and_persist` (AssertionError: assert 0 == 2)
  - `FAILED tests/integration/persistence/f/test_attempt_index_lists_attempt_ids_by_package_fingerprint` (AssertionError: assert () == ('attempt-1', 'attempt-2'))
  - `FAILED tests/integration/persistence/f/test_history_tables_reject_update_and_delete` (AssertionError: cp_render_packages should have rows, assert 0 > 0)
  - `FAILED tests/integration/persistence/f/test_record_and_outbox_commit_together` (AssertionError: assert 0 == 1)
  - `FAILED tests/integration/persistence/f/test_exception_and_missing_commit_roll_back_everything` (AssertionError: assert 0 == 1)
  - `FAILED tests/integration/persistence/f/test_unit_of_work_uses_one_connection` (AssertionError: assert None is not None)
  - `FAILED tests/integration/persistence/f/test_unit_of_work_lifecycle` (Failed: DID NOT RAISE UnitOfWorkNotActiveError)

## GREEN sau implementation

Sau khi hoàn tất cài đặt các module trong `src/render/persistence`, toàn bộ 20 test tích hợp chạy trên PostgreSQL 18.6 với cơ sở dữ liệu tạm riêng biệt cho từng bài test đều đạt tuyệt đối:
- Lệnh: `python -m pytest tests/integration/persistence/f/test_persist_f_postgres.py -q -p no:cacheprovider`
- Tóm tắt: `20 passed in 10.11s` (exit code 0)

## Lệnh đã chạy

| Bước | Lệnh | Exit code | Kết quả |
| --- | --- | --- | --- |
| 10 | `python -m pytest tests/integration/persistence/f/test_persist_f_postgres.py -q -p no:cacheprovider` | 1 | 18 failed, 2 passed in 9.04s (AssertionError, DID NOT RAISE, AttributeError do stub) |
| 20 | `python -m pytest tests/integration/persistence/f/test_persist_f_postgres.py -q -p no:cacheprovider` | 0 | 20 passed in 10.11s (toàn bộ 20 test đạt) |
| 22 | `git diff --check` | 0 | Không có khoảng trắng thừa hoặc lỗi diff |
| 23 | `python -m pytest tests/integration/persistence/f/test_persist_f_postgres.py -q -p no:cacheprovider` | 0 | 20 passed in 10.11s (GREEN xác nhận lần cuối) |
| 24 | `python -c "import pathlib; fs = list(pathlib.Path('src/render/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert fs and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and 'from src.' not in t, 'adapter F'"` | 0 | Probe đạt: không có DDL, không có 'from src.' |
