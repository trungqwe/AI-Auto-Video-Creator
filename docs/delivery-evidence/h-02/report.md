# Báo cáo bằng chứng H-02

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `7cdcbf1ee151fe8da9747c90f2079ed757c67224`
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-02 trong docs/implementation/h/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_list_query.py -q -p no:cacheprovider`
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `114 failed, 1 passed in 1.02s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/control_ui/test_h_list_query.py::test_defaults_without_params - NotImplementedError: H-02 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_list_query.py::test_limit_accepts_ascii_digits_within_range[1-1] - NotImplementedError: H-02 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_list_query.py::test_cursor_round_trip[a-b] - NotImplementedError: H-02 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_list_query.py::test_build_page_with_extra_row_has_cursor_of_last_item - NotImplementedError: H-02 RED skeleton`
- Xác nhận: Toàn bộ 114 lỗi là `NotImplementedError` từ khung RED skeleton ban đầu; 1 test pass ngay từ đầu là `test_module_imports_only_pure_stdlib`; hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_list_query.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `115 passed in 0.11s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/application/projections/list_query.py`: Module thuần túy chuẩn stdlib định nghĩa `ListQueryError` (với các mã lỗi `limit_invalid`, `sort_not_allowed`, `filter_not_allowed`, `cursor_invalid`), hai frozen dataclass `ListQuery` và `Page`, các hàm `encode_cursor`, `decode_cursor`, `parse_list_query` và `build_page`. Module không truy cập cơ sở dữ liệu, không đọc đồng hồ, không dùng phụ thuộc ngoài.
  - `tests/unit/control_ui/test_h_list_query.py`: Bộ kiểm thử đơn vị toàn diện với 115 test cases bao phủ toàn bộ parsing limit (chỉ chấp nhận chữ số ASCII 0-9, từ chối số âm, tràn trần, ký tự Unicode toàn chiều rộng), whitelist sort và direction, whitelist filter (từ chối workspace_id/actor_id kể cả khi nằm trong allowed_filters), round-trip cursor base64url JSON với chuỗi Unicode tiếng Việt, giới hạn độ dài cursor 512 ký tự, build_page keyset pagination và kiểm tra AST chỉ import stdlib thuần túy.
  - `docs/delivery-evidence/h-02/report.md`: Báo cáo bằng chứng nghiệm thu lưu lại toàn bộ môi trường, kết quả RED, GREEN, các quyết định mặc định và ánh xạ phản ví dụ.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/control_ui/test_h_list_query.py -q -p no:cacheprovider` | 0 | `115 passed in 0.11s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `ListQuery.cursor` là tuple `(sort_value, row_id)` đã giải mã, không giữ chuỗi thô.
2. `filters` là tuple các cặp `(tên, giá trị)` được sắp xếp theo thứ tự bảng chữ cái của tên trường filter.
3. `sort` mặc định là phần tử đầu tiên của `allowed_sorts`, `direction` mặc định là `asc`; hướng sắp xếp sai giá trị được báo lỗi `sort_not_allowed` với `field="direction"`.
4. Tham số lạ hoặc giá trị filter không phải chuỗi là `filter_not_allowed`; các trường danh tính `workspace_id` và `actor_id` luôn bị từ chối kể cả khi người gọi cấu hình nằm trong `allowed_filters`.
5. `limit` chấp nhận chuỗi số có số 0 đứng đầu (ví dụ `'007'` -> `7`), chuỗi dài hơn 18 ký tự bị từ chối ngay lập tức để chống DoS trước khi ép kiểu số nguyên.
6. `encode_cursor` ném `ValueError` khi giá trị không phải chuỗi hoặc độ dài token kết quả vượt quá 512 ký tự.
7. `build_page` cắt mềm khi nhận nhiều hơn `limit + 1` hàng đầu vào (chỉ lấy đúng `limit` phần tử đầu tiên cho trang hiện tại).

## Ánh xạ phản ví dụ

- Cursor offset số nguyên -> `test_cursor_is_not_an_integer_offset` và `test_invalid_cursor_param_is_rejected`
- Limit vượt trần được chấp nhận -> `test_limit_rejects_invalid_values` và `test_max_limit_comes_from_caller`
- Workspace ID tin từ query -> `test_identity_filters_are_never_allowed` và `test_query_never_carries_identity`
- Trang cuối vẫn có next_cursor -> `test_build_page_without_extra_row_has_no_cursor` và `test_keyset_walk_visits_every_row_once_and_last_page_has_no_cursor`
- Chữ số Unicode được coi là limit hợp lệ -> `test_limit_rejects_invalid_values`

## coveredIds

- `CT-API-001`
- `CT-API-002`
- `QR-PERF-005`

## Giới hạn

- Không chạy full suite, không chạy tests/m1, tests/m2.
- Không đọc DB hay đồng hồ hệ thống.
- Chỉ sử dụng thư viện tiêu chuẩn (stdlib).
- Cursor không ràng buộc cứng với `sort_key`/`direction` ở tầng projection thuần túy, do đó tầng gọi H-04 phải truyền đúng cặp sort tương ứng khi xây dựng câu lệnh SQL.
- Không gọi dịch vụ thật.
