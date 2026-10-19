# Báo cáo bằng chứng H-09

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `1602d70f0336bccf043242bb76a0bb1d57afd13a`
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-09 trong `docs/implementation/h/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_metadata_update.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 7)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `65 failed, 2 passed, 1 skipped, 2 warnings in 0.90s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/control_ui/test_h_metadata_update.py::test_forbidden_fields_constant_is_exact_frozenset - AssertionError: assert frozenset() == frozenset({'a...t_text', ...})`
  - `FAILED tests/unit/control_ui/test_h_metadata_update.py::test_allowed_fields_intersecting_forbidden_raise_at_build[allowed0] - NotImplementedError: H-09 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_metadata_update.py::test_valid_patch_calls_apply_update_once_with_int_revision - NotImplementedError: H-09 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_metadata_update.py::test_missing_if_match_is_422_and_not_applied - NotImplementedError: H-09 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_metadata_update.py::test_invalid_if_match_is_422_and_not_applied[abc] - NotImplementedError: H-09 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_metadata_update.py::test_missing_or_blank_idempotency_key_is_422_and_not_applied[None] - NotImplementedError: H-09 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_metadata_update.py::test_non_object_or_empty_body_is_422_and_not_applied[] - NotImplementedError: H-09 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_metadata_update.py::test_revision_conflict_maps_to_409_problem - NotImplementedError: H-09 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_metadata_update.py::test_module_source_is_scoped_and_has_no_blanket_except - AssertionError: assert 'controlplane.api.routes.modules.problem_detail' in {'__future__'}`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 2 test (`test_revision_conflict_error_is_plain_exception` và `test_modules_directory_has_no_init_file`) đã PASS ngay từ đầu. Tất cả 65 test thất bại đều do `NotImplementedError` từ khung skeleton chưa cài logic hoặc `AssertionError` khi kiểm tra hằng số rỗng và cấu trúc import ban đầu.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_metadata_update.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic ở bước 9)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `83 passed, 2 warnings in 0.95s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/api/routes/modules/metadata_update.py`: Module mới cung cấp router cập nhật metadata theo allowlist, định nghĩa tập `FORBIDDEN_METADATA_FIELDS` gồm 8 trường cấm (`article_body`, `body`, `script`, `script_text`, `event_relation`, `event_links`, `secret`, `secret_value`), lớp ngoại lệ `RevisionConflictError`, hàm `build_metadata_router` trả về `APIRouter` với đúng một route `PATCH {prefix}/{item_id}`, kiểm tra định dạng `prefix` bắt đầu `/v1/`, kiểm tra giao tập cấm khi dựng router, trích xuất và xác thực `Idempotency-Key` (không rỗng, đơn nhất), `If-Match` (chuỗi chữ số ASCII tối đa 18 ký tự), body JSON object không rỗng, kiểm tra các khóa ngoài `allowed_fields` trả về `422 FORBIDDEN_FIELD`, bọc hàm `apply_update` qua `run_in_threadpool`, xử lý xung đột phiên bản trả về `409 REVISION_CONFLICT` qua RFC 7807 problem details của H-07, và để các lỗi khác lan ra ngoài.
  - `tests/unit/control_ui/test_h_metadata_update.py`: Bộ kiểm thử đơn vị gồm 83 test cases bao phủ toàn diện: hằng số tập cấm và lớp ngoại lệ, từ chối cho phép trường cấm khi khởi tạo router, thực thi PATCH hợp lệ gọi `apply_update` đúng 1 lần với revision kiểu `int`, trích xuất số nguyên từ `If-Match`, từ chối khi thiếu/sai/trùng lặp `If-Match`, từ chối khi thiếu/rỗng/trùng lặp `Idempotency-Key`, từ chối body không phải JSON object hoặc rỗng, gom các lỗi kiểm thực vào cùng một phản hồi `VALIDATION_FAILED`, chặn trường cấm với `FORBIDDEN_FIELD`, ánh xạ `RevisionConflictError` sang mã 409, đảm bảo lỗi hệ thống khác lan ra ngoài, ngăn ghi đè khi revision cũ, chuyển tiếp nguyên vẹn `Idempotency-Key`, trả về 405 cho các HTTP method khác (GET, PUT, DELETE, POST), kiểm tra tiền tố prefix bắt buộc bắt đầu `/v1/`, xác thực router chỉ có duy nhất một route PATCH, phân tích AST đảm bảo không có blanket except, và xác nhận thư mục `modules` không chứa `__init__.py`.
  - `docs/delivery-evidence/h-09/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/control_ui/test_h_metadata_update.py -q -p no:cacheprovider` | 0 | `83 passed, 2 warnings in 0.95s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `RevisionConflictError` định nghĩa riêng trong module theo spec; adapter ở composition root phải ném lớp này hoặc để `main.py` ánh xạ lỗi miền `controlplane.domain.concurrency.RevisionConflictError` (open item `YC-HT-H-02`).
2. `apply_update` đồng bộ, chạy qua `run_in_threadpool`.
3. `If-Match` chỉ nhận 1-18 chữ số ASCII, header trùng lặp hoặc rỗng là 422.
4. JSON hỏng hoặc không phải object hoặc rỗng là 422 `VALIDATION_FAILED`, mọi lỗi header/body được gom vào một `field_errors` theo thứ tự `Idempotency-Key`, `If-Match`, `body`.
5. Lỗi header/body kiểm trước `FORBIDDEN_FIELD`.
6. `field_errors` không chứa giá trị người dùng gửi.
7. Không thêm `__init__.py` (D8-H-07).

## Ánh xạ phản ví dụ

- Cho phép sửa script hoặc article body: Đã loại trừ qua `test_forbidden_key_is_422_forbidden_field_and_not_applied` và `test_allowed_fields_intersecting_forbidden_raise_at_build`.
- If-Match bị bỏ qua: Đã loại trừ qua `test_missing_if_match_is_422_and_not_applied` và `test_invalid_if_match_is_422_and_not_applied`.
- Ghi âm thầm khi revision cũ: Đã loại trừ qua `test_stale_if_match_is_conflict_and_does_not_write`.
- Thiếu Idempotency-Key vẫn ghi: Đã loại trừ qua `test_missing_or_blank_idempotency_key_is_422_and_not_applied`.

## coveredIds

- `CT-API-001`
- `CT-API-003`
- `CT-API-004`
- `CT-API-009`

## Danh sách chờ user (pendingUserCheckpoint)

- `USER-CKPT-D9-D10`
- `CP7 tài nguyên thật (D5)`

## Giới hạn

- Không sửa src ngoài `metadata_update.py`.
- Không thêm `__init__.py` trong `src/controlplane/api/routes/modules/` hay `tests/`.
- Không chạy full suite, `tests/m1`, `tests/m2`.
- Không thêm thư viện mới.
- Không gọi dịch vụ thật.
