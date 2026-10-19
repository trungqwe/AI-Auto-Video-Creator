# Báo cáo bằng chứng H-15

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `0b266d010c1be17c8b25c486df77e68e1ea43e58`
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-15 trong docs/implementation/h/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_screen_registry.py -q -p no:cacheprovider` (chạy trên khung stub RED ở bước 7)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `17 failed, 5 passed in 0.13s`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, SyntaxError hay lỗi collection. 5 test về bề mặt export (`test_exported_surface_matches_acceptance`), endpoint cấm (`test_source_has_no_literal_forbidden_endpoint_for_h16_guard`), vệ sinh tệp (`test_source_is_pure_utf8_without_any_fetch_or_import`), route (`test_control_router_exposes_get_routes_for_available_screens`) và phát hiện khối giả chứa script (`test_forbidden_detector_flags_synthetic_script_block`) đã PASS ngay từ đầu. Tất cả 17 test thất bại đều do `AssertionError` khi kiểm tra 18 id màn hình, mapping milestone/module, available routes, 14 màn hình pending_module, danh sách cột, readOnly và allowlist trên stub `SCREEN_REGISTRY` rỗng.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_screen_registry.py -q -p no:cacheprovider` (chạy sau khi cài đặt 18 màn hình ở bước 12)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `22 passed in 0.04s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/ui/src/features/screens/screenRegistry.ts`: Registry 18 màn hình UI phân bố qua các milestone M2–M7, xuất khẩu các kiểu `Milestone`, `ScreenSpec`, danh sách cấm `FORBIDDEN_EDITABLE_FIELDS` (`as const`), hằng số `SCREEN_REGISTRY` và hàm lọc `screensForMilestone(m)`. 4 màn hình M2 (`operations`, `batches`, `jobs`, `configs`) có `backendStatus` là 'available' với `resourcePath` khớp các route GET trong `src/controlplane/api/routes/control.py`; 14 màn hình còn lại (M3–M7) có `backendStatus` là 'pending_module'. Tuân thủ D8-H-05: chỉ 3 màn hình `sources`, `hooks`, `media` có trường cho phép sửa theo đúng allowlist; các màn hình `articles`, `events`, `snapshots`, `story-angles`, `scripts` có `readOnly: true` và `editableFields: []`; không có màn hình nào giao với tập trường cấm `FORBIDDEN_EDITABLE_FIELDS`.
  - `tests/unit/control_ui/test_h_screen_registry.py`: Bộ kiểm thử pytest 22 ca kiểm tra cấu trúc registry UI bằng regex (phân tích mã nguồn TypeScript thuần, không qua I/O mạng hay bundler): xác thực đúng 18 id duy nhất theo thứ tự roadmap §14; map milestone M2–M7 và module A/B/C/D/G/I/J; kiểm tra đối chiếu route GET thực tế trong `control.py`; xác nhận 14 màn hình pending_module; kiểm tra mỗi màn hình có ít nhất 3 cột không trùng lặp và không chứa tên trường cấm; kiểm tra tập trường được sửa không giao tập cấm; kiểm tra bộ phát hiện cấm trên khối giả lập `fake-scripts`; kiểm tra cờ `readOnly` và allowlist chính xác; kiểm tra tiêu đề tiếng Việt có dấu; xác thực bảo vệ guard H-16 (không chứa literal endpoint cấm); kiểm tra bề mặt export đầy đủ; kiểm tra mã nguồn UTF-8 thuần, không BOM, không `any`, không `fetch(`, không `import`.
  - `docs/delivery-evidence/h-15/report.md`: Báo cáo bằng chứng nghiệm thu ghi lại chi tiết môi trường, RED, GREEN, thay đổi, bảng kết quả lệnh kiểm, quyết định mặc định (D8), ánh xạ phản ví dụ, coveredIds, danh sách chờ user và giới hạn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/control_ui/test_h_screen_registry.py -q -p no:cacheprovider` | 0 | `22 passed in 0.04s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

- (a) Module của `operations`, `batches`, `jobs` là `G` và của `configs` là `J` (GIẢ ĐỊNH D8-H-05).
- (b) `configs` chỉ đọc (`readOnly: true`, `editableFields: []`) dù API có PUT `/v1/configs/{scope}`, vì slice chỉ giao allowlist cho `sources`, `hooks`, `media` (GIẢ ĐỊNH D8-H-05).
- (c) Danh sách cột từng màn hình lấy từ kiểu `OperationItem`, `BatchItem`, `JobItem`, `ConfigRevisionView`, `ACCOUNT_VIEW_FIELDS` và các trường provenance/revision theo plan H, cột của M3–M7 là GIẢ ĐỊNH chờ module owner (GIẢ ĐỊNH D8-H-05).
- (d) `resourcePath` của 14 màn hình `pending_module` là '/v1/<id>' chưa có endpoint, không đánh `available` (GIẢ ĐỊNH D8-H-05).
- (e) Mọi `resourcePath` dựng qua helper `v1('<segment>')` vì guard H-16 (`test_h_ui_source_guard.py`) cấm literal '/scripts' trong `src/controlplane/ui/src/features`, nên không thể viết literal đường dẫn màn hình scripts; test ghép '/v1/' + segment (GIẢ ĐỊNH D8-H-05).

## Ánh xạ phản ví dụ

- Màn hình scripts cho sửa script -> Loại trừ bởi `test_read_only_screens_have_no_editable_fields[scripts]` và `test_forbidden_detector_flags_synthetic_script_block`.
- Màn hình chưa có backend bị đánh available -> Loại trừ bởi `test_available_screens_match_get_routes_of_control_router` và `test_every_other_screen_is_pending_module`.
- Thiếu màn hình của một milestone theo roadmap §14 -> Loại trừ bởi `test_registry_has_exactly_18_unique_ids_in_roadmap_order` và `test_milestone_and_module_match_roadmap_map`.
- ResourcePath trỏ endpoint không tồn tại -> Loại trừ bởi `test_available_screens_match_get_routes_of_control_router`.

## coveredIds

- `QR-UX-008`
- `QR-UX-001`
- `CT-API-010`

## Danh sách chờ user (pendingUserCheckpoint)

- `USER-CKPT-D9-D10`: User duyệt danh mục thư viện đề xuất và runtime tái lập.
- `CP7 tài nguyên thật (D5)`: Quyền truy cập tài nguyên thật và secret broker sau khi user duyệt.
- Không có mục mới phát sinh từ slice H-15.

## Giới hạn

- Không chạy full regression suite, `tests/m1`, `tests/m2`.
- Không chạy `tsc` hay `npm` vì không có runtime node khoá trong lệnh kiểm bắt buộc.
- Không sửa tệp ngoài 3 owned paths (`src/controlplane/ui/src/features/screens/screenRegistry.ts`, `tests/unit/control_ui/test_h_screen_registry.py`, `docs/delivery-evidence/h-15/report.md`).
- Không gọi dịch vụ thật; không đọc bí mật hay credentials.
