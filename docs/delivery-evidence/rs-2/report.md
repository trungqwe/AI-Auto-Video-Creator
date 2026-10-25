# RS-2: Service articles chỉ đọc (module B)

## Phạm vi
Triển khai đúng 3 tệp thuộc owned paths:
- `src/controlplane/infrastructure/read_screens/articles.py`
- `tests/integration/read_screens/test_rs_2_articles.py`
- `docs/delivery-evidence/rs-2/report.md`

## RED (bước 8)
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_2_articles.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 1 (khác 0)
- Dòng tổng kết nguyên văn: `27 failed, 3 passed in 1.91s`
- RED chạy trên stub trả rỗng nên không phải lỗi import hay thu thập (collection error). 3 test pass tại thời điểm RED là các trường hợp lọc source_id với giá trị lạ và rỗng trả danh sách rỗng (khớp với kết quả stub trả rỗng).
- Danh sách 27 test FAILED:
  - `test_rows_have_exact_keys_and_show_latest_revision`
  - `test_direction_defaults_to_desc_and_honours_explicit_direction`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[1-asc-expected0]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[1-desc-expected1]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[2-asc-expected0]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[2-desc-expected1]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[3-asc-expected0]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[3-desc-expected1]`
  - `test_default_direction_pagination_is_newest_first`
  - `test_source_id_filter_uses_latest_revision_and_unknown_value_is_empty[src-a-expected0]`
  - `test_source_id_filter_uses_latest_revision_and_unknown_value_is_empty[src-b-expected1]`
  - `test_source_id_filter_paginates`
  - `test_unsupported_filter_name_raises_value_error`
  - `test_fetch_one_returns_latest_revision_row_or_none`
  - `test_workspaces_are_isolated`
  - `test_service_does_not_change_source_tables`
  - `test_one_query_per_call_whatever_the_article_count`
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
  - Khóa dòng và revision: `AssertionError: assert [] == ['a-5', 'a-4', 'a-3', 'a-2', 'a-1']`
  - Phân trang cursor: `assert 1 == 3 where 1 = len([Page(items=(), next_cursor=None)])`
  - Bộ lọc lạ và cursor sai: `Failed: DID NOT RAISE ValueError`
  - Chi tiết fetch_one: `AssertionError: assert None == {'article_id': 'a-2', ...}`
  - Ranh giới kiến trúc: `AssertionError: assert 'r.revision = a.revision' in ...`

## GREEN (bước 10)
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_2_articles.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 0
- Dòng tổng kết nguyên văn: `30 passed in 0.87s`
- Toàn bộ 30 test passed, 0 failed, 0 skipped, 0 error.

## Lệnh kiểm khác
| Lệnh kiểm | Mục đích | Mã thoát |
| --- | --- | --- |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/articles.py').read_text(encoding='utf-8').lower(); assert 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'from src.' not in t and 'os.environ' not in t and 'normalized_text' not in t, 'RS-2'"` | Quét văn bản articles.py cấm chuỗi cấm (bước 11) | 0 |
| `git diff --check` | Kiểm tra diff/khoảng trắng cuối dòng trước khi stage (bước 12) | 0 |
| `git diff --check --cached` | Kiểm tra staging của 3 owned paths (bước 15) | 0 |

## Kết luận theo tiêu chí nghiệm thu
1. `ArticleModuleService(connection_scope)` cung cấp đầy đủ `fetch_page` và `fetch_one`. Câu lệnh SQL nối `cp_articles` với `cp_article_revisions` theo `r.revision = a.revision` với id `article_id`, sắp theo `updated_at`, lọc theo `source_id`. Dòng trả về có đúng 7 khóa `article_id`, `source_id`, `title`, `published_at`, `fetch_evidence_ref` (= `raw_snapshot_ref`, null khi thiếu), `revision`, `updated_at`. `published_at` là null khi bài không có ngày. Bài nhiều revision hiển thị title và revision mới nhất. Mỗi lời gọi chỉ thực thi đúng 1 truy vấn SQL (không N+1).
2. Phân trang cursor keyset ≥2 trang không trùng lặp và không sót dòng cho cả `asc` và `desc`, mặc định theo `desc`. `fetch_one` trả dòng đúng, trả `None` khi không tồn tại hoặc id thuộc workspace khác. Cô lập workspace hoàn toàn cho cả danh sách, chi tiết và bộ lọc. Bộ lọc `source_id` lọc theo revision mới nhất, giá trị lạ hoặc rỗng trả về rỗng. Số hàng bảng nguồn `cp_articles` và `cp_article_revisions` không đổi sau các thao tác đọc service. Cursor không hợp lệ ném `ValueError`.
3. Không trả các trường cấm: `normalized_text`, `requested_url`, `final_url`, `provenance_chain`. Canary trong các trường này không xuất hiện trong kết quả JSON serialize. Mã nguồn `articles.py` sạch hoàn toàn các chuỗi cấm (`insert into`, `update controlplane`, `delete from`, `from src.`, `os.environ`, `normalized_text`).

## Ghi chú
(a) Test ghim `updated_at` bằng một câu lệnh cập nhật trong phần seed của test (repository đặt `updated_at` theo giờ giao dịch) để thứ tự và cặp trùng xác định, service hoàn toàn chỉ đọc không ghi;
(b) Bài không có dòng revision sẽ không hiển thị vì sử dụng nối trong (INNER JOIN), phù hợp với kế hoạch mục 5.1;
(c) Bộ lọc ngoài `source_id` ném `ValueError` thay vì bỏ qua im lặng;
(d) Tuyệt đối không ghi DSN, mật khẩu hay bất kỳ thông tin bí mật nào trong báo cáo, test hoặc mã nguồn.

## Rebase lên integration head 24833dbb

- Cấp lại sau thu hồi grant G1 (BINDING_DRIFT): rebase nhánh lane lên `24833dbb52f5872416f369a2ee4517e536017e70` bằng `git rebase 24833dbb52f5872416f369a2ee4517e536017e70`, giữ nguyên các commit của lane.
- Ràng buộc đã đổi nằm ở `src/controlplane/api/wiring/production.py` (ngoài owned paths của RS-2). Kết quả probe đọc tệp ở bước 2: []. Kết luận: không có dòng nào nhắc tới ArticleModuleService/read_screens nên mã RS-2 không cần đổi.
- `python -m pytest tests/integration/read_screens/test_rs_2_articles.py -q -p no:cacheprovider`: mã thoát 0, dòng tổng kết nguyên văn `30 passed in 1.48s`.
- Quét `articles.py` tìm chuỗi cấm: mã thoát 0.
- `git diff --check`: mã thoát 0.
