# Báo cáo bằng chứng H-12

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `3699ef42c7c3f4dc5540c478fce3d86ef3a633fb`
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-12 trong docs/implementation/h/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_status_pill.py -q -p no:cacheprovider` (chạy trên khung stub RED ở bước 3)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `4 failed, 16 passed in 0.22s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/control_ui/test_h_status_pill.py::test_source_has_no_violation - AssertionError: assert ["missing:imp...ion.cssClass'] == []`
  - `FAILED tests/unit/control_ui/test_h_status_pill.py::test_signature_and_presenter - AssertionError: assert 'presentStatus(status)' in "import React from 'react';\nexport const StatusPill: React.FC<{ status: string | null | undefined; testIdPrefix?: string }> = () => <span />;\n"`
  - `FAILED tests/unit/control_ui/test_h_status_pill.py::test_span_carries_class_role_label_and_testid - AssertionError: assert 'className={`pill ${presentation.cssClass}`}' in "import React from 'react';\nexport const StatusPill: React.FC<{ status: string | null | undefined; testIdPrefix?: string }> = () => <span />;\n"`
  - `FAILED tests/unit/control_ui/test_h_status_pill.py::test_label_text_is_rendered_as_jsx_content - AssertionError: assert None is not None`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, SyntaxError hay lỗi collection. Tất cả 4 test thất bại đều do `AssertionError` khi kiểm tra trên stub `StatusPill.tsx` chưa triển khai logic.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_status_pill.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic đầy đủ ở bước 5)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `20 passed in 0.04s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/ui/src/components/StatusPill.tsx`: Component React hiển thị nhãn trạng thái (StatusPill), import `presentStatus` từ `../features/operations/statusPresentation.ts`. Render `<span>` với className `pill ${presentation.cssClass}`, role="status", aria-label là `{presentation.label}`, data-testid là `${testIdPrefix ?? 'status'}-${suffix}` (với `suffix = normalized === '' ? 'unknown' : normalized` và `normalized = typeof status === 'string' ? status.trim().toLowerCase() : ''`), nội dung là `{presentation.label}` qua JSX. Không import ag-grid-*, không import api/client, không tự gọi fetch, không dùng dangerouslySetInnerHTML hay innerHTML.
  - `tests/unit/control_ui/test_h_status_pill.py`: Bộ kiểm thử tĩnh bằng pytest đọc tệp TSX, kiểm tra import `presentStatus`, chữ ký component, các thuộc tính bắt buộc (`role="status"`, `aria-label`, `data-testid`, `testIdPrefix`, `{presentation.label}`, `presentation.cssClass`), chuẩn hóa trạng thái và 8 mẫu phản ví dụ tham số hóa (HTML thô, ag-grid, api/client, fetch, ký tự thay thế) cùng các test kiểm tra thiếu token và màu thuần.
  - `docs/delivery-evidence/h-12/report.md`: Báo cáo bằng chứng nghiệm thu ghi lại chi tiết môi trường, RED, GREEN, thay đổi, bảng kết quả lệnh kiểm, quyết định mặc định (D8), ánh xạ phản ví dụ, coveredIds, danh sách chờ user và giới hạn.
- Xác nhận không sửa `OperationsGrid.tsx`, `statusPresentation.ts` hay bất kỳ tệp nào khác trong `src/**`.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/control_ui/test_h_status_pill.py -q -p no:cacheprovider` | 0 | `20 passed in 0.04s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

- data-testid dùng giá trị chuẩn hóa trim và lowercase; chuỗi rỗng, null, undefined cho hậu tố 'unknown' — GIẢ ĐỊNH D8-H-12.
- testIdPrefix='operation-status' giữ tương thích e2e hiện có.
- Không thay OperationsGrid.tsx trong slice này, việc nối vào lưới thuộc YC-HT-H-03.

## Ánh xạ phản ví dụ

- Render HTML thô -> Loại trừ bởi `test_raw_html_and_self_fetching_components_are_reported` và `test_violation_is_reported` (mẫu `dangerouslySetInnerHTML`, `innerHTML`).
- Trạng thái chỉ khác nhau bằng màu -> Loại trừ bởi `test_color_only_pill_is_reported` và `test_removed_token_is_reported_missing` (`{presentation.label}`, `aria-label=`, `role="status"`).
- Component tự gọi API -> Loại trừ bởi `test_raw_html_and_self_fetching_components_are_reported` và `test_violation_is_reported` (mẫu `api/client`, `fetch`).

## coveredIds

- `CT-API-007`
- `EG-M2-H-4`

## Danh sách chờ user (pendingUserCheckpoint)

- `USER-CKPT-D9-D10`: User duyệt danh mục thư viện đề xuất và runtime tái lập.
- `CP7 tài nguyên thật (D5)`: Quyền truy cập tài nguyên thật và secret broker sau khi user duyệt.
- Không có mục mới phát sinh từ slice H-12.

## Giới hạn

- Guard tĩnh bằng stdlib Python đọc tệp TSX, không thay thế `tsc` hay `npm run build`, không kiểm tra DOM thật (việc đó thuộc CP7-H-01).
- Không chạy full regression suite, `tests/m1`, `tests/m2`.
- Không thêm thư viện ngoài.
- Không sửa tệp ngoài 3 owned paths.
- Không gọi dịch vụ thật; không đọc bí mật hay credentials.
