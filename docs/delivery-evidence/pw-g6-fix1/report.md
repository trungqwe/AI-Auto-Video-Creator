# Báo cáo chuyển giao: mỗi lô chọn số luồng video 1-10 (PW-G6-FIX1)

Task: PW-G6-FIX1
Mã tham chiếu R34 (nêu trong lệnh kiểm của task)
Trạng thái: IMPLEMENTED

## 1. Tóm tắt và nhóm lỗi R34

Nhóm lỗi R34: lô trước đây luôn chạy K = 1 vì relay không bao giờ gửi khoá `max_concurrent_videos`, nên nhánh song song của PW-G5-FIX1 không bao giờ chạy trong production. Nay profile giữ `batch.max_concurrent_videos` = `{default 6, max 10}` (basis DECIDED, `meta.revision` 4 lên 5); `POST /v1/batches` cho chọn từ 1 tới mức tối đa; payload sự kiện outbox `production_batch.start_accepted` và input workflow chỉ có khoá `max_concurrent_videos` khi K > 1.

Đường đi của số luồng:

1. Launcher nạp profile; `build_production_app` kiểm `max <= MAX_VIDEO_STREAMS` (10) rồi gắn `api_app.state.batch_concurrency = BatchConcurrency(6, 10)`.
2. `POST /v1/batches` truyền `batch_concurrency` (hoặc `SEQUENTIAL` khi app không có state) vào `start_batch`. Target kiểm trước; sau đó `resolve(payload, limits)` trả K (thiếu khoá thì mặc định 6); sai thì `BatchFieldError` và route trả 422 `VALIDATION_FAILED` kèm `field_errors.max_concurrent_videos`, trước khi mở UoW.
3. `start_batch` ghi `max_concurrent_videos` vào payload `start_accepted` chỉ khi K > 1.
4. `OutboxRelay._request` đọc khoá, bỏ qua sự kiện nếu không phải int, là bool hoặc < 1, và thêm khoá vào input `ProductionBatchWorkflow` chỉ khi K > 1.
5. `BatchParams.from_payload` (PW-G5-FIX1) chọn nhánh `_run_concurrent(K)`.

`GET /v1/batch-settings` trả `{'max_concurrent_videos': {'default', 'min': 1, 'max'}}` từ cùng giá trị.

Giá trị profile: `batch.max_concurrent_videos` = `{"default": 6, "max": 10}`, basis `DECIDED`; `meta.revision.value` = 5; `gpu.slots` giữ `{"lock": "LOCK-DESKTOP-GPU", "slots": 2}`.

## 2. Tệp đã đổi

- `tools/launcher/prod/profile.json`: khoá mới và `meta.revision` 5.
- `src/controlplane/api/wiring/production_profile.py`: 85 khoá bắt buộc, kiểm giá trị `{default, max}`.
- `src/controlplane/application/control_api/batch_concurrency.py` (mới): `BatchConcurrency`, `SEQUENTIAL`, `BatchFieldError`, `resolve`.
- `src/controlplane/application/control_api/commands.py`: `start_batch` nhận `concurrency`, payload sự kiện.
- `src/controlplane/api/routes/control.py`: `POST /v1/batches` bắt `BatchFieldError`; route `GET /v1/batch-settings`.
- `src/controlplane/api/wiring/production.py`: gắn `state.batch_concurrency`, kiểm trần máy.
- `src/controlplane/infrastructure/db/orchestration/outbox_relay.py`: `_request` chuyển khoá khi K > 1.
- `docs/runbook/runbook-v1.md`, `docs/implementation/adapt/plan.md`: dòng `batch.max_concurrent_videos`.
- `tests/integration/prod_wiring/test_pw_g6_fix1_batch_settings.py` (mới).
- `tests/integration/adapt/config/test_adapt_config_profile.py`, `tests/integration/adapt/wire/test_adapt_wire_services.py`, `tests/integration/adapt/prod/test_adapt_prod_app.py`: 85 khoá, test giá trị và test state.
- `docs/delivery-evidence/pw-g6-fix1/report.md` (mới).

## 3. Bằng chứng RED (mã cũ)

- Bước 5: `python -m pytest tests/integration/prod_wiring/test_pw_g6_fix1_batch_settings.py -q -p no:cacheprovider`, exit code 1, `38 failed, 3 passed in 9.27s`. Các test dùng `bc()` (resolve, giới hạn, SEQUENTIAL, POST, GET `/v1/batch-settings`) hỏng vì `ModuleNotFoundError` của `batch_concurrency`: ghi nhận, không tính RED oracle. Test relay hỏng vì assertion trên mã cũ: `test_relay_forwards_concurrency_above_one` (input không có khoá) và `test_relay_skips_invalid_concurrency_without_blocking` (`assert 2 == 1`, relay vẫn start với 0, -1, True, 'x', 1.5). Ba test đạt là test relay K = 1 (hai ca) và test docstring `coveredIds`.
- Bước 9: ba tệp adapt, exit code 1, `16 failed, 165 passed in 30.38s`. RED hợp lệ bằng assertion: `test_profile_has_exactly_the_required_parameters` (còn 84), `test_batch_max_concurrent_videos_is_decided` và `test_batch_max_concurrent_videos_loads_default_and_max` (thiếu khoá trong profile), `test_profile_loads_typed_values` (84 khác 85), 10 ca `test_invalid_batch_max_concurrent_videos_names_it`. Test prod app: `test_batch_max_above_machine_capacity_does_not_start` hỏng `DID NOT RAISE ProductionProfileError`; `test_production_app_carries_batch_concurrency_from_profile` hỏng vì thiếu mô-đun/state (ghi nhận).

## 4. Lệnh đã chạy trên mã mới

| Lệnh | Exit code | Dòng tổng kết pytest / kết quả |
| --- | --- | --- |
| test mới + PW-G6 relay + PW-G5-FIX1 (bước 19) | 0 | `57 passed in 31.67s` |
| config + wire + prod app + launch CLI (bước 20) | 0 | `220 passed in 30.79s` |
| `test_pw_e2e_batch_video.py` (bước 21) | 0 | `10 passed in 163.70s (0:02:43)` |
| `python -m pytest tests/unit -q -p no:cacheprovider` (bước 22) | 0 | `7544 passed, 2561 subtests passed in 30.65s` |
| probe profile, loader, control/commands/production, relay/wire/runbook, `report.md` và `git diff --check` | xem mục 7 | chạy sau khi ghi báo cáo, kết quả trong thông báo `worker_done` |

## 5. Quyết định thiết kế

- Kiểm target trước số luồng; lỗi target vẫn là `VALIDATION_ERROR` (h24), lỗi số luồng là `VALIDATION_FAILED` 422 với `field_errors`.
- Hash idempotency vẫn tính trên payload thô.
- Không chặn trường lạ trong payload (h08).
- Route `GET /v1/batch-settings` nằm ngoài `/v1/batches/` vì `/batches/{batch_id}` parse UUID.
- K = 1 (hoặc thiếu khoá) giữ đúng 5 khoá ở payload sự kiện và input workflow.
- `gpu.slots` giữ 2; không migration; không sửa `docs/09-contracts`.
- App không có profile (test_driver, M2) dùng `SEQUENTIAL` (1, 1).
- Launcher và relay không đọc K từ profile; K không nằm trong `WorkflowSettings`.

## 6. Giới hạn

- Số 10 luồng và mặc định 6 là tính toán của Control (CPU 7950X bão hòa khoảng 146 video mỗi giờ), chưa đo 10 luồng thật; CP7-11 đo thật để chỉnh mức tối đa.
- Giao diện chọn số luồng chưa thuộc gói này.
- `meta.revision` 5 đổi `policy_revision` thành `profile-5`; lane đang chạy chỉ nhận khi rebase hoặc cấp lại.
- Sự kiện tạo lô có trước khi gộp không mang khoá nên chạy tuần tự.

## 7. Kiểm tra cuối

Đã đọc lại báo cáo này sau khi ghi và xác nhận chữ có dấu tiếng Việt còn nguyên. Kết quả `git diff --check` và các probe ghi trong thông báo `worker_done`.
