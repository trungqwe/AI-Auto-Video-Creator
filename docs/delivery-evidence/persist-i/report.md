# Báo cáo PERSIST-I

## Tệp đã sửa/tạo

- `src/controlplane/infrastructure/db/storage_meta/records.py`
- `src/controlplane/infrastructure/db/storage_meta/catalog.py`
- `src/controlplane/infrastructure/db/storage_meta/__init__.py`
- `tests/integration/persistence/i/test_persist_i_postgres.py`
- `docs/delivery-evidence/persist-i/report.md`

## Quyết định thiết kế và mục mở

1. `workspace_id` được nhận qua tham số constructor tùy chọn `workspace_id: str | None = None` của `PostgresStorageMetaRepository` và truy xuất qua helper `_scope()` vì `UploadReceiptPort` cùng các bảng lease, placement, working set policy yêu cầu phạm vi workspace nhưng chữ ký của port không mang `workspace_id`. Tám phương thức hiện có (`find_version`, `insert_version`, `get_version`, `insert_location`, `get_location`, `update_location`, `insert_authorization`, `authorize_location`) giữ nguyên chữ ký và vẫn nhận `workspace_id` qua tham số, đảm bảo tương thích ngược hoàn toàn.
2. `ArtifactVersionCatalogPort` được cài đặt ở lớp `PostgresArtifactVersionCatalog` riêng biệt trong `catalog.py` vì phương thức `insert_version` của nó trùng tên với `StorageMetaRepository.insert_version` nhưng khác chữ ký (một bên nhận request object `DeclareArtifactVersionRequest`, một bên nhận `values: dict[str, Any]`), một lớp không thể cài đặt đồng thời cả hai mà không gây xung đột chữ ký — đây là mục mở cho gói hội tụ khi nối composition root.
3. Bảng `cp_upload_receipts` không có cột lưu `content_sha256` và `size_bytes`, do đó adapter lấy thông tin này bằng cách JOIN với bảng `cp_artifact_versions` trong `get()`, và trong `save()` adapter chủ động kiểm tra tính khớp giữa receipt và version tương ứng; `target_backend_ref` được đặt mặc định là `'cloud'` thông qua tham số constructor `upload_backend_ref`.
4. Ánh xạ trạng thái upload receipt đảm bảo không làm mất hành vi nghiệp vụ: `CORRUPT` và `MISSING` được lưu vào cơ sở dữ liệu thành `'FAILED'` (do ràng buộc CHECK của bảng không có hai giá trị này), khi đọc ngược lại `'FAILED'` được ánh xạ thành `CORRUPT`; `UPLOADING` và `UPLOADED_UNVERIFIED` khi đọc ngược lại được ánh xạ thành `PREPARED` — mục mở: hợp đồng có thể bổ sung các trạng thái chi tiết hơn nếu cần.
5. Các dataclass domain `ArtifactVersion`, `ArtifactLocation` không có các trường mở rộng của migration 0010 và `CleanupAuthorization.recovery_epoch` được khai báo kiểu `int`; do tầng domain không thuộc owned paths của gói này nên các trường mở rộng được đọc qua read models tại `records.py` (`ArtifactVersionExtension`, `ArtifactLocationFields`) và adapter trả `recovery_epoch` dưới dạng `str` — mục mở cho chủ sở hữu gói domain cập nhật định nghĩa khi thích hợp.
6. `WorkingSetPolicy.policy_revision` (kiểu `str`) ánh xạ vào cột `BIGINT` trong bảng `cp_working_set_policies` và chỉ chấp nhận chuỗi số nguyên dương; nếu cột `max_working_set_bytes` có giá trị `NULL` thì ném `ValueError` khi đọc; chính sách working set policy là append-only, nếu `policy_revision` đã tồn tại thì `insert_working_set_policy` trả về `False` thay vì ghi đè.
7. Trường `last_verified_at` của `cp_artifact_locations` được tự động gán bằng `CURRENT_TIMESTAMP` khi thực hiện `update_location` chuyển trạng thái sang `VERIFIED`.
8. `CloudObjectPort` không có adapter PostgreSQL; kiểm thử quét mã nguồn đã xác minh adapter không chứa triển khai lưu trữ object cloud.
9. `CleanupAuthorizationStore.authorize` so sánh `recovery_epoch` bằng toán tử `!=` thô nên caller phải truyền cùng kiểu dữ liệu cho `recovery_epoch` và `current_recovery_epoch` — mục mở cho gói application; chưa ghi user checkpoint M2.

## RED trước implementation

Chứng kiến RED hợp lệ tại Bước 15 trên PostgreSQL 18.6 trước khi cài đặt adapter, hoàn toàn bằng `AssertionError` do các hàm stub gây ra; không có lỗi import, lỗi cú pháp hay lỗi setup/fixture:
- Lệnh: `python -m pytest tests/integration/persistence/i/test_persist_i_postgres.py -q -p no:cacheprovider`
- Tóm tắt: `11 failed, 5 passed in 5.87s` (exit code 1)
- Danh sách test fail:
  - `FAILED tests/integration/persistence/i/test_persist_i_postgres.py::test_version_round_trip_with_extension_columns` (AssertionError: assert None == ArtifactVersionExtension(...))
  - `FAILED tests/integration/persistence/i/test_persist_i_postgres.py::test_catalog_declare_is_idempotent_and_workspace_scoped` (AssertionError: assert (False is True) where False = DeclareArtifactVersionResult(...).matched_existing)
  - `FAILED tests/integration/persistence/i/test_persist_i_postgres.py::test_cleanup_authorization_recovery_epoch_is_text` (AssertionError: assert 7 == '007')
  - `FAILED tests/integration/persistence/i/test_persist_i_postgres.py::test_location_ct_sto_002_fields_round_trip` (AssertionError: assert (None is not None))
  - `FAILED tests/integration/persistence/i/test_persist_i_postgres.py::test_upload_receipt_round_trip_and_outcome_unknown` (AssertionError: assert None == UploadReceipt(...))
  - `FAILED tests/integration/persistence/i/test_persist_i_postgres.py::test_upload_receipt_unique_per_operation_key_and_bound_to_version` (AssertionError: assert 0 == 1 where 0 = count(..., 'cp_upload_receipts'))
  - `FAILED tests/integration/persistence/i/test_persist_i_postgres.py::test_persist_to_cloud_outcome_unknown_then_reconcile_after_restart` (AssertionError: assert (None is not None))
  - `FAILED tests/integration/persistence/i/test_persist_i_postgres.py::test_materialization_lease_round_trip_and_idempotent_per_operation` (AssertionError: assert (None is not None))
  - `FAILED tests/integration/persistence/i/test_persist_i_postgres.py::test_revision_placement_round_trip_and_idempotent` (AssertionError: assert None == RevisionPlacement(...))
  - `FAILED tests/integration/persistence/i/test_persist_i_postgres.py::test_working_set_policy_round_trip_and_latest_revision` (AssertionError: assert False is True)
  - `FAILED tests/integration/persistence/i/test_persist_i_postgres.py::test_declare_and_outbox_roll_back_together` (AssertionError: assert (0 == 1))

## GREEN sau implementation

Sau khi hoàn tất cài đặt các module trong `src/controlplane/infrastructure/db/storage_meta`, toàn bộ 16 test tích hợp chạy trên PostgreSQL 18.6 với cơ sở dữ liệu tạm riêng biệt cho từng bài test đều đạt tuyệt đối:
- Lệnh: `python -m pytest tests/integration/persistence/i/test_persist_i_postgres.py -q -p no:cacheprovider`
- Tóm tắt: `16 passed in 6.08s` (exit code 0)

## Lệnh đã chạy

| Bước | Lệnh | Exit code | Kết quả |
| --- | --- | --- | --- |
| 15 | `python -m pytest tests/integration/persistence/i/test_persist_i_postgres.py -q -p no:cacheprovider` | 1 | 11 failed, 5 passed in 5.87s (toàn bộ fail do AssertionError từ stub) |
| 24 | `python -m pytest tests/integration/persistence/i/test_persist_i_postgres.py -q -p no:cacheprovider` | 0 | 16 passed in 6.08s (toàn bộ 16 test đạt tuyệt đối) |
| 25 | `python -m pytest tests/m2/test_p5b_artifact_metadata.py -q` | 0 | 5 passed in 2.38s (hồi quy P5B đạt) |
| 26 | `git diff --check` | 0 | Không có khoảng trắng thừa hoặc lỗi diff |
| 27 | `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/storage_meta'); t = ' '.join(f.read_text(encoding='utf-8') for f in d.rglob('*.py')); assert 'CREATE TABLE' not in t and 'ALTER TABLE' not in t, 'adapter I'"` | 0 | Probe đạt: không có DDL trong storage_meta |
