# Bằng chứng PERSIST-A — adapter PostgreSQL của nguồn thu thập

## Phạm vi

Các tệp thuộc owned paths đã tạo và chỉnh sửa:
- `src/source_ingestion/persistence/__init__.py`
- `src/source_ingestion/persistence/repositories.py`
- `src/source_ingestion/persistence/outbox.py`
- `src/source_ingestion/persistence/unit_of_work.py`
- `src/source_ingestion/persistence/_sql.py`
- `src/source_ingestion/persistence/_codec.py`
- `tests/integration/persistence/a/test_persist_a_postgres.py`
- `docs/delivery-evidence/persist-a/report.md`

Không sửa migration, composition root, api/wiring, lockfile, tests/m2, adapter in-memory (`src/source_ingestion/adapters/memory.py`); không thêm thư viện bên ngoài.

## RED

Lệnh kiểm thử đã chạy:
```bash
python -m pytest tests/integration/persistence/a/test_persist_a_postgres.py -q -p no:cacheprovider
```

Kết quả:
- Exit code: 1
- Tổng số test: 22 (18 FAILED, 4 PASSED)
- RED được chứng kiến hoàn toàn do assertion failures và DID NOT RAISE trên bộ khung kho no-op (không phải ImportError, thiếu migration, hay thiếu binary):
  1. `test_source_round_trip`: FAILED (AssertionError: `assert None == Source(...)`)
  2. `test_candidate_round_trip`: FAILED (AssertionError: `assert None == SourceCandidate(...)`)
  3. `test_run_round_trip_with_attempts`: FAILED (AssertionError: `assert None == CollectionRun(...)`)
  4. `test_package_round_trip`: FAILED (AssertionError: `assert None == PackageRecord(...)`)
  5. `test_checkpoint_round_trip`: FAILED (AssertionError: `assert None == CollectionCheckpoint(...)`)
  6. `test_receipt_round_trip`: FAILED (AssertionError: `assert None == CommandReceipt(...)`)
  7. `test_tombstone_blocks_reregistration`: FAILED (AssertionError: `assert <IdentityMatchKind.NONE: 'NONE'> is <IdentityMatchKind.TOMBSTONE: 'TOMBSTONE'>`)
  8. `test_periodic_run_unique`: FAILED (Failed: `DID NOT RAISE DuplicatePeriodicRunError`)
  9. `test_package_unique`: FAILED (Failed: `DID NOT RAISE DuplicatePackageError`)
  10. `test_receipt_unique`: FAILED (Failed: `DID NOT RAISE DuplicateReceiptError`)
  11. `test_append_only_tables_reject_update_delete`: FAILED (Failed: `DID NOT RAISE RaiseException`)
  12. `test_checkpoint_advance_only_over_durable_items`: FAILED (Failed: `DID NOT RAISE CheckpointRejected`)
  13. `test_uow_commit_persists_aggregate_and_outbox_together`: FAILED (AssertionError: `assert 0 == 1`)
  14. `test_outbox_deduplication_id_keeps_one_row`: FAILED (AssertionError: `assert '' == '9c9888aa-0340-5841-85cb-8dacadfb1d38'`)
  15. `test_outbox_unsafe_payload_aborts_aggregate`: FAILED (Failed: `DID NOT RAISE ValueError`)
  16. `test_outbox_workspace_and_recovery_epoch`: FAILED (Failed: `DID NOT RAISE ValueError`)
  17. `test_uow_borrows_exactly_one_connection`: FAILED (AssertionError: `assert 0 == 1`)
  18. `test_uow_not_active_and_not_reentrant`: FAILED (Failed: `DID NOT RAISE UnitOfWorkNotActiveError`)

## GREEN

Số vòng chạy tới xanh: 1 vòng duy nhất (tất cả 22 test đều pass ngay lần đầu thực thi implementation thật).

Danh sách ba lệnh bắt buộc và kết quả thực thi:

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `git diff --check` | 0 | Không có cảnh báo khoảng trắng thừa (whitespace clean). |
| `python -m pytest tests/integration/persistence/a/test_persist_a_postgres.py -q -p no:cacheprovider` | 0 | 22 passed in 9.20s (toàn bộ 22/22 test đạt). |
| `python -c "import pathlib; fs = list(pathlib.Path('src/source_ingestion/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert fs and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and 'from src.' not in t, 'adapter A'"` | 0 | Probe PASS: không chứa CREATE TABLE, ALTER TABLE, hay import tiền tố 'from src.'. |

## Quyết định và mục mở

1. `PackageRecord` và `CollectionCheckpoint` không mang `workspace_id` nên workspace được lấy từ collection run qua `run_id` (run phải tồn tại trong cùng giao dịch; nếu thiếu run thì ném `RecordNotFoundError`).
2. Mỗi package được ghi thêm một dòng vào bảng `cp_fetch_observations` trong cùng savepoint, không chép nội dung văn bản sang bảng quan sát.
3. `PostgresSourceIngestionUnitOfWork(manager, *, workspace_id=None, correlation_id=None, actor='source_ingestion')`: workspace của outbox được lấy từ payload hoặc ngữ cảnh UoW; sự kiện `CollectedDocumentAvailable` không có `workspace_id` trong payload nên wiring phải truyền `workspace_id` khi tạo UoW (thuộc phạm vi của `CP-4-WIRING`).
4. Cột `cp_outbox_events.schema_version` có kiểu dữ liệu `INTEGER` nên ghi giá trị số `1`, chuỗi `'1.0.0'` của envelope được đặt trong cột `payload`.
5. `recovery_epoch` được ghi số khi chuỗi biểu diễn toàn chữ số thập phân, ngược lại là `NULL` để tránh lỗi commit (theo quyết định OI-PERSIST-03).
6. Thao tác `rollback()` luôn được thực thi khi thoát khỏi khối `with`, không bao giờ tự động commit.
7. Việc đồng bộ `README.md`, `CHANGELOG.md`, `HANDOFF.md` nằm ngoài phạm vi owned paths nên Worker không sửa, để dành cho Control/AI PM đồng bộ ở bước nghiệm thu.
