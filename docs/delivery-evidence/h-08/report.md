# Báo cáo bằng chứng H-08

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `210ac3386e5e5fc4c6623e26e5e127eea34a8ab5`
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-08 trong `docs/implementation/h/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_read_only_listing.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `41 failed, 2 passed, 2 warnings in 0.71s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/control_ui/test_h_read_only_listing.py::test_valid_query_calls_fetch_page_once_with_identity_workspace - NotImplementedError: H-08 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_read_only_listing.py::test_default_query_uses_defaults_and_null_cursor - NotImplementedError: H-08 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_read_only_listing.py::test_cursor_param_is_decoded_into_query - NotImplementedError: H-08 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_read_only_listing.py::test_identity_fields_in_query_are_rejected_and_fake_not_called[params0] - NotImplementedError: H-08 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_read_only_listing.py::test_workspace_filter_is_rejected_even_when_listed_as_allowed - NotImplementedError: H-08 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_read_only_listing.py::test_invalid_list_params_return_422_problem_without_calling_fake[params0-limit-limit_invalid] - NotImplementedError: H-08 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_read_only_listing.py::test_every_route_is_get_only[False] - NotImplementedError: H-08 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_read_only_listing.py::test_write_methods_return_405_without_calling_fakes[POST] - NotImplementedError: H-08 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_read_only_listing.py::test_unversioned_prefix_is_rejected[/api/x] - NotImplementedError: H-08 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_read_only_listing.py::test_module_source_has_no_write_route_body_access_or_broad_except - AssertionError: assert 0 == 2`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 2 test kiểm tra chữ ký hàm và cấu trúc thư mục không có __init__.py (`test_builder_signature_is_keyword_only`, `test_modules_directory_has_no_init_file`) đã PASS ngay từ đầu. 41 test thất bại đều là `NotImplementedError: H-08 RED skeleton` do khung skeleton chưa cài logic hoặc `AssertionError: assert 0 == 2` do chưa đăng ký route nào.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_read_only_listing.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic ở bước 8)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `43 passed, 2 warnings in 0.70s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/api/routes/modules/read_only_listing.py`: Module mới cung cấp hàm `build_listing_router` tạo APIRouter chỉ đọc (GET) cho route module. Kiểm tra prefix phải bắt đầu bằng `/v1/` (phát sinh `ValueError('prefix_must_be_versioned')` nếu sai), thẩm định cấu hình sớm bằng `parse_list_query({}, **limits)`, workspace_id luôn lấy từ `request.state.identity['workspace_id']` (tuyệt đối không đọc từ query hay body), chuyển đổi ngoại lệ `ListQueryError` thành phản hồi 422 RFC 7807 qua `problem_response` của H-07 với `field_errors={exc.field: exc.code}`, đăng ký endpoint GET item khi có `fetch_one` (trả 404 NOT_FOUND problem_response nếu `fetch_one` trả về None).
  - `tests/unit/control_ui/test_h_read_only_listing.py`: Bộ kiểm thử đơn vị gồm 43 test cases bao phủ: truy vấn hợp lệ với các tham số phân trang/lọc/sắp xếp chỉ gọi `fetch_page` một lần với workspace của identity, truy vấn mặc định, giải mã con trỏ cursor, trang rỗng, từ chối tham số identity trong query (như `workspace_id`, `actor_id`) và bộ lọc `workspace_id` kể cả khi nằm trong allowed_filters, từ chối các tham số query không hợp lệ trả về 422 `VALIDATION_FAILED` mà không gọi hàm giả, đảm bảo mọi route chỉ chấp nhận GET (trừ HEAD do Starlette thêm) và trả 405 cho POST/PUT/PATCH/DELETE, xử lý `fetch_one` trả đối tượng hoặc 404 có thân problem detail, không đăng ký route item nếu không có `fetch_one`, không rò rỉ chi tiết ngoại lệ trong lỗi 500, từ chối prefix không có tiền tố phiên bản `/v1/`, kiểm tra lỗi cấu hình lúc build router, xác nhận chữ ký keyword-only, xác nhận thư mục `modules` không chứa `__init__.py`, và kiểm tra cây cú pháp AST không có route ghi, không đọc request body và chỉ xử lý khối except `ListQueryError`.
  - `docs/delivery-evidence/h-08/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/control_ui/test_h_read_only_listing.py -q -p no:cacheprovider` | 0 | `43 passed, 2 warnings in 0.70s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Chữ ký `fetch_one` là `fetch_one(request, workspace_id, item_id)` trả `Mapping[str, object] | None`.
2. Chỉ báo lỗi `ListQueryError` đầu tiên dưới dạng `{field: code}` trong `field_errors`.
3. Cấu hình sai (`default_limit`, `max_limit`, `allowed_sorts`, `allowed_filters`) phát sinh `ValueError` ngay lúc build router thông qua `parse_list_query({}, **limits)` chứ không đợi tới lúc có request.
4. Tham số query lặp thì giá trị cuối thắng (`dict(request.query_params)`).
5. Router không bắt ngoại lệ ngoài `ListQueryError`, lỗi khác thành 500 do tầng middleware của ứng dụng xử lý, thân 500 không chứa chi tiết ngoại lệ hay traceback.

## Ánh xạ phản ví dụ

- `tin workspace từ query`: Đã loại trừ qua `test_identity_fields_in_query_are_rejected_and_fake_not_called` và `test_workspace_filter_is_rejected_even_when_listed_as_allowed`.
- `có route ghi`: Đã loại trừ qua `test_every_route_is_get_only`, `test_write_methods_return_405_without_calling_fakes` và `test_module_source_has_no_write_route_body_access_or_broad_except` (quét AST).
- `trả 200 thân trống khi không tìm thấy`: Đã loại trừ qua `test_fetch_one_none_returns_404_problem_with_body` (trả 404 có thân `application/problem+json`).
- `lỗi 500 lộ ngoại lệ`: Đã loại trừ qua `test_fetch_page_exception_returns_500_without_leaking_detail` và `test_fetch_one_exception_returns_500_without_leaking_detail`.

## coveredIds

- `CT-API-001`
- `CT-API-002`
- `CT-API-010`

## Danh sách chờ user (pendingUserCheckpoint)

- `USER-CKPT-D9-D10`
- `CP7 tài nguyên thật (D5)`

## Giới hạn

- Không thêm `__init__.py` trong `src/controlplane/api/routes/modules/` hay trong thư mục `tests/`.
- Không sửa `main.py`, `control.py`, `pyproject.toml`, lockfile.
- Việc đấu nối router vào composition root thuộc trách nhiệm của YC-HT-H-02.
- Không chạy full suite, `tests/m1`, `tests/m2`.
- Không gọi dịch vụ thật.