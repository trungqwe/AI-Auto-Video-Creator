# Báo cáo chuyển giao: PERSIST-B

## 1. Trạng thái
- Trạng thái: IMPLEMENTED, GREEN.
- Integration head đã rebase: `836de0d664d3bcbc2dc5ff53013cb8b9c5a94cf0`.
- Ghi nhận dependency: Trạng thái BLOCKED DEPENDENCY_GAP trước đây (cột `dedup_policy_revision` là BIGINT) đã được giải quyết triệt để bởi gói tích hợp `CP-3-MIGRATIONS-FIX1`. Cả hai bảng `cp_collected_document_resolutions` và `cp_dedup_evidence` hiện đều có cột `dedup_policy_revision TEXT`. Đủ cả 8 bảng và các ràng buộc, trigger theo migration 0013.

## 2. Lệnh kiểm RED và kết quả ban đầu
- Lệnh kiểm: `python -m pytest tests/integration/persistence/b/test_persist_b_postgres.py -q -p no:cacheprovider`
- Exit code: 1 (RED hợp lệ do assertion đúng oracle trước khi cài adapter)
- Đoạn output thật (đã ẩn DSN):

```text
..FFFFFFFFFFFF                                                           [100%]
================================== FAILURES ===================================
_________ test_unit_of_work_exposes_expected_repositories_and_outbox __________

manager = <controlplane.infrastructure.db.uow.TransactionManager object at 0x000002B7B0DB4C20>
workspace_id = '699eddc5-1fd6-4191-9e7d-64cf7e381c40'

    def test_unit_of_work_exposes_expected_repositories_and_outbox(manager: TransactionManager, workspace_id: str) -> None:
>       uow = new_uow(manager, workspace_id)

tests/integration/persistence/b/test_persist_b_postgres.py:185:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

manager = <controlplane.infrastructure.db.uow.TransactionManager object at 0x000002B7B0DB4C20>
workspace_id = '699eddc5-1fd6-4191-9e7d-64cf7e381c40'

    def new_uow(manager: TransactionManager, workspace_id: str) -> UnitOfWork:
>       assert hasattr(persistence, 'PostgresIngestionUnitOfWork'), 'ingestion.persistence must export PostgresIngestionUnitOfWork'
E       AssertionError: ingestion.persistence must export PostgresIngestionUnitOfWork
E       assert False
E        +  where False = hasattr(persistence, 'PostgresIngestionUnitOfWork')

tests/integration/persistence/b/test_persist_b_postgres.py:93: AssertionError
...
=========================== short test summary info ===========================
FAILED tests/integration/persistence/b/test_persist_b_postgres.py::test_unit_of_work_exposes_expected_repositories_and_outbox
FAILED tests/integration/persistence/b/test_persist_b_postgres.py::test_article_round_trip_and_lookups
FAILED tests/integration/persistence/b/test_persist_b_postgres.py::test_resolution_round_trip_and_unique_key
FAILED tests/integration/persistence/b/test_persist_b_postgres.py::test_event_round_trip
FAILED tests/integration/persistence/b/test_persist_b_postgres.py::test_record_kinds_map_to_four_tables
FAILED tests/integration/persistence/b/test_persist_b_postgres.py::test_article_and_outbox_commit_together
FAILED tests/integration/persistence/b/test_persist_b_postgres.py::test_outbox_deduplication_id_is_idempotent
FAILED tests/integration/persistence/b/test_persist_b_postgres.py::test_error_after_aggregate_write_rolls_back_aggregate_and_outbox
FAILED tests/integration/persistence/b/test_persist_b_postgres.py::test_exit_without_commit_rolls_back
FAILED tests/integration/persistence/b/test_persist_b_postgres.py::test_unsafe_outbox_payload_rolls_back_aggregate
FAILED tests/integration/persistence/b/test_persist_b_postgres.py::test_append_only_tables_reject_update
FAILED tests/integration/persistence/b/test_persist_b_postgres.py::test_persistence_package_has_no_ddl_or_package_a_dependency
12 failed, 2 passed in 5.40s
```

## 3. Lệnh kiểm GREEN và kết quả sau khi cài adapter
- Lệnh kiểm: `python -m pytest tests/integration/persistence/b/test_persist_b_postgres.py -q -p no:cacheprovider`
- Exit code: 0
- Output thật:

```text
..............                                                           [100%]
14 passed in 6.14s
```

## 4. Kiểm tra probe tĩnh và định dạng diff
- Lệnh probe quét tệp mã nguồn adapter:
  `python -c "import pathlib; fs = list(pathlib.Path('src/ingestion/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert fs and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and 'from src.' not in t, 'adapter B'"`
  - Exit code: 0 (Đã quét 3 tệp, không phát hiện `CREATE TABLE`, `ALTER TABLE`, hoặc `from src.`).
- Lệnh kiểm tra định dạng diff:
  `git diff --check`
  - Exit code: 0 (Không có lỗi định dạng hay khoảng trắng thừa).

## 5. Ánh xạ cơ sở dữ liệu và ràng buộc nghiệp vụ
- Ánh xạ 8 bảng của migration `0013_ingestion`:
  - `PostgresArticleRepository`: lưu và tra cứu aggregate Article trong `controlplane.cp_articles` và lịch sử revisions trong `controlplane.cp_article_revisions`.
  - `PostgresResolutionRepository`: lưu mapping kết quả deduplication trong `controlplane.cp_collected_document_resolutions`.
  - `PostgresEventRepository`: lưu event nghiệp vụ trong `controlplane.cp_events`.
  - `PostgresRecordRepository`: ánh xạ 4 kind vào 4 bảng phụ trợ tương ứng.
- Ánh xạ 4 kind của RecordRepository:
  - `dedup_evidence`: bảng `controlplane.cp_dedup_evidence` (khóa `evidence_id`, cột `collected_document_id`, `dedup_policy_revision`).
  - `event_link_candidate`: bảng `controlplane.cp_event_link_candidates` (khóa `record_id`, hỗ trợ UPSERT).
  - `event_update`: bảng `controlplane.cp_event_updates` (khóa `record_id`, cột `event_id`).
  - `event_update_candidate`: bảng `controlplane.cp_event_update_candidates` (khóa `record_id`, hỗ trợ UPSERT).
  - Mọi kind khác (bao gồm các kind reserved hay kind lạ) đều bị từ chối bằng `UnknownRecordKindError` trước khi tương tác cơ sở dữ liệu.
- Ràng buộc unique resolution:
  - Khóa chính `(workspace_id, collected_document_id, dedup_policy_revision)` bảo đảm tính duy nhất tuyệt đối của resolution theo từng revision của policy.
- Bảng append-only:
  - Các bảng `cp_article_revisions`, `cp_dedup_evidence`, `cp_event_updates` được bảo vệ bởi trigger `cp_reject_ingestion_history_mutation` (từ chối mọi thao tác UPDATE hoặc DELETE với thông báo lỗi `append-only`).
  - Tại repository, ghi lại cùng khóa với payload khác bị từ chối bằng `ValueError`.
- Tính toàn vẹn giao dịch Unit of Work:
  - Aggregate và outbox được ghi trên cùng một kết nối duy nhất qua `manager.borrow_connection()`.
  - `commit()` xác nhận đồng thời cả aggregate và outbox; khi xảy ra ngoại lệ hoặc thoát khối `with` mà không commit, cả aggregate và outbox đều tự động rollback.

## 6. Mục theo dõi cho Control
- Kind phụ cần bổ sung bảng: Hiện tại use case có tham chiếu tới hai kind `article_media_attachment` (trong `src/ingestion/application/resolve_document.py:47`) và `activity_result` (trong `src/ingestion/application/activity_handler.py:30`). Migration 0013 hiện tại chưa có bảng cho hai kind này, nên `PostgresRecordRepository` từ chối chúng với `UnknownRecordKindError`. Cần bổ sung bảng tại migration tiếp theo trước khi thực hiện wiring cho hai luồng use case này.
- Ngữ cảnh Unit of Work: `PostgresIngestionUnitOfWork` nhận các tham số `workspace_id`, `correlation_id`, `actor` khi khởi tạo (do protocol UnitOfWork ở mức domain/ports không yêu cầu truyền `workspace_id` trong từng thao tác repo).

## 7. Phạm vi tệp đã sửa đổi
Các tệp đã sửa đổi đều nằm đúng trong owned paths:
- `src/ingestion/persistence/__init__.py`
- `src/ingestion/persistence/repositories.py`
- `src/ingestion/persistence/uow.py`
- `tests/integration/persistence/b/test_persist_b_postgres.py`
- `docs/delivery-evidence/persist-b/report.md`
