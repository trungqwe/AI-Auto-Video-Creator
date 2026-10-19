# Báo cáo bằng chứng H-11

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `1602d70f0336bccf043242bb76a0bb1d57afd13a`
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-11 trong docs/implementation/h/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_status_presentation.py -q -p no:cacheprovider` (chạy trên khung stub RED ở bước 6)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `7 failed, 2 passed in 0.13s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/control_ui/test_h_status_presentation.py::test_status_keys_equal_h01 - AssertionError: export const STATUS_PRESENTATION: Record<OperationStatus, StatusPresentation>`
  - `FAILED tests/unit/control_ui/test_h_status_presentation.py::test_status_rows_match_acceptance - AssertionError: export const STATUS_PRESENTATION: Record<OperationStatus, StatusPresentation>`
  - `FAILED tests/unit/control_ui/test_h_status_presentation.py::test_labels_distinct_with_vietnamese_marks - AssertionError: export const STATUS_PRESENTATION: Record<OperationStatus, StatusPresentation>`
  - `FAILED tests/unit/control_ui/test_h_status_presentation.py::test_css_classes_distinct_and_flags - AssertionError: export const STATUS_PRESENTATION: Record<OperationStatus, StatusPresentation>`
  - `FAILED tests/unit/control_ui/test_h_status_presentation.py::test_unrecognized_status_has_pill_unknown_branch - assert "export const UNRECOGNIZED_STATUS_PRESENTATION: StatusPresentation = {\n  label: 'Không nhận diện được',\n  cssClass: 'pill-unknown',\n  terminal: false,\n  attention: true,\n};" in 'export {};\n'`
  - `FAILED tests/unit/control_ui/test_h_status_presentation.py::test_artifact_availability_five_states - AssertionError: export const ARTIFACT_AVAILABILITY_PRESENTATION: Record<ArtifactAvailability, ArtifactAvailabilityPresentation>`
  - `FAILED tests/unit/control_ui/test_h_status_presentation.py::test_imports_and_interfaces - assert "import type { OperationStatus } from '../../types/operationView.ts';" in 'export {};\n'`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, SyntaxError hay lỗi collection. 2 test tĩnh (`test_no_accepted_fallback`, `test_no_any_and_no_replacement_char`) đã PASS ngay từ đầu. Tất cả 7 thất bại đều do AssertionError của oracle trên khung export rỗng.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_status_presentation.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic ở bước 8)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `9 passed in 0.06s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/ui/src/features/operations/statusPresentation.ts`: Định nghĩa và export `STATUS_PRESENTATION` (Record<OperationStatus, StatusPresentation> đủ 6 trạng thái `accepted`, `running`, `waiting`, `outcome_unknown`, `succeeded`, `failed` với nhãn tiếng Việt đủ dấu, cssClass duy nhất, cờ terminal và attention đúng đặc tả), `UNRECOGNIZED_STATUS_PRESENTATION`, hàm `presentStatus` chuẩn hóa chữ thường và trả fallback an toàn không rơi về accepted, `ARTIFACT_AVAILABILITY_STATES`, type `ArtifactAvailability`, interface `ArtifactAvailabilityPresentation`, `ARTIFACT_AVAILABILITY_PRESENTATION` (5 trạng thái `original`, `processed`, `uncertain`, `failed`, `unavailable`) và hàm `presentArtifactAvailability`. Tuyệt đối không dùng kiểu `any` và không chứa ký tự thay thế `\ufffd`.
  - `tests/unit/control_ui/test_h_status_presentation.py`: Bộ kiểm thử đơn vị gồm 9 hàm kiểm tra: các khóa trạng thái khớp H-01 qua OPERATION_STATUSES, hàng trạng thái khớp acceptance, nhãn tiếng Việt đôi một khác nhau và có dấu tiếng Việt, cssClass đôi một khác nhau và các cờ terminal/attention đúng, nhánh fallback pill-unknown và hàm normalize, không fallback về accepted, đủ 5 trạng thái artifact với nhãn tiếng Việt có dấu, import đúng type OperationStatus từ operationView.ts và các interface, không dùng `any` và không chứa ký tự thay thế.
  - `docs/delivery-evidence/h-11/report.md`: Báo cáo bằng chứng nghiệm thu ghi lại chi tiết môi trường, RED, GREEN, thay đổi, bảng kết quả lệnh kiểm, quyết định mặc định D8, ánh xạ phản ví dụ, coveredIds, danh sách chờ user và giới hạn.
- Xác nhận: Tệp `src/controlplane/ui/src/index.css` và `src/controlplane/ui/src/types/operationView.ts` hoàn toàn không bị sửa đổi trong toàn bộ quá trình thực hiện task.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/control_ui/test_h_status_presentation.py -q -p no:cacheprovider` | 0 | `9 passed in 0.06s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

- GIẢ ĐỊNH: Presentation artifact chỉ có `label` vì acceptance không yêu cầu cssClass, CSS cho lớp mới (pill-waiting, pill-outcome-unknown, pill-unknown) là YC-HT-H-03.
- GIẢ ĐỊNH: `presentStatus` bỏ khoảng trắng đầu cuối và chuyển chữ thường, giá trị không phải chuỗi hoặc rỗng trả `pill-unknown`.

## Ánh xạ phản ví dụ

- `waiting` hiển thị như `accepted` -> Loại trừ bởi `test_status_rows_match_acceptance` và `test_css_classes_distinct_and_flags`.
- Giá trị lạ thành `accepted` -> Loại trừ bởi `test_unrecognized_status_has_pill_unknown_branch` và `test_no_accepted_fallback`.
- Nhãn không dấu -> Loại trừ bởi `test_labels_distinct_with_vietnamese_marks`.
- Thiếu trạng thái artifact -> Loại trừ bởi `test_artifact_availability_five_states`.

## coveredIds

- `QR-UX-001`
- `QR-UX-003`
- `CT-API-007`

## Danh sách chờ user (pendingUserCheckpoint)

- `PUC-H-03`: Xác nhận enum và cấu trúc wait_reason/progress khi có cập nhật contract.
- `USER-CKPT-D9-D10`: User duyệt danh mục thư viện đề xuất và runtime tái lập.
- `CP7 tài nguyên thật (D5)`: Quyền truy cập tài nguyên thật và secret broker sau khi user duyệt.

## Giới hạn

- Không chạy full regression suite, tests/m1, tests/m2.
- Không thêm thư viện ngoài; không sửa lockfile.
- Chỉ sửa 3 owned paths được phân quyền (`src/controlplane/ui/src/features/operations/statusPresentation.ts`, `tests/unit/control_ui/test_h_status_presentation.py`, `docs/delivery-evidence/h-11/report.md`).
- Không gọi dịch vụ thật; không đọc thông tin bảo mật hay credentials.
- Không chạy tsc hay trình duyệt: kiểm tra TS ở slice này là tĩnh qua pytest.
