# Báo cáo PERSIST-C

## Tệp đã sửa/tạo

- `src/catalog/persistence/__init__.py`
- `src/catalog/persistence/_db.py`
- `src/catalog/persistence/mapping.py`
- `src/catalog/persistence/assets.py`
- `src/catalog/persistence/renditions.py`
- `src/catalog/persistence/hooks.py`
- `src/catalog/persistence/usage.py`
- `tests/integration/persistence/c/test_persist_c_postgres.py`
- `docs/delivery-evidence/persist-c/report.md`

## Quyết định thiết kế và mục mở

1. Mọi kho adapter (`PostgresMediaAssetRepository`, `PostgresRenditionStore`, `PostgresHookHistory`, `PostgresMediaUsageRepository`) nhận `(connection, workspace_id)` vì mọi bảng trong migration `0014_catalog` có cột `workspace_id NOT NULL`. Kết nối do caller sở hữu; adapter không tự mở kết nối, không commit, không rollback.
2. Cột `cp_media_assets.fingerprint` là `NOT NULL` trong khi domain cho phép `fingerprint` là `None` (khi tài sản mới được khám phá nhưng chưa acquire). Vì vậy sử dụng placeholder `pending:<media_asset_id>` cho tài sản chưa acquire, ghi nhãn GIẢ ĐỊNH theo mặc định đơn giản D8, không sửa migration; khi fingerprint đã được thiết lập thì không thể sửa đổi hoặc xóa (bất biến).
3. Cột `discovery_id` lưu giá trị khám phá mới nhất, đồng thời `payload.discovery_ids` lưu toàn bộ danh sách định danh khám phá theo thời gian, giúp phương thức `find_by_discovery_id` tra cứu được cả định danh cũ và mới.
4. Bảng `cp_media_provenance` lưu vết xuất xứ dạng append-only với `provenance_id` là mã băm SHA-256 xác định từ nội dung, thứ tự xuất xứ lưu trong `payload.seq`.
5. Thuộc tính `transformation_spec_revision` trong domain là kiểu `str` nhưng cột cơ sở dữ liệu là `BIGINT`, do đó adapter xác thực chuỗi số thập phân chuẩn (`0|[1-9][0-9]*`) trước khi chuyển đổi sang số nguyên.
6. Cột `status` của tài sản mang giá trị `DISCOVERED` khi chưa có fingerprint và `CATALOGED` sau khi đã gán fingerprint.
7. Tìm kiếm toàn văn (FTS): Cột `search_text` chứa các từ chữ-số viết thường không trùng lặp; câu truy vấn sử dụng toán tử mảng `string_to_array(search_text, ' ') @> text[]` khớp với chỉ mục GIN `cp_media_assets_fts_idx` và `cp_hooks_fts_idx`, đã được kiểm chứng bằng `EXPLAIN` trong test tích hợp; không sử dụng pgvector.
8. `PostgresHookHistory` cung cấp đầy đủ các phương thức `get(hook_id, revision)`, `latest(hook_id)`, `append(revision)` khớp hoàn toàn chữ ký của `HookHistory` trong domain/application (và bổ sung `search`), cho phép `import_hook` và `update_hook_metadata` chạy trực tiếp mà không cần sửa `src/catalog/application`.
9. Hỗ trợ `CP-5-COMPLETION`: Hàm `media_usage_repository_factory(workspace_id)` mượn trực tiếp thuộc tính `uow.connection` của completion unit of work, đảm bảo `MediaUsageRecorder.record_production_usage` thực thi cùng giao dịch completion mà không mở kết nối thứ hai.
10. Chưa ghi user checkpoint M2.

## RED trước implementation

Chứng kiến RED hợp lệ tại Bước 13 trên PostgreSQL 18.6 trước khi cài đặt adapter, hoàn toàn bằng `AssertionError` do các hàm stub no-op gây ra; không có lỗi import, lỗi cú pháp hay lỗi setup/fixture:
- Lệnh: `python -m pytest tests/integration/persistence/c/test_persist_c_postgres.py -q -p no:cacheprovider`
- Tóm tắt: `11 failed, 3 passed in 4.88s` (exit code 1)
- Danh sách test fail:
  - `FAILED tests/integration/persistence/c/test_persist_c_postgres.py::test_asset_round_trip_and_lookups` (AssertionError: assert None == MediaAsset(...))
  - `FAILED tests/integration/persistence/c/test_persist_c_postgres.py::test_fingerprint_is_set_once` (AssertionError: assert None == MediaAsset(...))
  - `FAILED tests/integration/persistence/c/test_persist_c_postgres.py::test_provenance_is_append_only_and_discovery_ids_accumulate` (AssertionError: assert None == MediaAsset(...))
  - `FAILED tests/integration/persistence/c/test_persist_c_postgres.py::test_fts_search_returns_only_matching_assets` (AssertionError: assert [] == [MediaAsset(...)])
  - `FAILED tests/integration/persistence/c/test_persist_c_postgres.py::test_workspaces_are_isolated` (AssertionError: assert None == MediaAsset(...))
  - `FAILED tests/integration/persistence/c/test_persist_c_postgres.py::test_renditions_round_trip_and_are_immutable` (AssertionError: assert RenditionSet(...) == RenditionSet(...))
  - `FAILED tests/integration/persistence/c/test_persist_c_postgres.py::test_hook_history_round_trip_and_matches_in_memory` (AssertionError: assert None == HookRevision(...))
  - `FAILED tests/integration/persistence/c/test_persist_c_postgres.py::test_hook_revisions_are_immutable_and_searchable` (AssertionError: assert [] == [HookRevision(...)])
  - `FAILED tests/integration/persistence/c/test_persist_c_postgres.py::test_usage_is_unique_and_replay_does_not_duplicate` (AssertionError: assert False is True)
  - `FAILED tests/integration/persistence/c/test_persist_c_postgres.py::test_only_production_rows_are_counted` (AssertionError: assert 0 == 2)
  - `FAILED tests/integration/persistence/c/test_persist_c_postgres.py::test_recorder_shares_the_completion_transaction` (AssertionError: assert 0 == 2)

## GREEN sau implementation

Sau khi hoàn tất cài đặt các module trong `src/catalog/persistence`, toàn bộ 14 test tích hợp chạy trên PostgreSQL 18.6 với cơ sở dữ liệu tạm riêng biệt cho từng bài test đều đạt tuyệt đối:
- Lệnh: `python -m pytest tests/integration/persistence/c/test_persist_c_postgres.py -q -p no:cacheprovider`
- Tóm tắt: `14 passed in 4.50s` (exit code 0)

## Lệnh đã chạy

| Bước | Lệnh | Exit code | Kết quả |
| --- | --- | --- | --- |
| 13 | `python -m pytest tests/integration/persistence/c/test_persist_c_postgres.py -q -p no:cacheprovider` | 1 | 11 failed, 3 passed in 4.88s (AssertionError do stub) |
| 23 | `python -m pytest tests/integration/persistence/c/test_persist_c_postgres.py -q -p no:cacheprovider` | 0 | 14 passed in 4.50s (toàn bộ 14 test đạt) |
| 24 | `python -m pytest tests/unit/catalog -q -p no:cacheprovider` | 0 | 194 passed, 463 subtests passed in 0.25s |
| 25 | `python -c "import pathlib; fs = list(pathlib.Path('src/catalog/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert fs and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and 'from src.' not in t, 'adapter C'"` | 0 | Probe đạt: không có DDL, không có 'from src.' |
| 26 | `git diff --check` | 0 | Không có khoảng trắng thừa hoặc lỗi diff |
