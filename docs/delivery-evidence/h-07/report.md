# Báo cáo bằng chứng H-07

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `d6f0c277e1d921c36e0ba0553aca131ca6d991da`
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-07 trong `docs/implementation/h/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_problem_detail.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 6)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `34 failed, 3 passed in 0.57s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/control_ui/test_h_problem_detail.py::test_specs_cover_exactly_four_codes_with_expected_values - AssertionError: assert [] == ['VALIDATION_..., 'NOT_FOUND']`
  - `FAILED tests/unit/control_ui/test_h_problem_detail.py::test_problem_body_has_exact_ten_keys[VALIDATION_FAILED] - NotImplementedError: H-07 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_problem_detail.py::test_technical_detail_ref_added_only_when_present[VALIDATION_FAILED] - NotImplementedError: H-07 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_problem_detail.py::test_field_errors_are_copied_and_default_is_fresh - NotImplementedError: H-07 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_problem_detail.py::test_non_string_field_errors_are_rejected[bad0] - NotImplementedError: H-07 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_problem_detail.py::test_unknown_code_is_rejected[X] - NotImplementedError: H-07 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_problem_detail.py::test_problem_response_uses_state_correlation_id_and_table[VALIDATION_FAILED] - NotImplementedError: H-07 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_problem_detail.py::test_key_set_matches_sse_presenter_problem - NotImplementedError: H-07 RED skeleton`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 3 test kiểm tra chữ ký và cấu trúc AST (`test_signatures_cannot_take_detail_from_exception`, `test_module_source_has_no_exception_or_traceback_handling`, `test_modules_directory_has_no_init_file`) đã PASS ngay từ đầu. Tất cả 34 test thất bại đều là `NotImplementedError` do khung skeleton chưa cài logic hoặc `AssertionError` khi kiểm tra hằng số rỗng.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_problem_detail.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic ở bước 8)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `37 passed in 0.28s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/api/routes/modules/problem_detail.py`: Module mới khai báo bảng `PROBLEM_SPECS` cho đúng 4 mã lỗi RFC 7807 (`VALIDATION_FAILED`, `FORBIDDEN_FIELD`, `REVISION_CONFLICT`, `NOT_FOUND`) với detail tiếng Việt đầy đủ dấu, hàm kiểm tra an toàn `_checked_field_errors`, hàm xây dựng payload `problem_body` đảm bảo đúng thứ tự 10 khóa cơ sở khớp `SseStreamPresenter._problem` (thêm khóa thứ 11 `technical_detail_ref` khi có giá trị), và hàm tạo `JSONResponse` `problem_response` với `media_type='application/problem+json'`, status code theo bảng và correlation_id từ `request.state.correlation_id`.
  - `tests/unit/control_ui/test_h_problem_detail.py`: Bộ kiểm thử đơn vị gồm 37 test cases kiểm tra độ bao phủ 4 mã lỗi trong `PROBLEM_SPECS`, số lượng và thứ tự 10 khóa cơ sở của `problem_body`, việc thêm `technical_detail_ref`, tính nguyên tử và sao chép an toàn của `field_errors`, từ chối `field_errors` không phải chuỗi, từ chối mã lỗi lạ trước khi kiểm tra `field_errors`, các thuộc tính HTTP của `problem_response`, yêu cầu bắt buộc `correlation_id` trong state, chống rò rỉ traceback trong payload JSON, chữ ký hàm keyword-only, không sử dụng `str(exc)`/`traceback`/`except` trong mã nguồn, kiểm tra thư mục `modules` không có `__init__.py`, và đối chiếu regex bộ khóa khớp hoàn toàn `SseStreamPresenter._problem`.
  - `docs/delivery-evidence/h-07/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/control_ui/test_h_problem_detail.py -q -p no:cacheprovider` | 0 | `37 passed in 0.28s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `PROBLEM_SPECS` là dict thường giống `_PROBLEM_SPECS` của `stream.py`.
2. Kiểm tra mã lỗi hợp lệ trước khi kiểm tra `field_errors`.
3. `field_errors` phải là Mapping có khóa và giá trị đều là str, được sao chép (`dict(field_errors)`) để không chia sẻ tham chiếu mutable.
4. `technical_detail_ref` chỉ thêm vào body khi có giá trị khác rỗng (`if technical_detail_ref:`).
5. Thiếu `request.state.correlation_id` thì phát sinh lỗi `AttributeError`, không đặt giá trị mặc định để đảm bảo bắt buộc có correlation_id.

## Ánh xạ phản ví dụ

- `detail lấy từ str(exc)`: Đã giải quyết và loại trừ qua `test_signatures_cannot_take_detail_from_exception` (chữ ký hàm không nhận exception/detail ngoài) và `test_module_source_has_no_exception_or_traceback_handling` (kiểm tra AST mã nguồn không có khối `except`, không import `traceback`, không gọi `str(...)`).
- `thiếu correlation_id`: Đã giải quyết và loại trừ qua `test_problem_response_requires_correlation_id_in_state` (truy cập trực tiếp `request.state.correlation_id` không default) và tham số `correlation_id` keyword-only bắt buộc trong `problem_body`.
- `status không khớp bảng`: Đã giải quyết và loại trừ qua `test_problem_body_has_exact_ten_keys` và `test_problem_response_uses_state_correlation_id_and_table` (status code lấy trực tiếp từ `PROBLEM_SPECS`).
- `field_errors lồng object có thể nhúng stack trace`: Đã giải quyết và loại trừ qua `test_non_string_field_errors_are_rejected` (từ chối dict lồng nhau, kiểu int, None, list, bytes, v.v., phát sinh `ValueError('field_errors_must_be_strings')`).

## coveredIds

- `CT-API-001`
- `CT-API-010`
- `QR-UX-004`

## Danh sách chờ user (pendingUserCheckpoint)

- `USER-CKPT-D9-D10`
- `CP7 tài nguyên thật (D5)`

## Giới hạn

- Không sửa `src/controlplane/api/sse/stream.py`, `pyproject.toml`, `uv.lock`.
- Không thêm `__init__.py` trong `src/controlplane/api/routes/modules/` hay trong thư mục `tests/`.
- Không chạy full suite, `tests/m1`, `tests/m2`.
- Chỉ dùng thư viện `fastapi`/`starlette` đã có sẵn trong runtime khoá.
- Không gọi dịch vụ thật.
