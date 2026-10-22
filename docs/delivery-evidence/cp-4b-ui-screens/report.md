# Báo cáo giao hàng: CP-4B-UI-SCREENS

## 1. Phạm vi thực hiện

Danh sách các tệp đã sửa đổi hoặc tạo mới trong phạm vi owned paths của gói:
- `src/controlplane/ui/src/types/api.ts`: Bổ sung 6 trường tùy chọn vào `OperationItem` (`progress`, `started_at`, `updated_at`, `finished_at`, `wait_reason`, `problem`), thêm kiểu `ModuleRow` và `ModulePage`.
- `src/controlplane/ui/src/api/client.ts`: Thêm `fetchModulePage` và `patchModuleItem` (sử dụng method PATCH, header If-Match theo revision nguyên dương, Idempotency-Key bắt buộc); giữ nguyên `/test-driver/issue-capability`.
- `src/controlplane/ui/src/features/screens/screenRegistry.ts`: Chuyển duy nhất `stage-runs` sang `available`; thêm cột `revision` vào `columns` của `sources`, `media`, `hooks`; giữ 13 màn hình còn lại ở `pending_module`. Tổng số màn hình là 18.
- `src/controlplane/ui/src/screens/screenHelpers.ts`: Tạo helper thuần cho bảng và form (`sendableFields` loại bỏ các trường cấm; `newIdempotencyKey` sinh khóa mới; không chứa sink XSS).
- `src/controlplane/ui/src/screens/ModuleListScreen.tsx`: Bảng hiển thị theo `ScreenSpec`, phân trang qua `next_cursor` (nút Tải thêm); màn hình khóa không gọi API.
- `src/controlplane/ui/src/screens/EditableMetadataScreen.tsx`: Màn hình sửa metadata gồm danh sách và form chỉ nhận các trường trong `editableFields` hợp lệ, gửi PATCH kèm If-Match và Idempotency-Key.
- `src/controlplane/ui/src/App.tsx`: Tích hợp `ScreensNavigator` dựng điều hướng màn hình từ `SCREEN_REGISTRY`, các nút `pending_module` bị khóa (disabled) và không mount; giữ nguyên bốn thẻ cũ và prop `onOpenTestError=`.
- `src/controlplane/ui/src/index.css`: Bổ sung CSS cho `screen-nav`, `metadata-form`, `screen-error`, `screen-status`, `row-selected`.
- `tests/unit/control_ui/test_h_screen_registry.py`: Mở rộng kiểm thử ghìm H với `AVAILABLE_IDS` (thêm `stage-runs`), `PENDING_IDS`, `REVISION_COLUMN_IDS`, `router_get_paths` nhận diện `QueryListing`, và các test client.
- `tests/unit/control_ui/test_h_ts_contract_types.py`: Mở rộng kiểm thử ghìm H siết chặt 6 trường tùy chọn của `OperationItem` và các kiểu trang `ModuleRow`/`ModulePage`.
- `src/controlplane/ui/dist/**`: Dựng lại toàn bộ thư mục dist thông qua `npm run build`.

## 2. Kết quả chứng kiến RED trước khi implement

Lệnh thực hiện ở bước 6:
`python -m pytest tests/unit/control_ui/test_h_screen_registry.py tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cacheprovider`

Exit code: 1

Bốn dòng FAILED đầu tiên:
`FAILED tests/unit/control_ui/test_h_screen_registry.py::test_available_screens_match_get_routes_of_control_router`
`FAILED tests/unit/control_ui/test_h_screen_registry.py::test_available_and_pending_ids_partition_the_registry`
`FAILED tests/unit/control_ui/test_h_screen_registry.py::test_stage_runs_is_available_with_route_and_integration_test_evidence`
`FAILED tests/unit/control_ui/test_h_screen_registry.py::test_editable_screens_expose_revision_column[sources]`

Dòng tóm tắt nguyên văn:
`10 failed, 31 passed in 0.23s`

Xác nhận RED: Tất cả các test thất bại đều do AssertionError đối chiếu với oracle nguồn chưa cập nhật, không có lỗi collection, cú pháp hay ImportError.

## 3. Kết quả GREEN và dựng ui/dist

Kết quả thực hiện các lệnh bước 23 đến 27:

1. Bước 23 (Build UI dist):
- Lệnh: `npm --prefix src/controlplane/ui run build`
- Exit code: 0
- Kết quả: `built in 2.86s`, tạo mới `dist/index.html` và các tệp assets băm.
- Hai tệp assets thật được `dist/index.html` tham chiếu:
  - `index-Bh32kNNb.js`
  - `index-DNWUXu2_.css`

2. Bước 24 (Probe dist không mồ côi):
- Lệnh: `python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d / 'index.html').read_text(encoding='utf-8'); r = re.findall('assets/([A-Za-z0-9_.-]+)', h); assert r and all((d / 'assets' / x).is_file() for x in r), r; k = [f.name for f in (d / 'assets').iterdir() if f.is_file() and f.name not in r and not (f.name.endswith('.map') and f.name[:-4] in r)]; assert not k, ('orphan hashed files', k)"`
- Exit code: 0 (mọi tệp tham chiếu đều tồn tại, không có tệp băm mồ côi).

3. Bước 25 (Chạy toàn bộ test control_ui gồm guard H-16):
- Lệnh: `python -m pytest tests/unit/control_ui -q -p no:cacheprovider`
- Exit code: 0
- Dòng tóm tắt nguyên văn: `661 passed, 1 warning in 2.46s`

4. Bước 26 (Probe nguồn UI):
- Lệnh: `python -c "import pathlib; u = pathlib.Path('src/controlplane/ui/src'); a = (u / 'App.tsx').read_text(encoding='utf-8'); c = (u / 'api' / 'client.ts').read_text(encoding='utf-8'); assert 'SCREEN_REGISTRY' in a and 'onOpenTestError=' in a, 'App.tsx registry and test button'; assert all(k in c for k in ['PATCH', 'If-Match', 'Idempotency-Key', '/test-driver/issue-capability']), 'client.ts'"`
- Exit code: 0 (App.tsx có đủ registry và nút test; client.ts có đủ PATCH, If-Match, Idempotency-Key và endpoint test-driver).

5. Bước 27 (Probe registry):
- Lệnh: `python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8'); s = dict(re.findall('id: ' + chr(39) + '([a-z-]+)' + chr(39) + '.*?backendStatus: ' + chr(39) + '([a-z_]+)' + chr(39), r, re.S)); assert len(s) == 18, s; assert all(s[i] == 'pending_module' for i in ['artifacts', 'snapshots', 'story-angles', 'scripts', 'accounts', 'cost']), s"`
- Exit code: 0 (đúng 18 màn hình, 6 màn hình ngoài BL-CV-05 giữ pending_module).

## 4. Trạng thái Registry

- Chỉ có `stage-runs` được chuyển sang `available` vì CP-4-QUERIES chỉ mới có route và test tích hợp cho tài nguyên này.
- Bảy tài nguyên còn lại (`sources`, `articles`, `events`, `media`, `hooks`, `sessions`, `logs`) tiếp tục giữ `pending_module` vì bị BLOCKED (DEPENDENCY_GAP) theo báo cáo tại `docs/delivery-evidence/cp-4-queries/report.md`.
- Sáu màn hình ngoài BL-CV-05 (`artifacts`, `snapshots`, `story-angles`, `scripts`, `accounts`, `cost`) giữ nguyên `pending_module`.
- Cột `revision` đã được thêm vào `columns` của `sources`, `media`, `hooks`.
- Tổng số màn hình trong `SCREEN_REGISTRY` là 18 màn hình.
- Hệ quả: Do `sources`, `media`, `hooks` vẫn ở trạng thái `pending_module` nên component `EditableMetadataScreen` chưa được mở trong vận hành thực tế của giao diện, và route `PATCH /v1/sources` chưa được mount phía backend (`route_catalog` hiện chỉ khai báo PATCH cho `hooks` và `media`).

## 5. Mục BL-CV-13 — BLOCKED

- Trạng thái: BLOCKED.
- Gói này không gỡ nút kiểm thử `onOpenTestError` và route `/test-driver/issue-capability`.
- Chuỗi nguồn RSS sửa được thuộc trách nhiệm của CP-4-WIRING (mount router), ADAPT-PROD (gắn service thật) và CP-4-QUERIES (GET).
- Gói CP-4B-UI-SCREENS chỉ thực hiện xây dựng màn hình trên shell và hàm gửi PATCH, không làm phần ngoài phong bì.

## 6. Mục BL-CV-07 — PENDING

- Trạng thái: PENDING.
- Phần chạy `npm run test:e2e` do Control thực hiện và ghi bằng chứng; Worker không chạy lệnh này và không tuyên bố kết quả e2e PASS.
- Các hạng mục UI của BL-CV-07 nằm ngoài yêu cầu nghiệm thu 1–5 hoặc ngoài owned paths:
  - `components/OperationsGrid.tsx`, `components/BatchesGrid.tsx`, `components/JobsGrid.tsx`: PENDING / BLOCKED (ngoài owned paths).
  - Pill CSS cho `waiting`, `outcome-unknown`, `unknown`: PENDING / BLOCKED (ngoài yêu cầu gói này).
  - Chuyển `eventKinds` sang `streamEventKinds`: PENDING / BLOCKED (ngoài owned paths).
- Tất cả các hạng mục trên được ghi nhận là PENDING / BLOCKED, Worker không tuyên bố đã làm.

## 7. Tuân thủ quy chuẩn và kỷ luật ranh giới

- Không chạm hay sửa `components/Header.tsx`, các file test M2 trong `tests/m2/e2e/**`, và route `/test-driver`.
- Không chạy `npm ci` hay `npm install`.
- Toàn bộ các gọi `fetch` chỉ nằm bên trong `src/controlplane/ui/src/api/client.ts`. Không có fetch ngoài client.ts, không chứa sink XSS hoặc endpoint cấm.
- Không push, không merge và không vi phạm các ranh giới bảo vệ.
