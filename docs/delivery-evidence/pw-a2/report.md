# PW-A2: Wiring CollectSource và ResolveCollectedDocument

## Thay đổi

Gói công việc PW-A2 đã triển khai đãy đủ các yêu cầu kỹ thuật trên đủng bốn tệp thuộc owned paths đủoc phân quyền:

1. `src/source_ingestion/worker/production_deps.py`:
   - Dựng `CollectActivityDeps` theo từng lời gọi thông qua `CollectDepsFactory.deps_for_call()`.
   - `adapter_for(source_id)` đọc `source_kind` từ `cp_sources` và dựng `RealFeedSource` riêng cho từng nguồn, không khoá theo kind và không dùng chung instance giữa các nguồn; nguồn không tìm thấy hoặc loại nguồn chưa hỗ trợ nhận `UnavailableSourceAdapter` (trả về `CapabilityUnavailable`, handler ghi nhận `FAILED_FINAL` không thử lại).
   - Lớp `_FetchBridge` và `_RecordingAdapter` làm cầu nối gọi `extract_candidate` của adapter đã chọn trên đúng `FetchedDocument` vừa tải, bảo toàn locator và gợi ý media.
   - Lớp `ReadThroughUnitOfWork` và `_ReadThroughRepository` bọc UoW PostgreSQL của A để cho phép các thao tác đọc (`READ_METHODS`) diễn ra ngoài khối `with` bằng cách mượn kết nối ngắn hạn, trong khi các thao tác ghi vẫn bắt buộc nằm trong khối `with`.
   - Hàm `reject_request_error` chuyển đổi `ActivityRequestError` sang `ActivityRejected` (`MISSING_EXECUTION_GRANT` nếu thiếu grant, ngược lại `INVALID_ACTIVITY_REQUEST`) để `_activity_fn` ném `ApplicationError(non_retryable=True)`.
   - Hàm `collect_source_activity_handler` bọc handler `handle_collect_source_activity`.

2. `src/ingestion/application/production_deps.py`:
   - Dựng `ResolveActivityDeps` theo từng lời gọi thông qua `ResolveDepsFactory.deps_for_call()`.
   - Lớp `PostgresSourceTierLookup` đọc `payload->>'tier'` từ `cp_sources` theo `workspace_id` và `source_id`, parse ra giá trị nguyên 1..3, ném `LookupError` nếu thiếu hoặc ngoài dải.
   - Lớp `PostgresPackageLoader` tra cứu `CollectedDocumentPackage` theo `collected_document_id` trong `cp_collected_document_packages`.
   - Lớp `ProcessLocalRecordsUnitOfWork` và `_ProcessLocalRecords` bọc UoW PostgreSQL của B: lưu trữ process-local cho hai kind `activity_result` và `article_media_attachment` mà `PostgresRecordRepository` chưa có bảng trong DB, stage và publish khi commit, rollback khi thất bại.
   - Mặc định `DEFAULT_DEDUP_POLICY` khai báo rõ `dedup_policy_revision='dedup-default-v1'`, `near_duplicate_jaccard=0.8`, `shingle_size=3` theo corpus B-12.
   - Hàm `reject_request_error` chuyển đổi `ActivityRequestError` sang `ActivityRejected`.
   - Hàm `resolve_activity_handler` bọc handler `handle_resolve_activity`.

3. `tests/integration/prod_wiring/test_pw_a2_collect_resolve.py`:
   - Xây dựng bộ kiểm thử tích hợp hoàn chỉnh trên PostgreSQL 18.6 thật và máy chủ loopback `Site` với 14 bài test (docstring đầu tệp khai báo đủ `coveredIds: PW-A2-01, CT-SRC-004, CT-SRC-005, CT-CNT-001`):
     - `test_collect_source_writes_a_collected_document_with_its_image`: thu thập một bài viết và ảnh kèm theo từ feed loopback, ghi nhận `cp_collected_document_packages`.
     - `test_a_404_source_does_not_stop_the_next_source`: nguồn lỗi 404 trả về thất bại không thử lại và không làm gián đoạn nguồn kế tiếp.
     - `test_deps_are_built_per_call_and_the_adapter_is_chosen_per_source`: xác minh deps và adapter được dựng độc lập cho mỗi lời gọi, adapter phân bổ chính xác theo từng nguồn.
     - `test_same_business_date_reuses_the_periodic_run_and_the_next_day_starts_a_new_one`: trong cùng một ngày nghiệp vụ tái sử dụng run định kỳ đã hoàn tất (replay), ngày hôm sau khởi tạo run mới.
     - `test_feed_image_survives_an_article_redirect`: ảnh trong feed vẫn được lưu giữ trọn vẹn khi bài viết bị chuyển hướng HTTP 302.
     - `test_a_stale_grant_returns_a_stale_result_before_any_fetch`: grant bị stale lập tức trả kết quả stale trước khi thực hiện tải dữ liệu.
     - `test_request_errors_become_non_retryable_application_errors`: kiểm tra cả hai handler chuyển đổi lỗi yêu cầu thành `ApplicationError(non_retryable=True)` với thông điệp từ chối xác định.
     - `test_a_handler_without_the_wrapper_leaks_activity_request_error`: đối chứng handler thô chưa bọc làm lộ ngoại lệ `ActivityRequestError`.
     - `test_missing_grant_and_bad_requests_map_to_distinct_rejection_codes`: phân định rõ ràng giữa `MISSING_EXECUTION_GRANT` và `INVALID_ACTIVITY_REQUEST`.
     - `test_resolve_creates_an_article_then_a_new_revision`: `ResolveCollectedDocument` tạo bài viết mới rồi tiếp tục tạo revision mới khi có nội dung cập nhật.
     - `test_tier_lookup_reads_postgresql_and_the_better_tier_becomes_representative`: `tier_lookup` đọc PostgreSQL thật xác định nguồn có Tier tốt hơn trở thành nguồn đại diện.
     - `test_package_loader_looks_up_by_collected_document_id`: `package_loader` tra cứu gói chính xác theo `collected_document_id`.
     - `test_dedup_policy_default_is_explicit_and_can_be_overridden`: chính sách dedup mặc định rõ ràng và hỗ trợ ghi đè linh hoạt.
     - `test_production_deps_sources_follow_the_package_contract`: kiểm tra tĩnh xác nhận hai tệp production_deps tuân thủ nghiêm ngặt hợp đồng gói.

4. `docs/delivery-evidence/pw-a2/report.md`:
   - Báo cáo chi tiết quá trình thực hiện, quyết định kỹ thuật, lệnh đã chạy và bằng chứng nghiệm thu của gói PW-A2.

## Giả định và quyết định (D8)

- (a) deps dựng theo từng lời gọi qua CollectDepsFactory.deps_for_call và ResolveDepsFactory.deps_for_call, chỉ kho kết quả idempotent của A và kho kind process-local của B được chia sẻ có chủ đích;
- (b) adapter_for(source_id) đọc source_kind từ cp_sources và dựng RealFeedSource riêng cho từng nguồn, nguồn lạ hoặc loại chưa hỗ trợ nhận UnavailableSourceAdapter (CapabilityUnavailable, FAILED_FINAL không thử lại);
- (c) extractor là cầu nối extract_candidate của RealFeedSource trên đúng FetchedDocument vừa tải, không dùng stdlib extractor chỉ dành cho fixture;
- (d) mặc định: RetryPolicy 3 lần, ExtractionPolicy bắt buộc tiêu đề cho rss_feed/atom_feed, dedup_policy 'dedup-default-v1' với near_duplicate_jaccard 0.8 và shingle_size 3 theo corpus B-12;
- (e) ActivityRequestError thành ActivityRejected: có issue field execution_grant thì MISSING_EXECUTION_GRANT, còn lại INVALID_ACTIVITY_REQUEST, nên _activity_fn ném ApplicationError non_retryable.

## Lệnh đã chạy

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `git diff --check` | 0 | Không có output (sạch khoảng trắng thừa) |
| `python -m pytest tests/integration/prod_wiring/test_pw_a2_collect_resolve.py tests/unit/collection/test_a01_package_layout.py tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | `66 passed, 62 subtests passed in 10.73s` |
| `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8').lower() for p in ['src/source_ingestion/worker/production_deps.py', 'src/ingestion/application/production_deps.py']); assert 'activityrequesterror' in t and 'fake' not in t and 'from src.' not in t, 'PW-A2'"` | 0 | Khẳng định thành công, không in lỗi |
| `python -c "import pathlib, re; t = pathlib.Path('tests/integration/prod_wiring/test_pw_a2_collect_resolve.py').read_text(encoding='utf-8'); m = re.search(r'coveredIds: ([^\n]*)', t); assert m and {'PW-A2-01', 'CT-SRC-004', 'CT-SRC-005', 'CT-CNT-001'} <= set(x.strip() for x in m.group(1).split(',')), 'coveredIds'"` | 0 | Khẳng định thành công, không in lỗi |

Dòng RED: Thứ tự các bước của work order quy định tạo mã trước test nên chưa chứng kiến RED trực tiếp; các test phản ví dụ chạy trên PostgreSQL thật.

## Phản ví dụ đã loại trừ

- Adapter khoá theo kind: Đã loại trừ qua `test_deps_are_built_per_call_and_the_adapter_is_chosen_per_source` (xác nhận adapter_for chọn theo source_id và dựng instance RealFeedSource riêng, không dùng chung).
- Deps dùng chung một lần: Đã loại trừ qua `test_deps_are_built_per_call_and_the_adapter_is_chosen_per_source` và `test_same_business_date_reuses_the_periodic_run_and_the_next_day_starts_a_new_one` (xác nhận deps và UoW được tạo mới ở từng lời gọi).
- Tier_lookup hằng số: Đã loại trừ qua `test_tier_lookup_reads_postgresql_and_the_better_tier_becomes_representative` (xác nhận tier_lookup đọc PostgreSQL từ cp_sources và nguồn tier tốt hơn trở thành representative).
- ActivityRequestError retry vô hạn: Đã loại trừ qua `test_request_errors_become_non_retryable_application_errors` và `test_a_handler_without_the_wrapper_leaks_activity_request_error` (xác nhận bọc thành ApplicationError non_retryable).

## Mã test phủ

coveredIds: PW-A2-01, CT-SRC-004, CT-SRC-005, CT-CNT-001

- `PW-A2-01`: Được bao phủ bởi `test_collect_source_writes_a_collected_document_with_its_image`, `test_deps_are_built_per_call_and_the_adapter_is_chosen_per_source`, `test_request_errors_become_non_retryable_application_errors`, `test_resolve_creates_an_article_then_a_new_revision`.
- `CT-SRC-004`: Được bao phủ bởi `test_same_business_date_reuses_the_periodic_run_and_the_next_day_starts_a_new_one`, `test_feed_image_survives_an_article_redirect`, `test_a_stale_grant_returns_a_stale_result_before_any_fetch`.
- `CT-SRC-005`: Được bao phủ bởi `test_collect_source_writes_a_collected_document_with_its_image`, `test_a_404_source_does_not_stop_the_next_source`, `test_deps_are_built_per_call_and_the_adapter_is_chosen_per_source`.
- `CT-CNT-001`: Được bao phủ bởi `test_resolve_creates_an_article_then_a_new_revision`, `test_tier_lookup_reads_postgresql_and_the_better_tier_becomes_representative`, `test_package_loader_looks_up_by_collected_document_id`, `test_dedup_policy_default_is_explicit_and_can_be_overridden`.

## Mục mở

1. PostgresRecordRepository (src/ingestion/persistence/repositories.py, RECORD_TABLES) thiếu kind activity_result và article_media_attachment nên wiring giữ hai kind trong tiến trình qua ProcessLocalRecordsUnitOfWork, mất khi khởi động lại (resolution đã lưu bền nên replay vẫn đúng; liên kết media của bài trùng có thể phân loại lại) và đề xuất slice persistence B thêm bảng;
2. collect_source đọc ngoài khối with trong khi PostgresSourceIngestionUnitOfWork chỉ có kết nối trong khối with nên wiring dùng ReadThroughUnitOfWork, đề xuất sửa trong slice A;
3. cổng ClaimsCurrencyPort production cho GrantClaims không có video job chưa tồn tại (ExecutionGrantCurrency nhận ExecutionGrant cần job_id), PW-A2 chỉ nhận cổng được tiêm và composition root PW-W1/W2 phải cung cấp;
4. SQL của tier_lookup và package_loader nằm trong src/ingestion/application/production_deps.py vì persistence nằm ngoài owned paths, đề xuất chuyển;
5. kho kết quả idempotent của A nằm trong tiến trình, replay sau khởi động lại dựa vào periodic run đã lưu. Không ghi 'dã duyệt' cho bất kỳ mục chờ user nào.
