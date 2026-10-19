# Báo cáo bằng chứng B-10

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `2233e36f669f9ea4d8ffdd9b0724aa8c9fe19753`
- Nguồn quyền: IMPL-PLAN-B Auditor PASS; slice B-10 trong `docs/implementation/b/slices.md`; D3 user duyệt Phần B ngày 18/10/2026; Contract: CT-CNT-003, CT-CNT-006 (`docs/09-contracts/04-source-content-contracts.md`), D8-B-10 (`docs/implementation/b/plan.md`).

## RED

- Lệnh thực thi: `python -m pytest tests/unit/ingestion/test_ingestion_queries.py -q -p no:cacheprovider` (chạy trên skeleton của `queries.py`)
- Exit code thực tế: `1`
- Dòng tóm tắt nguyên văn: `47 failed, 8 passed in 0.35s`
- Chi tiết các test FAILED tiêu biểu kèm thông điệp nguyên văn:
  - `FAILED tests/unit/ingestion/test_ingestion_queries.py::test_trace_revision_returns_full_provenance - AssertionError: assert {'source_id':...d': None, ...} == {'source_id':...art-a-2', ...}`
  - `FAILED tests/unit/ingestion/test_ingestion_queries.py::test_unknown_revision_is_reported_not_hidden[art-missing-r1] - Failed: DID NOT RAISE LookupError`
  - `FAILED tests/unit/ingestion/test_ingestion_queries.py::test_search_without_filters_lists_every_revision_in_stable_order - AssertionError: assert [] == ['art-a-r1', ...', 'art-d-r1']`
  - `FAILED tests/unit/ingestion/test_ingestion_queries.py::test_invalid_filters_fail_closed[None] - Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/ingestion/test_ingestion_queries.py::test_count_new_articles_counts_distinct_new_article_by_utc_date - AssertionError: assert 0 == 2`
- Xác nhận: Hoàn toàn không có `ImportError`, `ModuleNotFoundError` hay lỗi collection; 8 test PASS trên skeleton là `test_query_constants_match_acceptance`, `test_search_filters_combine_with_and[filters10-expected10]`, `test_search_filters_combine_with_and[filters11-expected11]`, `test_count_new_articles_ignores_other_dispositions[NEW_REVISION]`, `test_count_new_articles_ignores_other_dispositions[DUPLICATE_MEDIA_ONLY]`, `test_count_new_articles_ignores_other_dispositions[DUPLICATE_NO_NEW_VALUE]`, `test_queries_never_write`, `test_queries_source_has_no_write_calls_or_forbidden_imports`; 47 test còn lại FAILED do `AssertionError` hoặc `Failed: DID NOT RAISE`.

## Thay đổi

- `src/ingestion/application/queries.py`:
  - Hằng số: `TRACE_FIELDS`, `SEARCH_FILTERS`, `NEW_ARTICLE`, `_FIELD_FILTERS`, `_BUSINESS_DATE_RE`.
  - Helper private: `_require_text`, `_fold`, `_is_missing`, `_business_date`.
  - Lớp `IngestionQueries`:
    - `__init__(uow)`: lưu UnitOfWork.
    - `_revisions()`: đọc toàn bộ revision từ `uow.articles.list_all()`, sắp xếp theo `(article_id, revision_number)`.
    - `_event_ids()`: ánh xạ `(article_id, article_revision_id)` sang tuple các `event_id` được sắp xếp từ `uow.events.list_all()`.
    - `trace_revision(article_revision_id)`: trả 9 trường truy vết CT-CNT-006, liệt kê trường thiếu trong `uncertain_fields`, đánh dấu `is_fully_traced`, trả bản sao `provenance_chain`, ném `ValueError` cho id không hợp lệ và `LookupError` cho revision không tồn tại.
    - `search(filters)`: lọc AND theo topic, source_id, event_id, article_revision_id, title_contains (so khớp con qua casefold + NFC); trả kết quả theo thứ tự ổn định `(article_id, revision_number)`.
    - `count_new_articles(topic, business_date_utc)`: đếm số `article_id` phân biệt có `NEW_ARTICLE` resolution trong topic, có `fetched_at` quy về UTC rơi vào đúng ngày nghiệp vụ UTC.
    - Hoàn toàn chỉ đọc qua `articles.list_all`, `events.list_all`, `resolutions.list_all`; không mở transaction, không gọi `save`, `put`, `commit`, `rollback`, `append_event`.
- `tests/unit/ingestion/test_ingestion_queries.py`:
  - 55 test items bao quát toàn diện các yêu cầu CT-CNT-006, D8-B-10, import boundary CHECK-B, kiểm tra truy vết đầy đủ và thiếu trường, xử lý lỗi fail-closed, tính ổn định thứ tự tìm kiếm, đếm bài mới theo ngày UTC, bất biến chỉ đọc (không ghi vào repository).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `git diff --check` | 0 | không output |
| 2 | `python -m pytest tests/unit/ingestion/test_ingestion_queries.py -q -p no:cacheprovider` | 0 | 55 passed in 0.06s |
| 3 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 35 passed in 0.05s |

## Quyết định mặc định (D8)

(Ghi nhận dưới dạng GIẢ ĐỊNH theo quy chế D8, chưa duyệt chính thức):
1. API là lớp `IngestionQueries(uow)` để giữ chữ ký `trace_revision(article_revision_id)`, `search(filters)`, `count_new_articles(topic, business_date_utc)`.
2. Trường truy vết thiếu = chuỗi rỗng/chỉ khoảng trắng/None, source_revision không phải int, fetched_at không parse RFC3339 có offset, provenance_chain rỗng; uncertain_fields = trường thiếu theo thứ tự TRACE_FIELDS rồi tới uncertain_fields đã lưu của revision; is_fully_traced False khi có trường truy vết trong uncertain_fields; raw_snapshot_ref tuỳ chọn trong binding nhưng vẫn được liệt kê khi thiếu.
3. Revision không tồn tại → LookupError, không trả rỗng.
4. Search tìm trên mọi revision, lọc AND, title_contains so khớp chuỗi con sau normalize_text + casefold, thứ tự (article_id, revision_number), event_ids lấy từ member_refs (chỉ bài LINKED) và sắp xếp; filter lạ/rỗng → ValueError.
5. Count_new_articles đếm article_id phân biệt có resolution NEW_ARTICLE (mọi dedup_policy_revision), topic của revision, ngày UTC của fetched_at (D8-B-10, múi giờ chưa chốt); business_date_utc nhận date hoặc chuỗi YYYY-MM-DD, datetime bị từ chối; NEW_ARTICLE trỏ revision không tồn tại → LookupError.
6. Truy vấn không mở transaction, không save/put/commit/append_event.

## Danh sách chờ user (pendingUserCheckpoint)

- Múi giờ ngày nghiệp vụ (ROADMAP-OPEN-004, QUALITY-OPEN-014/TEST-OPEN-009).
- Endpoint/màn hình tìm kiếm qua REQ-B-CONV-05.
- Adapter PostgreSQL qua REQ-B-CONV-02.
- USER-CKPT-D9-D10.
- CP7 tài nguyên thật (D5).

## Giới hạn

- Không chạy full suite, không chạy tests/m1, tests/m2.
- Không sửa ports.py, memory.py, event_link.py, normalization.py, binding, fixture, pyproject.toml, uv.lock, HANDOFF.md, README.md, CHANGELOG.md.
- Không gọi dịch vụ thật hay đọc bí mật.
