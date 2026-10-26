# RS-6: Service snapshots chỉ đọc (module D)

## Phạm vi
Triển khai đúng 3 tệp thuộc owned paths:
- `src/controlplane/infrastructure/read_screens/snapshots.py`
- `tests/integration/read_screens/test_rs_6_snapshots.py`
- `docs/delivery-evidence/rs-6/report.md`

## RED (bước 8)
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_6_snapshots.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe`)
- Mã thoát: 1 (khác 0)
- Dòng tổng kết nguyên văn: `36 failed, 5 passed in 0.93s`
- RED chạy trên stub rỗng trả `Page(items=(), next_cursor=None)` và `fetch_one` trả `None`, không có lỗi cú pháp, lỗi import hay lỗi thu thập test (collection error). 5 ca test pass tại thời điểm RED gồm: 4 ca kiểm thử bộ lọc với giá trị không tồn tại hoặc rỗng mong đợi danh sách rỗng (khớp với kết quả stub trả rỗng: `{'job_id': 'job-unknown'}`, `{'job_id': 'JOB-1'}`, `{'job_id': ''}`, `{'job_id': 'snap-a-1'}`) và 1 ca `test_reads_do_not_change_source_tables` do stub không thao tác CSDL nên số hàng bảng nguồn không đổi.
- Danh sách 36 test FAILED:
  - `test_rows_have_exact_keys_and_values`
  - `test_newest_analysis_revision_is_used`
  - `test_each_snapshot_is_one_row_even_with_several_analysis_revisions`
  - `test_missing_analysis_gives_null_model_and_prompt_ref`
  - `test_config_revision_ref_is_the_configuration_bundle_fingerprint`
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
  - `test_job_filter_is_exact_and_unknown_value_is_empty[params0-expected0]`
  - `test_job_filter_is_exact_and_unknown_value_is_empty[params1-expected1]`
  - `test_unsupported_filter_name_raises_value_error[video_job_ref]`
  - `test_unsupported_filter_name_raises_value_error[model]`
  - `test_unsupported_filter_name_raises_value_error[snapshot_id]`
  - `test_unsupported_filter_name_raises_value_error[workspace_id]`
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
  - Khóa dòng và danh sách rỗng: `AssertionError: assert [] == ['s5', 's4', 's3', 's2', 's1']`
  - Trạng thái chưa có trong hàng: `TypeError: 'NoneType' object is not subscriptable`
  - Phân trang mặc định: `assert 1 == 3 where 1 = len([Page(items=(), next_cursor=None)])`
  - Cursor lạ hoặc bộ lọc/sort lạ không ném lỗi: `Failed: DID NOT RAISE ValueError`
  - Ranh giới kiến trúc và quét nguồn thiếu SQL LATERAL: `assert 'left join lateral' in '"""read-only service behind the dashboard snapshots list (module d, rs-6): red stub."""...'`

## GREEN (bước 10)
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_6_snapshots.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 0
- Dòng tổng kết nguyên văn: `41 passed in 9.42s`
- Toàn bộ 41 test passed, 0 failed, 0 skipped, 0 error.

## Lệnh kiểm khác
| Lệnh kiểm | Mục đích | Mã thoát |
| --- | --- | --- |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/snapshots.py').read_text(encoding='utf-8').lower(); assert 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'from src.' not in t and 'os.environ' not in t and 'source_refs' not in t, 'RS-6'"` | Quét văn bản snapshots.py kiểm tra các chuỗi cấm (bước 11) | 0 |
| `git diff --check` | Kiểm tra diff/khoảng trắng cuối dòng (bước 12) | 0 |

## Kết luận theo tiêu chí nghiệm thu
1. `SnapshotModuleService(connection_scope)` cung cấp đầy đủ `fetch_page` và `fetch_one`. Câu lệnh SQL chạy trên `cp_production_snapshots s` kết hợp `LEFT JOIN LATERAL` lấy bản phân tích nội dung mới nhất (`ORDER BY a.created_at DESC, a.revision DESC, a.record_key DESC LIMIT 1`); id `snapshot_id`; sắp xếp theo `created_at`; lọc theo `job_id` (`s.payload->>'video_job_ref'`). Dòng trả về có đúng 6 khóa `snapshot_id`, `job_id`, `model`, `prompt_ref` (dạng `ref_id@revision_id`), `config_revision_ref` (= `configuration_bundle_fingerprint`), `created_at`. `model` và `prompt_ref` nhận giá trị `None` khi snapshot chưa có phân tích; snapshot có nhiều revision phân tích hiển thị chính xác model và prompt_ref của revision mới nhất.
2. Phân trang hai chiều không trùng lặp và không sót dòng cho cả hai chiều `asc` và `desc`, kể cả trường hợp hai bản ghi chia sẻ cùng giao dịch nên có `created_at` trùng nhau (s4 và s5) và bản ghi có nhiều revision phân tích (mỗi snapshot vẫn chỉ xuất hiện đúng một dòng). `fetch_one` xử lý đủ ba trường hợp: trả dòng đúng, trả `None` khi không tồn tại hoặc id thuộc workspace khác. Cô lập workspace hoàn toàn cho danh sách, chi tiết và bộ lọc (phân tích từ workspace khác trỏ snapshot của workspace hiện tại không làm rò rỉ dữ liệu). Lọc theo `job_id` khớp chính xác giá trị, giá trị lạ hoặc rỗng trả về rỗng. Bộ lọc không hỗ trợ hoặc sort lạ ném `ValueError` fail-closed. Số hàng bảng snapshot `cp_production_snapshots` và bảng phân tích `cp_content_analyses` không đổi sau các thao tác đọc. Cursor lạ hoặc sai định dạng ném `ValueError`.
3. Không trả `source_refs`, `index_revision_refs`, `recent_variant_exclusions`. Canary trong source_refs, index_revision_refs, recent_variant_exclusions, facts (`CANARY-SOURCE`, `CANARY-INDEX`, `CANARY-EXCLUSION`, `CANARY-FACT`) cùng `source_set_fingerprint` không bao giờ xuất hiện trong `json.dumps(dòng)`. Mã nguồn `snapshots.py` sạch hoàn toàn các chuỗi cấm (`insert into`, `update controlplane`, `delete from`, `from src.`, `os.environ`, `source_refs`).

## Ghi chú
(a) Bảng snapshot `cp_production_snapshots` và bảng phân tích `cp_content_analyses` đều append-only nên `created_at` lấy theo thời điểm giao dịch; s4 và s5 được seed cùng giao dịch để kiểm tra hòa thứ tự theo `snapshot_id`;
(b) Sắp xếp chỉ hỗ trợ `created_at`, sort lạ hoặc bộ lọc lạ ném `ValueError` fail-closed; bộ lọc chỉ hỗ trợ `job_id` (so khớp với `payload->>'video_job_ref'`);
(c) Tuyệt đối không ghi DSN, mật khẩu hay bất kỳ thông tin bí mật nào trong báo cáo, test hoặc mã nguồn.
