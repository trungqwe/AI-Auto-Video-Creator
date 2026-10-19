# Báo cáo bằng chứng H-01

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `7cdcbf1ee151fe8da9747c90f2079ed757c67224`
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-01 trong docs/implementation/h/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_operation_view_model.py -q -p no:cacheprovider` (chạy trên khung RED chưa có logic ở bước 4)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `54 failed, 1 passed in 0.60s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/control_ui/test_h_operation_view_model.py::test_status_constants - AssertionError: assert () == ('accepted', 'running', 'waiting', 'outcome_unknown', 'succeeded', 'failed')`
  - `FAILED tests/unit/control_ui/test_h_operation_view_model.py::test_status_matrix[PREPARED-None-accepted] - NotImplementedError: H-01 RED stub: build_operation_view`
  - `FAILED tests/unit/control_ui/test_h_operation_view_model.py::test_status_matrix[STARTED-None-running] - NotImplementedError: H-01 RED stub: build_operation_view`
  - `FAILED tests/unit/control_ui/test_h_operation_view_model.py::test_status_matrix[STARTED-wait_reason2-waiting] - NotImplementedError: H-01 RED stub: build_operation_view`
  - `FAILED tests/unit/control_ui/test_h_operation_view_model.py::test_status_matrix[SUCCEEDED-None-succeeded] - NotImplementedError: H-01 RED stub: build_operation_view`
  - `FAILED tests/unit/control_ui/test_h_operation_view_model.py::test_status_matrix[FAILED-None-failed] - NotImplementedError: H-01 RED stub: build_operation_view`
  - `FAILED tests/unit/control_ui/test_h_operation_view_model.py::test_status_matrix[OUTCOME_UNKNOWN-None-outcome_unknown] - NotImplementedError: H-01 RED stub: build_operation_view`
  - `FAILED tests/unit/control_ui/test_h_operation_view_model.py::test_status_values_match_contract_table - AssertionError: assert ['accepted', 'running', 'waiting', 'outcome_unknown', 'succeeded', 'failed'] == []`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, SyntaxError hay lỗi collection. 1 test tĩnh kiểm tra ranh giới import (test_module_has_no_clock_or_io_imports) đã PASS ngay từ đầu. Tất cả 54 test thất bại đều do `NotImplementedError` từ stub 'H-01 RED stub: ...' hoặc `AssertionError` do các hằng số cố ý để rỗng ở khung RED.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_operation_view_model.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic ở bước 6)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `55 passed in 0.08s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/application/projections/operation_view_model.py`: Module thuần read model cho OperationView (CT-API-007, luật D8-H-04). Định nghĩa `OPERATION_STATUSES` (6 giá trị), `TERMINAL_STATUSES` ('succeeded', 'failed'), `dataclass(frozen=True) OperationViewModel` gồm đúng 10 trường dữ liệu và phương thức `to_dict()` trả dict 10 khóa theo đúng thứ tự hợp đồng; hàm thuần `build_operation_view` ánh xạ trạng thái qua `map_operation_view` và áp dụng nghiêm ngặt các luật thẩm định D8-H-04.
  - `tests/unit/control_ui/test_h_operation_view_model.py`: Bộ kiểm thử đơn vị toàn diện gồm 19 nhóm test bao gồm kiểm tra hằng số trạng thái, ma trận 10 tổ hợp giữa 5 OperationState và wait_reason, độ phủ đủ 6 trạng thái view, phân biệt rõ waiting với running và outcome_unknown với failed, thẩm định chặt chẽ wait_reason và finished_at, kiểm tra problem hợp lệ và từ chối khi sai trạng thái, phát hiện và ngăn chặn rò rỉ stack trace/traceback/secret/internal detail ở mọi độ sâu cấu trúc, tính bất biến frozen của view, thứ tự khóa của to_dict, đối chiếu regex trực tiếp với bảng hợp đồng CT-API-007 và kiểm tra AST không có import đồng hồ hay I/O.
  - `docs/delivery-evidence/h-01/report.md`: Báo cáo bằng chứng nghiệm thu ghi lại chi tiết môi trường, RED, GREEN, thay đổi, bảng kết quả lệnh kiểm, quyết định D8, ánh xạ phản ví dụ, coveredIds, pendingUserCheckpoint và giới hạn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/control_ui/test_h_operation_view_model.py -q -p no:cacheprovider` | 0 | `55 passed in 0.08s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

- Áp dụng quyết định kiến trúc D8-H-04 cho mô hình OperationView.
- Mã lỗi ValueError `invalid_problem` là GIẢ ĐỊNH do slice H-01 lựa chọn khi problem thiếu một trong các khóa bắt buộc (`code`, `title`, `status`, `correlation_id`) hoặc có kiểu dữ liệu không phải dict.
- Kiểm tra khóa cấm (`stack_trace`, `traceback`, `secret_value`, `internal_detail`) so khớp nguyên khóa không phân biệt hoa thường ở mọi cấp độ lồng nhau (dict, list, tuple), không so khớp chuỗi con trong tên khóa; riêng chuỗi `Traceback (most recent call last)` bị cấm xuất hiện trong bất kỳ giá trị chuỗi nào của problem.
- Trạng thái `waiting` được suy ra trực tiếp từ kết quả của `map_operation_view(execution_state, wait_reason)`: nếu status là `waiting` mà `wait_reason` rỗng hoặc sai định dạng (không phải dict có khóa `code` chuỗi không rỗng) thì báo `invalid_wait_reason`; nếu status khác `waiting` mà có `wait_reason` thì báo `unexpected_wait_reason`.
- Trường `finished_at` ở các trạng thái terminal (`succeeded`, `failed`) nếu mang giá trị rỗng (`None` hoặc `""`) được tính là thiếu (`missing_finished_at`); nếu xuất hiện ở các trạng thái chưa terminal (`accepted`, `running`, `waiting`, `outcome_unknown`) thì báo `unexpected_finished_at`.

## Ánh xạ phản ví dụ

- Waiting hiển thị là running -> Loại trừ bởi test `test_waiting_is_not_running`.
- Outcome_unknown bị gộp vào failed -> Loại trừ bởi test `test_outcome_unknown_is_not_failed`.
- Problem mang stack trace hoặc secret -> Loại trừ bởi `test_problem_forbidden_key_top_level`, `test_problem_forbidden_key_nested`, `test_problem_traceback_string` và `test_unsafe_error_does_not_leak_value`.
- Finished_at xuất hiện khi còn running -> Loại trừ bởi test `test_unexpected_finished_at`.
- To_dict thiếu hoặc thừa khóa so với contract -> Loại trừ bởi test `test_to_dict_keys_match_contract_table` và `test_to_dict_returns_ten_keys_in_order`.

## coveredIds

- `CT-API-007`
- `QR-UX-003`
- `TST-SEC-INV-012`

## Danh sách chờ user (pendingUserCheckpoint)

- `PUC-H-03`: Xác nhận enum và mức severity GIẢ ĐỊNH D8-H-04.
- `USER-CKPT-D9-D10`: User duyệt danh mục thư viện đề xuất và runtime tái lập.
- `CP7 tài nguyên thật (D5)`: Quyền truy cập tài nguyên thật và secret broker sau khi user duyệt.

## Giới hạn

- Không chạy full regression suite, tests/m1, tests/m2.
- Chỉ sử dụng thư viện chuẩn Python (stdlib) và các module domain nội bộ `controlplane.domain`.
- Không sửa `operation_view_mapper.py`, `__init__.py` hay bất kỳ tệp nào ngoài 3 owned paths được cấp quyền.
- Không gọi dịch vụ thật; không đọc thông tin bảo mật hay credentials.
