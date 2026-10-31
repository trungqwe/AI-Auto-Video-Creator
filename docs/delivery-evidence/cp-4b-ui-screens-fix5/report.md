# Báo cáo giao hàng: CP-4B-UI-SCREENS-FIX5

## 1. Nhóm lỗi

`R34`: form tạo lô chưa cho user chọn số luồng video song song từ 1 tới mức tối đa theo quyết định user 31/10/2026 (CLOSURE_NOTE CP7/RG-10). PW-G6-FIX1 đã cho `POST /v1/batches` nhận `max_concurrent_videos` và `GET /v1/batch-settings` trả `{max_concurrent_videos: {default, min, max}}`, nhưng giao diện chưa dùng.

## 2. Các tệp đã sửa

- `src/controlplane/ui/src/types/api.ts`: thêm `BatchSettings`.
- `src/controlplane/ui/src/api/client.ts`: thêm `fetchBatchSettings()`; `startProductionBatch` có tham số thứ ba tuỳ chọn `maxConcurrentVideos?: number`, chỉ thêm `max_concurrent_videos` vào body khi khác `undefined`.
- `src/controlplane/ui/src/components/CommandForm.tsx`: ô `max-concurrent-select`, khoá nút gửi lúc tải cấu hình, chỉ gửi trường khi tải xong và max > 1.
- `tests/unit/control_ui/test_h_batch_concurrency_form.py` (mới).
- `src/controlplane/ui/dist/**` (dựng lại bằng `npm run build`).
- Báo cáo này.

## 3. RED

Lệnh: `python -m pytest tests/unit/control_ui/test_h_batch_concurrency_form.py -q -p no:cacheprovider` (trước khi sửa mã nguồn). Exit code: 1 (AssertionError).

```
FAILED tests/unit/control_ui/test_h_batch_concurrency_form.py::test_form_has_concurrency_select_and_loads_settings_once
FAILED tests/unit/control_ui/test_h_batch_concurrency_form.py::test_form_locks_submit_while_settings_load
FAILED tests/unit/control_ui/test_h_batch_concurrency_form.py::test_form_hides_select_when_max_not_above_one_and_sends_only_when_loaded
FAILED tests/unit/control_ui/test_h_batch_concurrency_form.py::test_client_exposes_batch_settings_and_optional_concurrency
FAILED tests/unit/control_ui/test_h_batch_concurrency_form.py::test_types_declare_batch_settings_without_any
FAILED tests/unit/control_ui/test_h_batch_concurrency_form.py::test_bundle_contains_select_and_settings_endpoint
6 failed in 0.28s
```

## 4. GREEN

| Bước | Lệnh | Exit code | Kết quả |
| --- | --- | --- | --- |
| 11 | `npm --prefix src/controlplane/ui run build` | 0 | `✓ built in 2.73s` |
| 12 | probe dist (4 tệp, không tệp băm mồ côi, bundle có `max-concurrent-select` và `/v1/batch-settings`) | 0 | không có output |
| 13 | `python -m pytest tests/unit/control_ui -q -p no:cacheprovider` | 0 | `681 passed, 1 warning in 1.76s` |
| 14 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7550 passed, 1 warning, 2561 subtests passed in 27.02s` |
| 15 | probe nguồn (form, client, types) | 0 | không có output |
| 16 | `git diff --check` | 0 | không có cảnh báo |

## 5. Tên tệp dist sau build

- `dist/index.html`
- `dist/assets/index-BgnRr_o6.js`
- `dist/assets/index-BgnRr_o6.js.map`
- `dist/assets/index-DNWUXu2_.css`

Tệp băm cũ `index-DV6jC0op.js` và `.map` đã bị xoá.

## 6. Giới hạn

- Worker không chạy `npm run test:e2e`, không tuyên bố e2e PASS; Control chạy khi đóng mốc.
- Lưới Lô sản xuất chưa hiện số luồng của từng lô (backlog).
- Số 10 luồng và mặc định 6 là tính toán của Control, chưa đo thật.
- Chưa có kiểm trình duyệt trong lane.

## 7. Tuân thủ

Không sửa `App.tsx`, `package.json`, `tests/m2`; không chạy `npm ci` hay `npm install`; `fetch` chỉ nằm ở `client.ts`; không push, không merge.
