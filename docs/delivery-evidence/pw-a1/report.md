# PW-A1: Nạp bảy nguồn seed và PlanCollectionCycle

## Thay đổi

Gói công việc PW-A1 đã triển khai đầy đủ các yêu cầu kỹ thuật trên đúng bốn tệp thuộc owned paths được phân quyền:

1. `src/source_ingestion/application/seed_sources.py`:
   - Tạo module nạp bảy nguồn seed từ `tools/launcher/prod/sources.json` qua `SourceCommandHandler.register_source` (FR-COL-001).
   - Triển khai `_load_sources` kiểm tra hợp lệ cấu trúc tệp (bắt buộc danh sách object không rỗng, đầy đủ các trường `code`, `url`, `source_kind`, `tier`, URL bắt đầu bằng `https://`, `enabled` là boolean, không trùng mã `code`) trước khi thực hiện bất kỳ thao tác ghi nào.
   - Hàm `seed_sources(handler, path, *, workspace_id, topics)` thực hiện nạp nguồn mang tính lũy quyền (idempotent) với tiền tố khoá `pw-a1:seed-source:<code>`, actor và correlation_id là `pw-a1-seed`, topic mặc định `('news',)`.
   - Xử lý phân loại kết quả: bắt `SourceAlreadyRegisteredError` tăng đếm `existing`, bắt `TombstoneConflictError` tăng đếm `tombstoned` mà không cố gắng hồi sinh nguồn đã xoá; phân biệt `registered` và `replayed` qua `result.replayed`. Trả về đối tượng `SeedSourcesReport`.

2. `src/source_ingestion/application/plan_cycle.py`:
   - Tạo các kiểu dữ liệu và giao thức: `CyclePlan` (chứa `cycle_ref`, `business_date`, danh sách nguồn `due` và `skipped`), giao thức `CycleMarkStore` với phương thức `claim`.
   - Lớp `PostgresCycleMarkStore`: quản lý bảng `controlplane.cp_source_cycle_marks` trên chính kết nối đang hoạt động của Unit of Work (`uow._active_connection` qua phương thức `for_uow`), bảo đảm thao tác mark nằm hoàn toàn trong cùng giao dịch với kết hoạch chu kỳ và commit đồng thời. Phương thức `claim` sử dụng câu lệnh `INSERT ... ON CONFLICT (workspace_id, source_id, cycle_day) DO NOTHING RETURNING source_id` và xác thực `collection_run_ref` khớp với `cycle_ref` hiện tại.
   - Lớp dịch vụ `PlanCollectionCycle`: tính toán `business_date` dựa trên đồng hồ tiêm được theo múi giờ `Asia/Ho_Chi_Minh`, lưu thời điểm `created_at` ở UTC; sinh `cycle_ref = 'cycle:' + cycle_key`. Gọi `rank_eligible_sources` với `existing_runs=()` (chủ ý vì mark là cổng kiểm soát một lượt mỗi ngày), áp dụng ngưỡng `tier_order` để chặn nguồn ngoài danh sách và sắp xếp theo thứ tự `(thứ hạng Tier, source_id)`. Gọi `uow.commit()` đúng một lần trong toàn bộ chu kỳ.
   - Hàm `plan_collection_cycle_handler`: tạo handler bọc dịch vụ trả về `ActivityResult` hợp lệ theo `validate_activity_result` với `disposition='succeeded'`, danh sách `output_refs` kiểu `collection_source`, thời điểm `completed_at` chuẩn hóa ISO-8601 kết thúc bằng `Z`, và metrics phản ánh `business_date`, `cycle_ref`, `selected`, `skipped`. Từ chối request thiếu claims bằng `MISSING_EXECUTION_GRANT` hoặc `operation_key` không hợp lệ bằng `INVALID_ACTIVITY_REQUEST`.

3. `tests/integration/prod_wiring/test_pw_a1_plan_cycle.py`:
   - Xây dựng bộ kiểm thử tích hợp hoàn chỉnh trên PostgreSQL 18.6 thật và loopback với 15 bài test:
     - `test_seed_twice_leaves_exactly_seven_sources`: kiểm tra seed lần đầu đăng ký đủ 7 nguồn, seed lần hai ghi nhận 7 replayed và số bản ghi `cp_sources` vẫn giữ đúng 7 nguồn ACTIVE.
     - `test_seed_rejects_an_invalid_file_before_any_write`: kiểm tra cấu trúc tệp không hợp lệ bị từ chối trước khi ghi và không để lại bản ghi nào trong DB.
     - `test_seed_counts_existing_and_tombstoned_sources_without_resurrecting`: kiểm tra nguồn đã đăng ký bằng khoá khác đếm là existing, nguồn đã xoá tombstone đếm là tombstoned và không bị hồi sinh.
     - `test_first_cycle_returns_seven_refs_then_none_the_same_day_then_seven_the_next_day`: kiểm tra chu kỳ đầu trong ngày trả đủ 7 refs, chu kỳ sau cùng ngày trả 0 refs, sang ngày hôm sau trả lại đủ 7 refs; kiểm tra `created_at` lưu UTC và `cycle_day` lưu ngày ICT.
     - `test_same_operation_key_replays_the_same_refs_and_other_keys_get_none`: kiểm tra gọi lại cùng operation_key nhận lại đúng các ref cũ, operation_key khác trong ngày nhận danh sách rỗng.
     - `test_disabled_sources_are_not_due`: kiểm tra nguồn bị tắt `collection_enabled=False` không được đưa vào danh sách đến hạn và không tiêu hao mark.
     - `test_tier_threshold_blocks_lower_tier_without_consuming_marks`: kiểm tra ngưỡng Tier chặn nguồn tier thấp mà không tiêu hao mark, sang lượt mở rộng mới nhận và ghi mark.
     - `test_refs_are_ordered_by_tier_rank_then_source_id`: kiểm tra các refs đầu ra được sắp xếp tuần tự theo thứ hạng Tier rồi đến source_id tăng dần.
     - `test_marks_are_written_in_the_plan_transaction_and_commit_with_it`: sử dụng lớp probe `ProbedUow` xác nhận kết nối bên trong UoW nhìn thấy 7 mark trước khi commit trong khi kết nối bên ngoài chưa thấy; sau commit cả hai đều thấy 7 mark.
     - `test_a_failed_commit_leaves_no_mark_and_the_next_call_returns_all_sources`: kiểm tra khi commit thất bại toàn bộ mark bị rollback, không còn mark nào trong DB và lượt gọi sau trả lại đủ 7 nguồn.
     - `test_handler_builds_a_valid_activity_result_and_rejects_bad_requests`: kiểm tra handler sinh kết quả khớp `validate_activity_result`, từ chối request thiếu claims bằng `MISSING_EXECUTION_GRANT` và request thiếu `operation_key` bằng `INVALID_ACTIVITY_REQUEST`.
     - `test_sources_follow_the_package_contract`: kiểm tra tĩnh hai tệp nguồn không chứa `from src.`, không import psycopg, không mở kết nối riêng hay autocommit, và chỉ chứa đúng một lệnh `commit()`.

4. `docs/delivery-evidence/pw-a1/report.md`:
   - Báo cáo chi tiết quá trình thực hiện, quyết định kỹ thuật, lệnh đã chạy và bằng chứng nghiệm thu của gói PW-A1.

## Giả định và quyết định (D8)

- (a) `seed_sources(handler, path, *, workspace_id)` nhận thêm tham số `workspace_id` vì phương thức `SourceCommandHandler.register_source` yêu cầu; khoá idempotency được định dạng `pw-a1:seed-source:<code>`, topic mặc định là `('news',)`; nguồn đã đăng ký bằng khoá khác được đếm là `existing`, nguồn ở trạng thái tombstone không bị đăng ký lại.
- (b) Đối tượng `Source` hiện tại chưa có trường độ ưu tiên riêng biệt nên thứ tự ưu tiên trong cùng một Tier được xếp theo `source_id` tăng dần theo hành vi của `rank_eligible_sources`.
- (c) Ngưỡng Tier được cấu hình thông qua tham số bắt buộc `tier_order` (các nguồn có Tier không nằm trong danh sách sẽ bị bỏ qua và không tiêu hao mark của ngày đó).
- (d) Trường `collection_run_ref` của bảng `cp_source_cycle_marks` lưu giá trị `cycle:<operation_key>` để khi gọi lại với cùng một `operation_key` hệ thống sẽ phát lại đúng các ref đã lập trước đó.
- (e) Danh sách `output_refs` của activity chỉ chứa các tham chiếu loại `collection_source`; thông tin `business_date` được đặt trong `metrics`.
- (f) Trong lệnh gọi `rank_eligible_sources`, tham số `existing_runs` được truyền tuple rỗng `()` vì bảng `cp_source_cycle_marks` đã đóng vai trò cổng kiểm soát tối đa một lượt mỗi ngày, còn các khoá periodic của `CollectionRun` tiếp tục được kiểm soát ở stage collect tiếp theo.

## Lệnh đã chạy

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/source_ingestion/application/seed_sources.py', 'src/source_ingestion/application/plan_cycle.py']); assert 'register_source' in t and 'cp_source_cycle_marks' in t and 'from src.' not in t, 'PW-A1'"` | 0 | Khẳng định thành công, không in lỗi |
| `python -m pytest tests/integration/prod_wiring/test_pw_a1_plan_cycle.py tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | `28 passed, 62 subtests passed in 6.17s` |
| `git diff --check` | 0 | Không có output (sạch khoảng trắng thừa) |
| `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/source_ingestion/application/seed_sources.py', 'src/source_ingestion/application/plan_cycle.py']); assert 'register_source' in t and 'cp_source_cycle_marks' in t and 'from src.' not in t, 'PW-A1'"` | 0 | Khẳng định thành công, không in lỗi |

Dòng RED: Thứ tự các bước của work order quy định tạo file nguồn trước rồi mới tạo tệp test nên không cho phép chứng kiến RED trực tiếp trước implementation; thay vào đó, các test phản ví dụ loại trừ vi phạm được xây dựng đầy đủ và chạy kiểm chứng trực tiếp trên PostgreSQL 18.6 thật.

## Phản ví dụ đã loại trừ

- Nguồn nạp đôi: Đã loại trừ qua `test_seed_twice_leaves_exactly_seven_sources`, nạp lần 2 báo 7 replayed và `cp_sources` vẫn giữ đúng 7 dòng.
- Hai lượt một ngày cho cùng nguồn: Đã loại trừ qua `test_first_cycle_returns_seven_refs_then_none_the_same_day_then_seven_the_next_day`, lượt đầu trả 7 refs, lượt hai trong cùng ngày trả 0 refs, sang ngày hôm sau trả lại đủ 7 refs.
- Mark ghi ngoài giao dịch: Đã loại trừ qua hai test `test_marks_are_written_in_the_plan_transaction_and_commit_with_it` và `test_a_failed_commit_leaves_no_mark_and_the_next_call_returns_all_sources`, đo bằng `ProbedUow` xác nhận kết nối UoW thấy mark trước khi commit và kết nối độc lập chưa thấy; khi commit lỗi toàn bộ mark bị huỷ bỏ không còn tồn đọng và lần gọi kế tiếp phục hồi trả đủ 7 nguồn.
- Bỏ qua Tier: Đã loại trừ qua `test_tier_threshold_blocks_lower_tier_without_consuming_marks`, nguồn có Tier ngoài danh sách bị chặn mà không tiêu hao mark, khi mở rộng danh sách Tier mới được chọn và ghi mark.
- Import tiền tố src: Đã loại trừ qua `test_sources_follow_the_package_contract` và các lệnh probe quét tĩnh ở bước 6 và 17.

## Mã test phủ

coveredIds: PW-A1-01, CT-SRC-004, CONV-A-06, FR-COL-001

- `PW-A1-01`: Được bao phủ bởi `test_seed_twice_leaves_exactly_seven_sources`, `test_seed_rejects_an_invalid_file_before_any_write`, `test_seed_counts_existing_and_tombstoned_sources_without_resurrecting`.
- `CT-SRC-004`: Được bao phủ bởi `test_first_cycle_returns_seven_refs_then_none_the_same_day_then_seven_the_next_day`, `test_same_operation_key_replays_the_same_refs_and_other_keys_get_none`, `test_disabled_sources_are_not_due`, `test_marks_are_written_in_the_plan_transaction_and_commit_with_it`, `test_a_failed_commit_leaves_no_mark_and_the_next_call_returns_all_sources`.
- `CONV-A-06`: Được bao phủ bởi `test_tier_threshold_blocks_lower_tier_without_consuming_marks`, `test_refs_are_ordered_by_tier_rank_then_source_id`, `test_handler_builds_a_valid_activity_result_and_rejects_bad_requests`.
- `FR-COL-001`: Được bao phủ bởi `test_seed_twice_leaves_exactly_seven_sources`, `test_first_cycle_returns_seven_refs_then_none_the_same_day_then_seven_the_next_day`, `test_sources_follow_the_package_contract`.

## Mục mở

1. `PostgresSourceIngestionUnitOfWork` hiện tại chưa có kho marks chuyên trách nên `PostgresCycleMarkStore.for_uow` phải truy cập trực tiếp `uow._active_connection`; khuyến nghị đưa việc bổ sung repository marks chính thức vào backlog của slice persistence.
2. `PlanCollectionCycle` có đặc tính `side_effect=False` trên hợp đồng hoạt động nên request từ workflow có thể không mang theo execution grant, tuy nhiên handler theo quy ước chung của `service_handler` sẽ từ chối nếu thiếu claims; gói tích hợp workflow PW-W1 cần bảo đảm cấp grant tương thích khi kích hoạt.
3. Tham chiếu `business_date` cần thiết cho các hoạt động của stage `CollectSource` tiếp theo sẽ do gói PW-A2 hoặc bước fan-out trong workflow bổ sung tương ứng.
4. Logic mở rộng Tier động dựa trên bộ đếm bài viết duy nhất (`decide_tier_expansion`) thuộc thẩm quyền phân hệ G/B, nằm ngoài phạm vi của PW-A1.
