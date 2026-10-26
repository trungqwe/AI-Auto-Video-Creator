# RS-3: Service events chỉ đọc (module B)

## Phạm vi
Triển khai đúng 3 tệp thuộc owned paths:
- `src/controlplane/infrastructure/read_screens/events.py`
- `tests/integration/read_screens/test_rs_3_events.py`
- `docs/delivery-evidence/rs-3/report.md`

## RED (bước 6)
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_3_events.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 1 (khác 0)
- Dòng tổng kết nguyên văn: `27 failed, 4 passed in 0.95s`
- RED chạy trên stub trả rỗng nên không phải lỗi import hay thu thập (collection error). 4 test pass tại thời điểm RED là các trường hợp lọc status với giá trị lạ và rỗng trả danh sách rỗng (khớp với kết quả stub trả rỗng), cùng với kiểm tra không làm thay đổi bảng nguồn khi stub không thao tác cơ sở dữ liệu.
- Danh sách 27 test FAILED:
  - `test_rows_have_exact_keys_and_use_first_member_article`
  - `test_events_without_resolvable_article_have_null_columns`
  - `test_direction_defaults_to_desc_and_honours_explicit_direction`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[1-asc-expected0]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[1-desc-expected1]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[2-asc-expected0]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[2-desc-expected1]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[3-asc-expected0]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[3-desc-expected1]`
  - `test_default_direction_pagination_is_newest_first`
  - `test_status_filter_is_exact_and_unknown_value_is_empty[candidate-expected0]`
  - `test_status_filter_is_exact_and_unknown_value_is_empty[confirmed-expected1]`
  - `test_status_filter_paginates`
  - `test_unsupported_filter_name_raises_value_error`
  - `test_fetch_one_returns_row_or_none`
  - `test_workspaces_are_isolated`
  - `test_one_query_per_call_whatever_the_event_count`
  - `test_invalid_cursor_time_raises_value_error[cursor0-asc]`
  - `test_invalid_cursor_time_raises_value_error[cursor0-desc]`
  - `test_invalid_cursor_time_raises_value_error[cursor1-asc]`
  - `test_invalid_cursor_time_raises_value_error[cursor1-desc]`
  - `test_invalid_cursor_time_raises_value_error[cursor2-asc]`
  - `test_invalid_cursor_time_raises_value_error[cursor2-desc]`
  - `test_invalid_cursor_time_raises_value_error[cursor3-asc]`
  - `test_invalid_cursor_time_raises_value_error[cursor3-desc]`
  - `test_forbidden_fields_never_leave_the_service`
  - `test_service_source_is_read_only_and_layered`
- Dòng trích assertion hoặc DID NOT RAISE đại diện cho từng nhóm:
  - Khóa dòng và thành viên đầu: `AssertionError: assert [] == ['e-6', 'e-5', 'e-4', 'e-3', 'e-2', 'e-1']`
  - Phân trang cursor: `assert 1 == 3 where 1 = len([Page(items=(), next_cursor=None)])`
  - Bộ lọc lạ và cursor sai: `Failed: DID NOT RAISE ValueError`
  - Chi tiết fetch_one: `AssertionError: assert None == {'event_id': 'e-2', ...}`
  - Ranh giới kiến trúc: `assert 'LEFT JOIN' in '"""Read-only service behind the Dashboard events list...'`

## GREEN (bước 8)
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_3_events.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 0
- Dòng tổng kết nguyên văn: `31 passed in 1.01s`
- Toàn bộ 31 test passed, 0 failed, 0 skipped, 0 error.

## Lệnh kiểm khác
| Lệnh kiểm | Mục đích | Mã thoát |
| --- | --- | --- |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/events.py').read_text(encoding='utf-8').lower(); assert 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'from src.' not in t and 'os.environ' not in t and 'normalized_text' not in t, 'RS-3'"` | Quét văn bản events.py cấm chuỗi cấm (bước 9) | 0 |
| `git diff --check` | Kiểm tra diff/khoảng trắng cuối dòng trước khi tạo báo cáo (bước 10) | 0 |

## Kết luận theo tiêu chí nghiệm thu
1. `EventModuleService(connection_scope)` cung cấp đầy đủ `fetch_page` và `fetch_one`. Câu lệnh SQL thực hiện LEFT JOIN giữa `cp_events` và `cp_article_revisions` theo `member_refs[0]` với id `event_id`, sắp xếp theo `updated_at`, lọc theo `status`. Dòng trả về có đúng 7 khóa `event_id`, `title`, `status`, `source_id`, `fetch_evidence_ref` (= `raw_snapshot_ref`), `revision`, `updated_at`. Ba cột `title`, `source_id`, `fetch_evidence_ref` lấy từ bản bài của `member_refs[0]` (GIẢ ĐỊNH-RS-01), và là `null` khi không tìm thấy bài hoặc `member_refs` rỗng/sai revision. Sự kiện có nhiều thành viên luôn lấy thành viên đầu tiên chứ không phải cuối cùng. Mỗi lời gọi chỉ thực thi đúng 1 truy vấn SQL (không N+1).
2. Phân trang cursor keyset ≥2 trang không trùng lặp và không sót dòng cho cả `asc` và `desc`, mặc định theo `desc` (mới nhất trước). `fetch_one` trả dòng đúng, trả `None` khi không tồn tại hoặc id thuộc workspace khác. Cô lập workspace hoàn toàn cho cả danh sách, chi tiết và bộ lọc. Bộ lọc `status` khớp chính xác giá trị, giá trị lạ hoặc rỗng trả về rỗng. Số hàng bảng nguồn `cp_events` và `cp_article_revisions` không đổi sau các thao tác đọc service. Cursor không hợp lệ ném `ValueError`.
3. Không trả các trường `member_refs`, `effective_time_range`, `topic` thô hoặc `normalized_text`. Canary trong các trường này không xuất hiện trong kết quả JSON serialize. Mã nguồn `events.py` sạch hoàn toàn các chuỗi cấm (`insert into`, `update controlplane`, `delete from`, `from src.`, `os.environ`, `normalized_text`).

## Ghi chú
(a) GIẢ ĐỊNH-RS-01 / OI-RS-01: bài đại diện là phần tử đầu của `payload.member_refs`, được thể hiện rõ ràng trong test và tài liệu, chưa phải quyết định đã được user phê duyệt chính thức;
(b) Nối đúng `article_id` và `article_revision_id` của `member_refs[0]` (không lấy bản mới nhất tùy tiện), dùng LEFT JOIN nên sự kiện thiếu bài, `member_refs` rỗng hoặc sai revision vẫn hiển thị bình thường với ba cột null mà không gây lỗi;
(c) Lọc `status` đọc `payload->>'status'`, khớp chính xác hoa thường, bộ lọc khác `status` ném `ValueError` fail-closed;
(d) Test ghim cột `updated_at` bằng một câu UPDATE trong seed (repository đặt theo giờ giao dịch) để thứ tự và cặp trùng xác định, service hoàn toàn chỉ đọc không ghi;
(e) Tuyệt đối không ghi DSN, mật khẩu hay bất kỳ thông tin bí mật nào trong báo cáo, test hoặc mã nguồn.
