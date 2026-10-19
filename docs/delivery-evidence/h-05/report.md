# Báo cáo bằng chứng H-05

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `ace870b20f86bf842f4c36566c30c98af9e05ae7`
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-05 trong docs/implementation/h/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_ops_read_models.py -q -p no:cacheprovider` (chạy trên khung stub RED ở bước 4)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `28 failed, 3 passed in 0.30s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/control_ui/test_h_ops_read_models.py::test_safe_summary_rejects_markers[Traceback (most recent call last): boom] - NotImplementedError: H-05 RED stub: safe_summary`
  - `FAILED tests/unit/control_ui/test_h_ops_read_models.py::test_safe_summary_truncates_and_flattens - NotImplementedError: H-05 RED stub: safe_summary`
  - `FAILED tests/unit/control_ui/test_h_ops_read_models.py::test_safe_summary_invalid_arguments - NotImplementedError: H-05 RED stub: safe_summary`
  - `FAILED tests/unit/control_ui/test_h_ops_read_models.py::test_log_rejects_traceback_summary - NotImplementedError: H-05 RED stub: build_log_entry`
  - `FAILED tests/unit/control_ui/test_h_ops_read_models.py::test_log_severity - NotImplementedError: H-05 RED stub: build_log_entry`
  - `FAILED tests/unit/control_ui/test_h_ops_read_models.py::test_stage_attempt - NotImplementedError: H-05 RED stub: build_stage_run_view`
  - `FAILED tests/unit/control_ui/test_h_ops_read_models.py::test_stage_problem_forbidden_key_top_level[stack_trace] - NotImplementedError: H-05 RED stub: build_stage_run_view`
  - `FAILED tests/unit/control_ui/test_h_ops_read_models.py::test_milestones_independent - NotImplementedError: H-05 RED stub: build_job_milestones`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, SyntaxError hay lỗi collection. 3 test tĩnh kiểm tra view và AST ranh giới import (test_session_and_capability_views, test_milestones_are_four_separate_fields, test_module_has_only_pure_imports) đã PASS ngay từ đầu. Tất cả 28 test thất bại đều do `NotImplementedError` từ stub 'H-05 RED stub: ...'.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_ops_read_models.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic ở bước 7)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `31 passed in 0.04s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/application/projections/ops_read_models.py`: Module thuần định nghĩa 5 dataclass frozen (`StageRunView`, `SessionView`, `LogEntryView`, `CapabilityHealthView`, `JobMilestonesView`) và 4 hàm dựng view an toàn (`safe_summary`, `build_log_entry`, `build_stage_run_view`, `build_job_milestones`) tuân thủ CT-API-002, CT-STATE-009 và các nguyên tắc bảo mật lọc rò rỉ stack trace/traceback.
  - `tests/unit/control_ui/test_h_ops_read_models.py`: Bộ kiểm thử đơn vị toàn diện gồm 21 nhóm test bao phủ mọi khía cạnh: lọc marker traceback/stack trace trong log summary, làm phẳng và cắt ngắn văn bản summary, thẩm định các trường severity/UUID technical_detail_ref, kiểm tra số lượt attempt và phát hiện đệ quy các khóa bị cấm trong problem (kể cả lồng sâu trong dict/list/tuple), kiểm tra tính độc lập và ràng buộc logic của 4 mốc job (completed yêu cầu upload_verified), tính bất biến frozen của các dataclass và kiểm tra AST chỉ import stdlib thuần.
  - `docs/delivery-evidence/h-05/report.md`: Báo cáo bằng chứng nghiệm thu ghi lại chi tiết môi trường, RED, GREEN, thay đổi, bảng kết quả lệnh kiểm, quyết định D8, ánh xạ phản ví dụ, coveredIds, danh sách chờ user và giới hạn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/control_ui/test_h_ops_read_models.py -q -p no:cacheprovider` | 0 | `31 passed in 0.04s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

- Các mã lỗi ValueError `invalid_summary`, `invalid_max_len`, `invalid_severity`, `invalid_technical_detail_ref`, `invalid_attempt`, `invalid_refs`, `invalid_problem`, `unsafe_problem`, `invalid_milestone` là GIẢ ĐỊNH của slice H-05 (spec chỉ cố định `unsafe_summary` và `completed_without_upload_verified`).
- Severity `debug/info/warning/error` là GIẢ ĐỊNH D8-H-04.
- `technical_detail_ref` phải là UUID dạng chuẩn có gạch ngang (không nhận dạng có ngoặc nhọn hoặc không gạch), chuẩn hoá về chữ thường để truy vấn `/v1/errors/{ref}` an toàn.
- Kiểm khóa cấm của problem là so khớp nguyên khóa không phân biệt hoa thường ở mọi độ sâu (dict, list, tuple), chỉ ba khóa `stack_trace`, `traceback`, `internal_detail`.
- Marker của safe_summary được kiểm trên toàn văn đã làm phẳng trước khi cắt.
- `status`, `availability` của stage/session/capability là chuỗi tự do vì contract chưa chốt enum (GIẢ ĐỊNH, chờ PUC-H-03).

## Ánh xạ phản ví dụ

- Log summary mang stack trace -> Loại trừ bởi test 1, 4 (`test_safe_summary_rejects_markers`, `test_log_rejects_traceback_summary`).
- Completion khi chưa verify upload -> Loại trừ bởi test 17 (`test_milestones_all_sixteen_combinations`).
- Bốn mốc gộp một cờ -> Loại trừ bởi test 16, 19 (`test_milestones_independent`, `test_milestones_are_four_separate_fields`).
- Attempt bằng 0 -> Loại trừ bởi test 8 (`test_stage_attempt`).
- Technical_detail_ref không phải UUID làm hỏng truy vấn /v1/errors/{ref} -> Loại trừ bởi test 7 (`test_log_technical_detail_ref`).

## coveredIds

- `CT-API-002`
- `CT-STATE-009`
- `QR-UX-003`
- `TST-E2E-INV-009`

## Danh sách chờ user (pendingUserCheckpoint)

- `PUC-H-03`: Xác nhận enum và mức severity GIẢ ĐỊNH D8-H-04.
- `USER-CKPT-D9-D10`: User duyệt danh mục thư viện đề xuất và runtime tái lập.
- `CP7 tài nguyên thật (D5)`: Quyền truy cập tài nguyên thật và secret broker sau khi user duyệt.

## Giới hạn

- Không chạy full regression suite, tests/m1, tests/m2.
- Chỉ sử dụng thư viện chuẩn Python (stdlib: `__future__`, `dataclasses`, `typing`, `uuid`).
- Không sửa tệp ngoài owned paths được cấp quyền (`src/controlplane/application/projections/ops_read_models.py`, `tests/unit/control_ui/test_h_ops_read_models.py`, `docs/delivery-evidence/h-05/report.md`).
- Không gọi dịch vụ thật; không đọc thông tin bảo mật hay credentials.
