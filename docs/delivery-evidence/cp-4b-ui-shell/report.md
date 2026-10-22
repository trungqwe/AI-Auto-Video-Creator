# Báo cáo chuyển giao CP-4B-UI-SHELL

## 1. Phạm vi thực hiện

- `src/controlplane/ui/src/App.tsx`:
  - Thay thế `Set` tự quản (`seenStreamEventIdsRef` khởi tạo bằng `new Set()`) bằng `BoundedEventDeduper` khởi tạo từ `createBoundedEventDeduper()` của `features/stream/boundedEventDeduper.ts`. Khử trùng lặp qua `seenBefore(id)` và làm sạch bằng `clear()` trong `onResync`.
  - Nối danh mục màn hình `screenRegistry` từ `features/screens/screenRegistry.ts` vào App shell thành tab chỉ đọc `Màn hình` (`tab-screens`) hiển thị component `ScreensPanel` (`data-testid="screens-panel"`).
  - Lọc các trường sửa được theo `FORBIDDEN_EDITABLE_FIELDS` (`visibleEditableFields`); shell không dựng bất kỳ ô nhập liệu nào.
  - Giữ nguyên các tab M2 (`tab-operations`, `tab-command`, `tab-batches`, `tab-jobs`) và dây nối nút kiểm thử `onOpenTestError={handleTriggerTestError}`.
- `src/controlplane/ui/dist/**`:
  - Dựng lại bản phân phối bằng `npm run build` trên runtime Node/D9 có sẵn.
  - Tệp băm mới sinh ra: `assets/index-BGSg0Sqj.js` và `assets/index-BGSg0Sqj.js.map`.
  - Hai tệp băm cũ đã được bản build dọn sạch: `assets/index-Dd0WysB0.js` và `assets/index-Dd0WysB0.js.map`.
  - Tệp `assets/index-CNmdI0B1.css` là tệp băm hiện hành: nội dung `index.css` không đổi nên băm không đổi, `dist/index.html` đang tham chiếu tệp này cùng `assets/index-BGSg0Sqj.js`, do đó giữ lại; xoá tệp này sẽ làm `index.html` trỏ tới tệp không tồn tại. Chỉ hai tệp băm cũ `index-Dd0WysB0.js` và `index-Dd0WysB0.js.map` cần vắng mặt và đã vắng mặt.

## 2. Lệnh đã chạy và kết quả

### Lệnh 1: `npm --prefix src/controlplane/ui run build`
Exit code: 0
Output:
```
> controlplane-admin-ui@0.2.0 build
> tsc && vite build

vite v6.2.0 building for production...
transforming...
✓ 39 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                     0.70 kB │ gzip:   0.44 kB
dist/assets/index-CNmdI0B1.css    231.37 kB │ gzip:  39.04 kB
dist/assets/index-BGSg0Sqj.js   1,066.64 kB │ gzip: 288.81 kB │ map: 3,494.52 kB

(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
✓ built in 2.06s
```

### Lệnh 2: `python -m pytest tests/unit/control_ui -q -p no:cacheprovider`
Exit code: 0
Output:
```
651 passed, 1 warning in 0.99s
```

### Lệnh 3: Probe `src/controlplane/ui/src/App.tsx`
Exit code: 0
Output:
```
python -c "import pathlib; t = pathlib.Path('src/controlplane/ui/src/App.tsx').read_text(encoding='utf-8'); assert 'boundedEventDeduper' in t and 'screenRegistry' in t, 'App.tsx must wire deduper and screen registry'; assert 'new Set' not in t, 'App.tsx must not keep its own Set'; assert 'onOpenTestError=' in t, 'BL-CV-13: keep test button wiring'"
=> Đạt (Exit code 0)
```

### Lệnh 4: Probe `src/controlplane/ui/dist`
Exit code: 0
Lệnh:
```sh
python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d / 'index.html').read_text(encoding='utf-8'); r = re.findall('assets/[A-Za-z0-9_.-]+', h); assert r and all((d / x).is_file() for x in r), r; assert not any((d / 'assets' / x).exists() for x in ['index-Dd0WysB0.js', 'index-Dd0WysB0.js.map']), 'old hashed files must be gone'; k = [f.name for f in (d / 'assets').iterdir() if f.is_file() and 'assets/' + f.name not in r and not (f.name.endswith('.map') and 'assets/' + f.name[:-4] in r)]; assert not k, ('orphan hashed files', k)"
```
Output: không có (probe đạt: mọi assets/* trong index.html là tệp thật, `index-Dd0WysB0.js` và `index-Dd0WysB0.js.map` không còn, không có tệp băm mồ côi)

### Lệnh 5: `git diff --check`
Exit code: 0
Output: Không có cảnh báo khoảng trắng (whitespace clean).

## 3. Trạng thái registry và màn hình

- `src/controlplane/ui/src/App.tsx` hiển thị `backendStatus` nguyên trạng từ `screenRegistry.ts` và không ghi đè giá trị.
- `src/controlplane/ui/src/features/screens/screenRegistry.ts` nằm ngoài `ownedPaths` nên được giữ nguyên.
- Các màn hình chỉ chuyển khỏi `pending_module` khi route tương ứng của CP-4 tồn tại. Hiện tại `control.py` chỉ có GET cho operations, batches, jobs, configs (trạng thái `available`).
- Đối chiếu sources, articles, events, media, hooks, snapshots, story-angles, scripts, stage-runs, sessions, logs, accounts, cost thuộc về các gói tiếp theo (`CP-4-WIRING`, `CP-4-QUERIES`, `CP-4B-UI-SCREENS`); việc mở rộng registry là follow-up, không tuyên bố đã hoàn thành.
- Bốn màn hình `available` (operations, batches, jobs, configs) khớp các route GET đang có trong `src/controlplane/api/routes/control.py`; mười bốn màn hình còn lại giữ `pending_module` vì route CP-4 tương ứng chưa tồn tại.
- Guard H-16 (`tests/unit/control_ui/test_h_ui_source_guard.py`) và `test_h_screen_registry.py` chạy trong Lệnh 2; `FORBIDDEN_EDITABLE_FIELDS` loại `article_body`, `script`, `secret` khỏi cột Trường sửa được, shell không dựng ô nhập.

## 4. Mục bị chặn (BL-CV-13)

BL-CV-13 — BLOCKED: nút handleTriggerTestError (prop onOpenTestError của components/Header.tsx) và đường /test-driver/issue-capability ở api/client.ts bị chặn vì hai spec M2 đóng băng bấm nút đó, auth-helper.ts dùng /test-driver và đường cấp phiên sản xuất chưa có; App.tsx giữ nguyên onOpenTestError=.

## 5. Mục chờ xử lý (BL-CV-07)

Các tệp UI sau nằm ngoài phong bì của nhiệm vụ CP-4B-UI-SHELL nên Worker không sửa và ghi nhận trạng thái PENDING theo quy định:
- `src/controlplane/ui/src/index.css` PENDING BL-CV-07 (chưa thêm CSS pill-waiting, pill-outcome-unknown, pill-unknown)
- `src/controlplane/ui/src/api/client.ts` PENDING BL-CV-07 (chưa chuyển sang dùng streamEventKinds, chưa bỏ eventKinds và Set)
- `src/controlplane/ui/src/components/OperationsGrid.tsx` PENDING BL-CV-07 (chưa nối StatusPill hoặc presentStatus)
- `src/controlplane/ui/src/components/BatchesGrid.tsx` PENDING BL-CV-07
- `src/controlplane/ui/src/components/JobsGrid.tsx` PENDING BL-CV-07
- `src/controlplane/ui/src/types/api.ts` PENDING BL-CV-07 (chưa mở rộng OperationItem, JobItem)
- `src/controlplane/ui/src/screens/**` PENDING BL-CV-07 (chưa tạo các màn hình chi tiết phân hệ)

Worker không sửa các tệp trên, đồng thời không sửa `src/controlplane/ui/src/api/streamEventKinds.ts` và `src/controlplane/ui/src/components/Header.tsx`.

## 6. Giới hạn và tuân thủ

- Worker không chạy `npm run test:e2e` (lệnh e2e do Control/Auditor thực thi và ghi nhận bằng chứng).
- Năm tệp spec M2 trong `tests/m2/e2e/` được giữ nguyên vẹn từng byte.
- Không tạo thêm spec `cp4b-*.spec.ts` mới khi chưa có chỉ thị.
- Không tuyên bố PASS e2e.
- Cổng kích hoạt sản xuất tiếp tục bị chặn (`PRODUCTION_ACTIVATION_BLOCKED`).
