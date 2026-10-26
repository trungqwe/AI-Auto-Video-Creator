# RS-4: Service media chỉ đọc (module C)

## Phạm vi
Triển khai đúng 3 tệp thuộc owned paths:
- `src/controlplane/infrastructure/read_screens/media.py`
- `tests/integration/read_screens/test_rs_4_media.py`
- `docs/delivery-evidence/rs-4/report.md`

## RED (bước 8)
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_4_media.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe`)
- Mã thoát: 1 (khác 0)
- Dòng tổng kết nguyên văn: `47 failed, 13 passed in 1.13s`
- RED chạy trên stub trả rỗng nên không phải lỗi import hay thu thập (collection error). 13 test pass tại thời điểm RED gồm: 7 ca kiểm thử bộ lọc với giá trị lạ/rỗng mong đợi danh sách rỗng (khớp với kết quả stub trả rỗng: `{'kind': 'audio', 'status': 'CATALOGED'}`, `{'kind': 'video'}`, `{'kind': 'IMAGE'}`, `{'kind': ''}`, `{'status': 'FAILED'}`, `{'status': 'cataloged'}`, `{'status': ''}`), 1 ca `test_reads_do_not_change_source_tables` do stub không thao tác CSDL nên bảng nguồn không đổi, 4 ca `test_apply_update_raises_capability_unavailable_and_changes_nothing` với 4 item_id ('alpha', 'charlie', 'nope', 'zulu') vì stub đã ném sẵn `CapabilityUnavailableError('media')`, và 1 ca `test_apply_update_signature_matches_route_contract` vì chữ ký của hàm `apply_update` trên stub đã đúng chuẩn keyword-only.
- Danh sách 47 test FAILED:
  - `test_rows_have_exact_keys_and_values`
  - `test_asset_without_fingerprint_is_discovered`
  - `test_default_direction_is_desc_and_explicit_direction_is_honoured`
  - `test_name_sort_follows_media_asset_id_not_updated_at`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[1-asc-updated_at]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[1-asc-name]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[1-desc-updated_at]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[1-desc-name]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[2-asc-updated_at]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[2-asc-name]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[2-desc-updated_at]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[2-desc-name]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[3-asc-updated_at]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[3-asc-name]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[3-desc-updated_at]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[3-desc-name]`
  - `test_default_pagination_is_newest_first`
  - `test_filters_are_exact_and_unknown_value_is_empty[params0-expected0]`
  - `test_filters_are_exact_and_unknown_value_is_empty[params1-expected1]`
  - `test_filters_are_exact_and_unknown_value_is_empty[params2-expected2]`
  - `test_filters_are_exact_and_unknown_value_is_empty[params3-expected3]`
  - `test_filters_are_exact_and_unknown_value_is_empty[params4-expected4]`
  - `test_filters_are_exact_and_unknown_value_is_empty[params5-expected5]`
  - `test_filter_paginates_with_name_sort`
  - `test_unsupported_filter_name_raises_value_error[tag]`
  - `test_unsupported_filter_name_raises_value_error[availability]`
  - `test_unsupported_filter_name_raises_value_error[source_id]`
  - `test_unsupported_filter_name_raises_value_error[rights_status]`
  - `test_unsupported_sort_key_raises_value_error`
  - `test_fetch_one_returns_row_or_none`
  - `test_workspaces_are_isolated`
  - `test_foreign_cursor_raises_value_error[updated_at-cursor0-asc]`
  - `test_foreign_cursor_raises_value_error[updated_at-cursor0-desc]`
  - `test_foreign_cursor_raises_value_error[updated_at-cursor1-asc]`
  - `test_foreign_cursor_raises_value_error[updated_at-cursor1-desc]`
  - `test_foreign_cursor_raises_value_error[updated_at-cursor2-asc]`
  - `test_foreign_cursor_raises_value_error[updated_at-cursor2-desc]`
  - `test_foreign_cursor_raises_value_error[updated_at-cursor3-asc]`
  - `test_foreign_cursor_raises_value_error[updated_at-cursor3-desc]`
  - `test_foreign_cursor_raises_value_error[name-cursor4-asc]`
  - `test_foreign_cursor_raises_value_error[name-cursor4-desc]`
  - `test_foreign_cursor_raises_value_error[name-cursor5-asc]`
  - `test_foreign_cursor_raises_value_error[name-cursor5-desc]`
  - `test_foreign_cursor_raises_value_error[name-cursor6-asc]`
  - `test_foreign_cursor_raises_value_error[name-cursor6-desc]`
  - `test_forbidden_fields_never_leave_the_service`
  - `test_service_source_is_read_only_and_layered`
- Trích assertion hoặc DID NOT RAISE đại diện cho từng nhóm:
  - Khóa dòng và danh sách rỗng: `AssertionError: assert [] == ['charlie', 'foxtrot', 'alpha', 'echo', 'delta', 'bravo']`
  - Trạng thái chưa có fingerprint: `KeyError: 'charlie'`
  - Phân trang mặc định: `assert 1 == 3 where 1 = len([Page(items=(), next_cursor=None)])`
  - Cursor lạ không ném lỗi: `Failed: DID NOT RAISE ValueError`
  - Ranh giới kiến trúc: `assert 'cp_media_assets' in '"""read-only service behind the dashboard media list...'`

## GREEN (bước 10)
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_4_media.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 0
- Dòng tổng kết nguyên văn: `60 passed in 1.01s`
- Toàn bộ 60 test passed, 0 failed, 0 skipped, 0 error.

## Lệnh kiểm khác
| Lệnh kiểm | Mục đích | Mã thoát |
| --- | --- | --- |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/media.py').read_text(encoding='utf-8').lower(); assert 'capabilityunavailableerror' in t and 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'from src.' not in t and 'os.environ' not in t and 'original_locator' not in t, 'RS-4'"` | Quét văn bản media.py kiểm tra chuỗi bắt buộc và cấm chuỗi cấm (bước 11) | 0 |
| `git diff --check` | Kiểm tra diff/khoảng trắng cuối dòng (bước 12) | 0 |

## Kết luận theo tiêu chí nghiệm thu
1. `MediaModuleService(connection_scope)` cung cấp đầy đủ `fetch_page`, `fetch_one` và `apply_update(*, request, item_id, expected_revision, changes, idempotency_key=None)` luôn ném `CapabilityUnavailableError('media')`. Câu lệnh SQL chạy trên `cp_media_assets`; id `media_asset_id`; sắp xếp theo `updated_at` hoặc `name` (`name` ánh xạ `media_asset_id`); lọc theo `kind` và `status` (cột). Dòng trả về có đúng 6 khóa `media_id`, `kind`, `rights_status` (← `rights.status`), `status`, `revision`, `updated_at`. Tài sản chưa có fingerprint có status `DISCOVERED`, có fingerprint có status `CATALOGED`.
2. Phân trang cursor keyset ≥2 trang cả `asc` và `desc` không trùng lặp và không sót dòng cho cả hai cách sắp xếp (`updated_at` và `name`), mặc định theo `desc` (mới nhất trước). `fetch_one` xử lý đủ ba trường hợp: trả dòng đúng, trả `None` khi không tồn tại hoặc id thuộc workspace khác. Cô lập workspace hoàn toàn cho danh sách, chi tiết và bộ lọc. Lọc theo `kind` và `status` khớp chính xác giá trị, giá trị lạ hoặc rỗng trả về rỗng. Bộ lọc lạ như `tag`, `availability`, `source_id`, `rights_status` hoặc sort lạ `revision` ném `ValueError`. Số hàng bảng nguồn `cp_media_assets` và `cp_media_provenance` không đổi sau các thao tác đọc và cả sau khi gọi `apply_update`. Cursor lạ/sai định dạng ném `ValueError`.
3. Không trả `fingerprint`, `discovery_ids`, provenance, `original_locator`. Canary trong provenance (`CANARY-LOCATOR`, `CANARY-DISCOVERY`, `CANARY-SOURCE-REF`, `CANARY-EVIDENCE`) và mọi fingerprint của các workspace không bao giờ xuất hiện trong `json.dumps(dòng)`. Mã nguồn `media.py` sạch hoàn toàn các chuỗi cấm (`insert into`, `update controlplane`, `delete from`, `from src.`, `os.environ`, `original_locator`) và chứa `capabilityunavailableerror`.

## Ghi chú
(a) Bảng `cp_media_assets` không có cột `kind` nên `kind` được trích xuất từ `payload->>'kind'`, `rights_status` từ `payload->'rights'->>'status'`;
(b) Sắp xếp theo `name` sử dụng keyset văn bản trên cột `media_asset_id` vì `common.keyset` chỉ hỗ trợ `timestamptz`. Cursor có `sort_value != row_id` bị từ chối bằng `ValueError` (fail-closed khi dùng nhầm cursor của kiểu sắp xếp khác);
(c) Bộ lọc `tag` và `availability` không còn được chấp nhận, ném `ValueError` fail-closed;
(d) Test ghim `updated_at` bằng một câu UPDATE trong seed CSDL để thứ tự và cặp trùng xác định, service hoàn toàn chỉ đọc không thao tác ghi;
(e) Tuyệt đối không ghi DSN, mật khẩu hay bất kỳ thông tin bí mật nào trong báo cáo, test hoặc mã nguồn.
