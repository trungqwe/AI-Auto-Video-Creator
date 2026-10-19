# Báo cáo bằng chứng H-16

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `ddeec203cadc4982286cbfa02a4882905967b7d1`
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-16 trong docs/implementation/h/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_ui_source_guard.py -q -p no:cacheprovider` (chạy trên khung stub RED ở bước 3)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `17 failed, 9 passed in 0.15s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/control_ui/test_h_ui_source_guard.py::test_violation_is_reported[src/components/A.tsx-<div dangerouslySetInnerHTML={{ __html: x }} />-dangerouslySetInnerHTML] - AssertionError: []`
  - `FAILED tests/unit/control_ui/test_h_ui_source_guard.py::test_violation_is_reported[src/components/A.tsx-el.innerHTML = x;-innerHTML] - AssertionError: []`
  - `FAILED tests/unit/control_ui/test_h_ui_source_guard.py::test_violation_is_reported[src/components/A.tsx-eval(code);-eval] - AssertionError: []`
  - `FAILED tests/unit/control_ui/test_h_ui_source_guard.py::test_violation_is_reported[src/components/A.tsx-const f = new Function('return 1');-new Function] - AssertionError: []`
  - `FAILED tests/unit/control_ui/test_h_ui_source_guard.py::test_violation_is_reported[src/components/A.tsx-document.write(x);-document.write] - AssertionError: []`
  - `FAILED tests/unit/control_ui/test_h_ui_source_guard.py::test_violation_is_reported[src/components/A.tsx-localStorage.setItem('a', 'b');-localStorage] - AssertionError: []`
  - `FAILED tests/unit/control_ui/test_h_ui_source_guard.py::test_violation_is_reported[src/components/A.tsx-sessionStorage.getItem('a');-sessionStorage] - AssertionError: []`
  - `FAILED tests/unit/control_ui/test_h_ui_source_guard.py::test_violation_is_reported[src/components/A.tsx-await fetch('/v1/jobs');-fetch_outside_api] - AssertionError: []`
  - `FAILED tests/unit/control_ui/test_h_ui_source_guard.py::test_violation_is_reported[src/components/A.tsx-const apiKey = 'abcdefgh12345678';-hardcoded_secret] - AssertionError: []`
  - `FAILED tests/unit/control_ui/test_h_ui_source_guard.py::test_simulated_bom_file_is_reported - AssertionError: []`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, SyntaxError hay lỗi collection. 7 test mẫu sạch (CLEAN) và 2 test quét cây UI thực tế (`test_current_ui_tree_has_no_violation`, `test_fetch_only_in_api_client`) đã PASS ngay từ đầu. Tất cả 17 test thất bại đều do `AssertionError` khi kiểm tra mẫu vi phạm trên stub `scan_ui_source` trả về danh sách rỗng `[]`.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_ui_source_guard.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic ở bước 5)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `26 passed in 0.05s`

## Thay đổi

- 2 tệp thuộc owned paths:
  - `tests/unit/control_ui/test_h_ui_source_guard.py`: Tệp kiểm thử và hàm guard tĩnh nguồn UI `scan_ui_source(path, text) -> list[str]` kiểm tra XSS sink (`dangerouslySetInnerHTML`, `.innerHTML`, `eval(`, `new Function(`, `document.write`, `localStorage`, `sessionStorage`), phát hiện `fetch(` ngoài thư mục `src/api/`, khóa secret/token/api_key hằng chữ/số từ 16 ký tự, ký tự hỏng `\uFFFD`, endpoint cấm `/scripts`, `/event-relations`, `/article-body` trong `src/api/` và `src/features/`, và ký tự BOM `\uFEFF`. Bao gồm 16 mẫu vi phạm, 7 mẫu sạch, 1 test BOM giả lập và 2 test quét cây UI thực tế dưới `src/controlplane/ui/src/`.
  - `docs/delivery-evidence/h-16/report.md`: Báo cáo bằng chứng nghiệm thu ghi lại chi tiết môi trường, RED, GREEN, thay đổi, bảng kết quả lệnh kiểm, quyết định mặc định (D8), ánh xạ phản ví dụ, coveredIds, danh sách chờ user và giới hạn.
- Không có module sản phẩm mới, không sửa bất kỳ tệp nào trong `src/**` (kể cả `src/controlplane/ui/src/**`).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/control_ui/test_h_ui_source_guard.py -q -p no:cacheprovider` | 0 | `26 passed in 0.05s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

- Regex khóa secret `SECRET_RE`: tên biến/thuộc tính chứa `api_key`, `apikey`, `secret` hoặc `token` (không phân biệt hoa thường, `re.IGNORECASE`), hỗ trợ chú thích kiểu TypeScript (ví dụ `: string`), gán chuỗi hằng chỉ gồm chữ và số (`[A-Za-z0-9]`) từ 16 ký tự trở lên (GIẢ ĐỊNH D8-H-16).
- Không loại trừ comment trong mã nguồn UI khi quét guard (bảo thủ fail-closed, GIẢ ĐỊNH D8-H-16).
- Endpoint cấm (`/scripts`, `/event-relations`, `/article-body`) chỉ xét trong các tệp thuộc `src/api/` và `src/features/` (GIẢ ĐỊNH D8-H-16).
- Đường dẫn truyền cho `scan_ui_source` được chuẩn hóa tính từ thư mục UI gốc, ví dụ `src/api/client.ts` (GIẢ ĐỊNH D8-H-16).
- Định dạng mỗi vi phạm trả về là chuỗi `<path>:<dòng>: <mã>` (cho phép tách mã vi phạm bằng `rsplit(': ', 1)`).

## Ánh xạ phản ví dụ

- `dangerouslySetInnerHTML` với dữ liệu nguồn ngoài -> Loại trừ bởi `test_violation_is_reported[dangerouslySetInnerHTML]`.
- `fetch` trực tiếp trong component -> Loại trừ bởi mẫu vi phạm `fetch_outside_api` và test quét cây `test_fetch_only_in_api_client` (chỉ cho phép trong `src/api/client.ts`).
- Secret hằng trong mã UI -> Loại trừ bởi 3 mẫu vi phạm `hardcoded_secret` (`apiKey`, `token`, `client_secret`).
- Endpoint sửa script hoặc quan hệ event (`/scripts`, `/event-relations`, `/article-body`) -> Loại trừ bởi 3 mẫu `forbidden_endpoint` trong `src/api/client.ts` và `src/features/x.ts`.

## coveredIds

- `CT-API-010`
- `TST-SEC-INV-012`
- `QR-UX-001`

## Danh sách chờ user (pendingUserCheckpoint)

- `USER-CKPT-D9-D10`: User duyệt danh mục thư viện đề xuất và runtime tái lập.
- `CP7 tài nguyên thật (D5)`: Quyền truy cập tài nguyên thật và secret broker sau khi user duyệt.
- Không có mục mới phát sinh từ slice H-16.

## Giới hạn

- Không chạy full regression suite, `tests/m1`, `tests/m2`.
- Test guard tĩnh bằng stdlib Python (`re`, `pathlib`), không thay thế hoàn toàn cho `tsc` hoặc `npm run build`.
- Quét cây UI chỉ đọc các tệp `.ts` và `.tsx` dưới `src/controlplane/ui/src/`, bỏ qua thư mục `node_modules` và `dist`.
- Chỉ sử dụng thư viện chuẩn Python (stdlib), không thêm thư viện ngoài.
- Không sửa tệp ngoài 2 owned paths (`tests/unit/control_ui/test_h_ui_source_guard.py` và `docs/delivery-evidence/h-16/report.md`).
- Không gọi dịch vụ thật; không đọc bí mật hay credentials.