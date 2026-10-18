# Báo cáo bằng chứng B-3

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `91878d46206a05e052217b54e81af614b6ba1bf7`
- Nguồn quyền: IMPL-PLAN-B Auditor PASS; slice B-3 trong docs/implementation/b/slices.md; D3 user duyệt Phần B ngày 18/10/2026.
- Binding refs: `a-b-collected-document.json`, `domain-event-envelope.json`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/ingestion/test_ingestion_article_aggregate.py tests/unit/ingestion/test_ingestion_memory_unit_of_work.py -q -p no:cacheprovider`
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `8 failed, 11 passed in 0.13s`
- Danh sách test FAILED kèm thông điệp nguyên văn:
  - `FAILED tests/unit/ingestion/test_ingestion_article_aggregate.py::test_with_revision_returns_new_article_and_keeps_old_revision`: `AssertionError: assert Article(...) is not Article(...)`
  - `FAILED tests/unit/ingestion/test_ingestion_article_aggregate.py::test_revision_number_must_increase_by_one`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/ingestion/test_ingestion_article_aggregate.py::test_revision_of_other_article_or_duplicate_id_is_rejected`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/ingestion/test_ingestion_article_aggregate.py::test_revision_copies_mutable_inputs`: `AssertionError: assert 'tampered' == 'final_fetch'`
  - `FAILED tests/unit/ingestion/test_ingestion_memory_unit_of_work.py::test_commit_persists_aggregate_and_outbox_together`: `AssertionError: assert () == (Article(...),)`
  - `FAILED tests/unit/ingestion/test_ingestion_memory_unit_of_work.py::test_duplicate_deduplication_id_is_written_once`: `AssertionError: assert 'evt-2' == 'evt-1'`
  - `FAILED tests/unit/ingestion/test_ingestion_memory_unit_of_work.py::test_stored_revisions_cannot_be_rewritten`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/ingestion/test_ingestion_memory_unit_of_work.py::test_records_are_stored_by_kind`: `AssertionError: assert [] == [{'collected_document_id': 'doc-1'}]`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection; 11 test pass trên skeleton và 8 test fail đúng oracle (AssertionError hoặc `Failed: DID NOT RAISE`).

## Thay đổi

- `src/ingestion/domain/article.py`: Aggregate `Article` và value object `ArticleRevision` cho bounded context ingestion (module B) tuân thủ CT-CNT-003:
  - `ArticleRevision`: Dataclass frozen, kw_only với đúng 24 trường dữ liệu, không có default; `__post_init__` sao chép nông `provenance_chain` thành tuple các `MappingProxyType`, `media_discovery_refs` và `uncertain_fields` thành tuple không đổi.
  - `Article`: Dataclass frozen, kw_only quản lý `article_id`, `identity_key`, `representative_source_id`, `revisions`. `__post_init__` kiểm tra tính liên tục của `revision_number` (1..n, từ chối bool), kiểm tra khớp `article_id` và từ chối `article_revision_id` trùng lặp. Phương thức `with_revision` trả về thực thể `Article` mới thông qua `dataclasses.replace` bảo toàn tính bất biến của các revision cũ.
- `src/ingestion/application/ports.py`: Định nghĩa các Protocol runtime_checkable phân tách ranh giới cổng cho module B theo D8-B-13:
  - `ArticleRepository`: get, find_by_identity_key, find_by_exact_fingerprint, list_all, save.
  - `ResolutionRepository`: get, list_all, save keyed bởi `(collected_document_id, dedup_policy_revision)`.
  - `EventRepository`: get, list_all, save theo `event_id`.
  - `RecordRepository`: put, get, list cho các bản ghi bổ trợ theo `kind`.
  - `SourceTierLookup`: tra cứu tier theo `source_id`.
  - `OutboxWriter`: phương thức `append_event` tương thích chữ ký với controlplane outbox writer.
  - `UnitOfWork`: context manager quản lý transaction theo collected document, hỗ trợ `commit` và `rollback`.
- `src/ingestion/infrastructure/memory.py`: Bộ adapter in-memory phục vụ kiểm thử và xử lý không phụ thuộc cơ sở dữ liệu:
  - `InMemoryUnitOfWork`: Phân tách vùng staged và committed; commit ghi đồng thời aggregate và outbox event; rollback huỷ toàn bộ stage; deduplication trong `append_event` trả về `event_id` cũ khi trùng `deduplication_id`.
  - `_ArticleRepository`, `_ResolutionRepository`, `_EventRepository`, `_RecordRepository`, `_OutboxWriter`: Các adapter nội bộ uow.
  - `InMemorySourceTierLookup`: Adapter tra cứu tier từ map, ném `LookupError` khi không tìm thấy nguồn.
- `tests/unit/ingestion/test_ingestion_article_aggregate.py`: 7 hàm test (9 test cases) bao quát đặc tính bất biến, cấu trúc trường CT-CNT-003, tăng revision, từ chối dữ liệu sai.
- `tests/unit/ingestion/test_ingestion_memory_unit_of_work.py`: 8 hàm test (10 test cases) bao quát kiểm tra Protocol runtime conformance, tính nguyên tử của commit, hủy stage khi lỗi hoặc thoát, outbox deduplication, ghi đè revision bị chặn, lưu trữ phụ trợ theo kind.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/ingestion/test_ingestion_article_aggregate.py tests/unit/ingestion/test_ingestion_memory_unit_of_work.py -q -p no:cacheprovider` | 0 | 19 passed in 0.04s |
| 2 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 35 passed in 0.05s (test_ingestion_import_boundary PASS) |
| 3 | `git diff --check` | 0 | không có output |

## Quyết định mặc định (D8)

1. `ArticleRevision` khai báo `kw_only=True`, không có giá trị mặc định nên thiếu bất kỳ trường nào đều ném `TypeError`; trường `title` rỗng do B-6 truyền khi thiếu dữ liệu nguồn.
2. `revision_number` bắt đầu từ 1, tăng đúng 1 qua mỗi revision, được kiểm tra nghiêm ngặt trong `Article.__post_init__` và từ chối kiểu `bool` (`isinstance(bool, int)` trong Python).
3. `provenance_chain` được sao chép nông thành tuple của `MappingProxyType`; `media_discovery_refs` và `uncertain_fields` thành tuple; do chứa `MappingProxyType`, `ArticleRevision` không hash được (`unsafe_hash=False` mặc định).
4. `published_at_confidence` là chuỗi tự do do B-6 gán — GIẢ ĐỊNH, enum chờ REQ-B-CONV-07.
5. Completeness flags gồm `is_complete` và `uncertain_fields` theo quy chuẩn CT-CNT-006.
6. Unit of work: Chỉ cho phép ghi trong ngữ cảnh `with uow:`, cho phép đọc cả ngoài transaction; ngoại lệ hoặc thoát khỏi context mà chưa commit sẽ loại bỏ toàn bộ staged writes; `commit` áp dụng đồng thời trạng thái aggregate và outbox records.
7. `deduplication_id` trùng (đã commit hoặc đang staged) trả về `event_id` cũ và không ghi thêm bản ghi mới.
8. Bổ sung `RecordRepository` cho các bản ghi phụ theo loại (`dedup_evidence`, `event_link_candidate`, `event_update`, `event_update_candidate`) để B-6..B-8 không cần sửa lại `ports.py`; ba loại `article`, `collected_document_resolution`, `event` sử dụng repository chuyên biệt.
9. `ResolutionRepository` khóa theo cặp `(collected_document_id, dedup_policy_revision)`; `save` ghi đè trong transaction, tính idempotency do caller B-6 kiểm tra bằng `get`.
10. Protocol `OutboxWriter` có cùng chữ ký với `IOutboxWriter.append_event`, không import phụ thuộc `controlplane`; việc kết nối tới outbox database thật thuộc REQ-B-CONV-02.
11. `InMemorySourceTierLookup`: nguồn lạ không có trong map ném `LookupError`.
12. Không bổ sung thêm thư viện ngoài, chỉ sử dụng Python standard library (`collections.abc`, `dataclasses`, `types`, `typing`, `uuid`).

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- EG-M3-7

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Kiểm tra CHECK-B dạng `python -c` không chạy vì Control không cấp quyền, thay thế đầy đủ bằng `test_ingestion_import_boundary` trong `test_ingestion_package_validation.py`.
- Không sửa `HANDOFF.md`, `README.md`, `CHANGELOG.md` hay tệp ngoài owned paths.
- Không gọi dịch vụ mạng thật hay đọc bí mật.
