# Báo cáo bằng chứng H-13

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `0b266d010c1be17c8b25c486df77e68e1ea43e58`
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-13 trong docs/implementation/h/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_error_hover_detail.py -q -p no:cacheprovider` (chạy trên khung stub RED ở bước 3)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `6 failed, 18 passed in 0.11s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/control_ui/test_h_error_hover_detail.py::test_source_has_no_violation - AssertionError: assert ['missing:tab...:onBlur', ...] == []`
  - `FAILED tests/unit/control_ui/test_h_error_hover_detail.py::test_signature_and_null_guard - assert 'problem: ErrorHoverProblem | null | undefined;' in ...`
  - `FAILED tests/unit/control_ui/test_h_error_hover_detail.py::test_trigger_is_keyboard_focusable_and_described_by_tooltip - assert 0 == 1`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, SyntaxError hay lỗi collection. Tất cả 6 test thất bại đều do `AssertionError` khi kiểm tra trên stub `ErrorHoverDetail.tsx` chưa triển khai logic.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_error_hover_detail.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic đầy đủ ở bước 5)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `24 passed in 0.04s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/ui/src/components/ErrorHoverDetail.tsx`: Component React hiển thị tooltip chi tiết lỗi khi hover hoặc focus bàn phím, đóng khi unhover, blur hoặc phím Escape. Chỉ hiển thị các trường an toàn (`title`, `code`, `correlation_id`, `detail` cắt tối đa 300 ký tự qua `MAX_DETAIL_CHARS`), nút kỹ thuật gọi callback `onOpenTechnicalDetail(technical_detail_ref)` có nhãn tiếng Việt có dấu, không import api/client, không tự fetch, không chứa trường nhạy cảm hoặc stack trace.
  - `tests/unit/control_ui/test_h_error_hover_detail.py`: Bộ kiểm thử tĩnh bằng pytest đọc tệp TSX, kiểm tra chữ ký, null guard, khả năng focus bàn phím (`tabIndex={0}`), ARIA tooltip, các handler sự kiện, giới hạn trường JSX, nhãn tiếng Việt và 17 mẫu tham số hoá phản ví dụ (xâm nhập cấm, thiếu token bắt buộc, component chỉ hover).
  - `docs/delivery-evidence/h-13/report.md`: Báo cáo bằng chứng nghiệm thu ghi lại chi tiết môi trường, RED, GREEN, thay đổi, bảng kết quả lệnh kiểm, quyết định mặc định (D8), ánh xạ phản ví dụ, coveredIds, danh sách chờ user và giới hạn.
- Không sửa bất kỳ tệp nào khác trong `src/**` (kể cả `SafeErrorModal.tsx`, `api/client.ts`, `types/api.ts`).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/control_ui/test_h_error_hover_detail.py -q -p no:cacheprovider` | 0 | `24 passed in 0.04s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

- Dùng nút kích hoạt `tabIndex={0}` dạng span với nhãn cố định 'Chi tiết lỗi'.
- Tooltip chỉ render khi mở (`open === true`).
- Cắt detail bằng `Array.from(...).slice(0, MAX_DETAIL_CHARS)` không thêm dấu chấm lửng để không vượt 300 ký tự (GIẢ ĐỊNH D8-H-13).
- Nút chi tiết kỹ thuật chỉ hiện khi có cả `technical_detail_ref` và `onOpenTechnicalDetail`, `technical_detail_ref` không render thành chữ.
- `onBlur` dùng `relatedTarget` để nút trong tooltip còn tiếp cận được bằng bàn phím mà không bị đóng tooltip ngoài ý muốn.

## Ánh xạ phản ví dụ

- Chỉ hover không focus được bằng bàn phím -> Loại trừ bởi `test_hover_only_source_is_reported` và `test_removed_token_is_reported_missing` (`tabIndex={0}`, `onFocus`, `Escape`).
- Tooltip nhúng `internal_detail` hoặc `stack` trace -> Loại trừ bởi `test_violation_is_reported` các mẫu `internal_detail`, `stack_trace`, `field:extra`.
- Component tự gọi API -> Loại trừ bởi `test_violation_is_reported` các mẫu `fetch` và `import:../api/client.ts`.

## coveredIds

- `QR-UX-004`
- `QR-UX-001`
- `CT-API-010`

## Danh sách chờ user (pendingUserCheckpoint)

- `USER-CKPT-D9-D10`: User duyệt danh mục thư viện đề xuất và runtime tái lập.
- `CP7 tài nguyên thật (D5)`: Quyền truy cập tài nguyên thật và secret broker sau khi user duyệt.
- Không có mục mới phát sinh từ slice H-13.

## Giới hạn

- Không chạy full regression suite, `tests/m1`, `tests/m2`.
- Test là guard tĩnh bằng stdlib Python đọc tệp TSX, không thay thế `tsc` hoặc `npm run build` và không kiểm hành vi DOM thật (việc đó thuộc CP7-H-01).
- Không thêm thư viện ngoài.
- Không sửa tệp ngoài 3 owned paths.
- Không gọi dịch vụ thật; không đọc bí mật hay credentials.
