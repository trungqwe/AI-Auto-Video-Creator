# RS-5: Service artifacts chỉ đọc (module I)

## Phạm vi
Triển khai đúng 3 tệp thuộc owned paths:
- `src/controlplane/infrastructure/read_screens/artifacts.py`
- `tests/integration/read_screens/test_rs_5_artifacts.py`
- `docs/delivery-evidence/rs-5/report.md`

## RED (bước 10)
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_5_artifacts.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe`)
- Mã thoát: 1 (khác 0)
- Dòng tổng kết nguyên văn: `41 failed, 10 passed in 1.04s`
- RED chạy trên stub rỗng trả `Page(items=(), next_cursor=None)` và `fetch_one` trả `None`, không có lỗi cú pháp, lỗi import hay lỗi thu thập test (collection error). 10 ca test pass tại thời điểm RED gồm: 9 ca kiểm thử bộ lọc với giá trị không tồn tại hoặc rỗng mong đợi danh sách rỗng (khớp với kết quả stub trả rỗng: `{'state': 'DECLARED'}`, `{'state': 'MATERIALIZING'}`, `{'kind': 'subtitle', 'state': 'VERIFIED'}`, `{'kind': 'nope'}`, `{'kind': 'RENDERED_VIDEO'}`, `{'kind': ''}`, `{'state': 'verified'}`, `{'state': 'BOGUS'}`, `{'state': ''}`) và 1 ca `test_reads_do_not_change_source_tables` do stub không thao tác CSDL nên số hàng bảng nguồn không đổi.
- Danh sách 41 test FAILED:
  - `test_rows_have_exact_keys_and_values`
  - `test_each_version_is_one_row_even_with_several_locations`
  - `test_state_is_taken_from_the_most_recently_updated_location`
  - `test_default_direction_is_desc_and_explicit_direction_is_honoured`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[1-asc]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[1-desc]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[2-asc]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[2-desc]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[3-asc]`
  - `test_cursor_pagination_has_no_duplicates_or_gaps[3-desc]`
  - `test_default_pagination_is_newest_first`
  - `test_filtered_pagination_has_no_duplicates_or_gaps[asc]`
  - `test_filtered_pagination_has_no_duplicates_or_gaps[desc]`
  - `test_filters_are_exact_and_unknown_value_is_empty[params0-expected0]`
  - `test_filters_are_exact_and_unknown_value_is_empty[params1-expected1]`
  - `test_filters_are_exact_and_unknown_value_is_empty[params2-expected2]`
  - `test_filters_are_exact_and_unknown_value_is_empty[params5-expected5]`
  - `test_filters_are_exact_and_unknown_value_is_empty[params6-expected6]`
  - `test_filters_are_exact_and_unknown_value_is_empty[params7-expected7]`
  - `test_filters_are_exact_and_unknown_value_is_empty[params8-expected8]`
  - `test_filters_are_exact_and_unknown_value_is_empty[params9-expected9]`
  - `test_unsupported_filter_name_raises_value_error[owner_ref]`
  - `test_unsupported_filter_name_raises_value_error[artifact_kind]`
  - `test_unsupported_filter_name_raises_value_error[sha256_hash]`
  - `test_unsupported_filter_name_raises_value_error[artifact_id]`
  - `test_unsupported_filter_name_raises_value_error[location]`
  - `test_unsupported_sort_key_raises_value_error`
  - `test_fetch_one_returns_row_or_none`
  - `test_workspaces_are_isolated`
  - `test_foreign_cursor_raises_value_error[cursor0-asc]`
  - `test_foreign_cursor_raises_value_error[cursor0-desc]`
  - `test_foreign_cursor_raises_value_error[cursor1-asc]`
  - `test_foreign_cursor_raises_value_error[cursor1-desc]`
  - `test_foreign_cursor_raises_value_error[cursor2-asc]`
  - `test_foreign_cursor_raises_value_error[cursor2-desc]`
  - `test_foreign_cursor_raises_value_error[cursor3-asc]`
  - `test_foreign_cursor_raises_value_error[cursor3-desc]`
  - `test_foreign_cursor_raises_value_error[cursor4-asc]`
  - `test_foreign_cursor_raises_value_error[cursor4-desc]`
  - `test_forbidden_fields_never_leave_the_service`
  - `test_service_source_is_read_only_and_layered`
- Trích assertion hoặc DID NOT RAISE đại diện cho từng nhóm:
  - Khóa dòng và danh sách rỗng: `AssertionError: assert [] == ['v7', 'v6', 'v5', 'v4', 'v3', 'v2', 'v1']`
  - Trạng thái chưa có trong hàng: `KeyError: 'v1'`
  - Phân trang mặc định: `assert 1 == 4 where 1 = len([Page(items=(), next_cursor=None)])`
  - Cursor lạ hoặc bộ lọc/sort lạ không ném lỗi: `Failed: DID NOT RAISE ValueError`
  - Ranh giới kiến trúc và quét nguồn thiếu SQL LATERAL: `assert 'left join lateral' in '"""read-only service behind the dashboard artifacts list (module i, rs-5)...'`

## GREEN (bước 12)
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_5_artifacts.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 0
- Dòng tổng kết nguyên văn: `51 passed in 0.74s`
- Toàn bộ 51 test passed, 0 failed, 0 skipped, 0 error.

## Lệnh kiểm khác
| Lệnh kiểm | Mục đích | Mã thoát |
| --- | --- | --- |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/artifacts.py').read_text(encoding='utf-8').lower(); assert 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'from src.' not in t and 'os.environ' not in t and 'provider_object_ref' not in t and 'logical_locator' not in t, 'RS-5'"` | Quét văn bản artifacts.py kiểm tra các chuỗi cấm (bước 13) | 0 |
| `git diff --check` | Kiểm tra diff/khoảng trắng cuối dòng (bước 15) | 0 |

## Kết luận theo tiêu chí nghiệm thu
1. `ArtifactModuleService(connection_scope)` cung cấp đầy đủ `fetch_page` và `fetch_one`. Câu lệnh SQL chạy trên `cp_artifact_versions v` kết hợp `LEFT JOIN LATERAL` lấy `state` của vị trí mới nhất (`ORDER BY l.updated_at DESC, l.location_id DESC LIMIT 1`); id `artifact_version_id::text`; sắp xếp theo `created_at`; lọc theo `kind` (`v.artifact_kind`) và `state` (`loc.state`). Dòng trả về có đúng 5 khóa `artifact_id`, `version` (= `artifact_version_id`), `state` (null khi chưa có vị trí), `kind`, `created_at`.
2. Phân trang hai chiều không trùng lặp và không sót dòng cho cả hai chiều `asc` và `desc`, kể cả trường hợp hai bản ghi chia sẻ cùng giao dịch nên có `created_at` trùng nhau (v6 và v7) và bản ghi có nhiều vị trí lưu trữ. `fetch_one` xử lý đủ ba trường hợp: trả dòng đúng, trả `None` khi không tồn tại hoặc id thuộc workspace khác. Cô lập workspace hoàn toàn cho danh sách, chi tiết và bộ lọc. Lọc theo `kind` và `state` khớp chính xác giá trị, lọc `state` theo vị trí cập nhật gần nhất chứ không lọc theo vị trí cũ, giá trị lạ hoặc rỗng trả về rỗng. Bộ lọc không hỗ trợ hoặc sort lạ ném `ValueError` fail-closed. Số hàng bảng bản `cp_artifact_versions` và bảng vị trí `cp_artifact_locations` không đổi sau các thao tác đọc. Cursor lạ hoặc sai định dạng ném `ValueError`.
3. Không trả `sha256_hash`, `owner_ref`, `provider_object_ref`, `logical_locator`, `verification_evidence_ref`. Canary trong metadata và vị trí (`CANARY-LOCATOR`, `CANARY-OBJECT`, `CANARY-OWNER`, `CANARY-EVIDENCE`) cùng mọi hash, owner_ref, location_id không bao giờ xuất hiện trong `json.dumps(dòng)`. Mã nguồn `artifacts.py` sạch hoàn toàn các chuỗi cấm (`insert into`, `update controlplane`, `delete from`, `from src.`, `os.environ`, `provider_object_ref`, `logical_locator`).

## Ghi chú
(a) Bảng bản artifact `cp_artifact_versions` có trigger bất biến nên `created_at` lấy theo thời điểm giao dịch; test seed mỗi bản trong giao dịch riêng, hai bản v6 và v7 được seed cùng giao dịch để kiểm tra hòa thứ tự theo `version` id (uuid text);
(b) `updated_at` của vị trí được ghim bằng một câu `UPDATE` trong seed CSDL để thứ tự thời gian xác định, service hoàn toàn chỉ đọc không thao tác ghi;
(c) Sắp xếp chỉ hỗ trợ `created_at`, sort hoặc bộ lọc lạ ném `ValueError` fail-closed;
(d) Tuyệt đối không ghi DSN, mật khẩu hay bất kỳ thông tin bí mật nào trong báo cáo, test hoặc mã nguồn.
