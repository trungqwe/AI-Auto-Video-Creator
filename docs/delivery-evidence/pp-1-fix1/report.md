# Báo cáo bằng chứng chuyển giao: PP-1-FIX1

## 1. Phạm vi thực hiện

Mã tham chiếu R34 (nêu trong lệnh kiểm của task).

Nguồn quyết định: user 31/10/2026 (CLOSURE_NOTE CP7/RG-10). `gpu.slots` giữ 2; không đổi `profile.json`; không thêm kind mới; không sửa `tests/real`.

Các tệp đã sửa:
- `src/render/ports/lease.py`: thêm `GpuLeaseWaitExpired(GpuLeaseUnavailable)`; sửa docstring module, `GpuLeaseUnavailable`, `GpuLeasePort.acquire`; bỏ cụm "caller waits (G sets WAITING_CAPABILITY)"; `__all__` có lớp mới.
- `src/controlplane/infrastructure/production_ports/gpu_lease.py`: `LocalGpuLease` thêm kw `wait_seconds` (mặc định 0, số hữu hạn >= 0, không bool); `threading.Lock` thành `threading.Condition`; `acquire` giữ nguyên, không chờ; thêm `acquire_waiting` (chờ có trần bằng `Condition.wait`, dọn lease quá TTL mỗi vòng, thức đúng lúc lease sớm nhất hết TTL); `release` gọi `notify_all`; `waiting_port()` trả một đối tượng `_WaitingPort` duy nhất.
- `src/controlplane/infrastructure/production_ports/ports_config.py` và `tools/launcher/prod/ports.json`: `gpu_lease` nhận đúng hai khoá `grace_seconds`, `wait_seconds`; `wait_seconds` = 180 (số nguyên dương); `revision` 1 thành 2.
- `src/controlplane/infrastructure/production_ports/assembly.py`: truyền `wait_seconds` cho `LocalGpuLease`; từ chối bằng `ValueError` (nêu `gpu_lease.wait_seconds`, `render.timeout_seconds`, `workflow.start_to_close_seconds`) khi `wait_seconds + ceil(render.timeout_seconds) >= start_to_close[desktop-render]` (180 + 900 < 1200); kiểm tra nằm trước mọi cuộc gọi mạng.
- `src/controlplane/api/wiring/render.py`: `render_activity_deps` đưa `waiting_port()` vào `RenderPipeline` khi `runtime.gpu_lease` là `LocalGpuLease`, còn lại giữ nguyên đối tượng.
- `src/render/application/render_video.py`: bắt `GpuLeaseWaitExpired` trước `GpuLeaseUnavailable`, ném `GpuLeaseNotAvailable` mã `gpu_lease_wait_expired`, category `capacity`, `retryable=False`, status 503; nhánh cũ giữ `retryable=True`.
- `src/render/worker/activity_handler.py`: mô tả `CAPACITY_UNAVAILABLE` thành "no GPU slot was free within the wait limit; nothing was rendered"; kind giữ nguyên.
- Test: `tests/integration/prod_ports/test_pp_1_gpu_lease.py`, `test_pp_2_credentials.py`, `test_pp_8_assembly.py`, `tests/integration/render/test_f18_render_video_pipeline.py`, `test_f20_worker_activity.py`, `tests/integration/prod_wiring/test_pw_w2_launcher_def.py` (một dòng).

Thời gian chờ suất GPU đo được (clock thật `time.monotonic`):
- Trong test chờ: luồng khác release sau 0,2 s thì `acquire_waiting` lấy được suất sau 0,206 s (test yêu cầu < 1 s).
- Trong test hết hạn: `wait_seconds` = 0,3 thì `GpuLeaseWaitExpired` được ném sau 0,306 s, không để lại lease.
- Lease rò (TTL 0,3 s, wait 5 s): luồng chờ thức và lấy suất sau 0,306 s.

## 2. Bằng chứng RED

Trước khi sửa mã production (chỉ `lease.py` đã có `GpuLeaseWaitExpired` để test thu thập được).

Bước 10, lệnh `python -m pytest tests/integration/prod_ports/test_pp_1_gpu_lease.py tests/integration/prod_ports/test_pp_2_credentials.py tests/integration/prod_ports/test_pp_8_assembly.py -q -p no:cacheprovider`, exit 1 (mong đợi):
- Dòng tổng kết: `28 failed, 132 passed in 24.21s`.
- Loại lỗi: `TypeError` (`wait_seconds`, `GpuLeasePortsConfig.__init__() got an unexpected keyword argument 'wait_seconds'`), `AttributeError` (`acquire_waiting`, `_wait_seconds`, `waiting_port`) và `AssertionError`.
- FAILED: 19 ca mới của `test_pp_1_gpu_lease.py`; `test_pp_2_credentials.py::test_real_ports_json_loads_with_expected_values` và `test_missing_key_is_rejected[keys6]`; `test_pp_8_assembly.py::test_gpu_lease_uses_profile_slots_and_ttl`, `test_gpu_lease_changes_with_the_profile_values`, `test_gpu_lease_wait_seconds_is_taken_from_the_ports_config`, ba ca `test_assembly_rejects_wait_plus_render_timeout_not_below_start_to_close`, `test_assembly_accepts_wait_plus_render_timeout_just_below_start_to_close`.

Bước 11, lệnh `python -m pytest tests/integration/render/test_f18_render_video_pipeline.py tests/integration/render/test_f20_worker_activity.py -q`, exit 1 (mong đợi):
- Dòng tổng kết: `2 failed, 85 passed in 0.69s`.
- FAILED: `test_f18_render_video_pipeline.py::test_gpu_lease_wait_expired_is_a_non_retryable_capacity_rejection_before_any_attempt` và `test_f20_worker_activity.py::test_a_wait_expired_gpu_lease_gives_a_non_retryable_capacity_problem`, cùng `AssertionError` (`gpu_lease_unavailable` != `gpu_lease_wait_expired`, retryable True).

## 3. Bằng chứng GREEN

| Bước | Lệnh | Exit | Dòng tổng kết pytest |
| --- | --- | --- | --- |
| 20 | pytest `test_pp_1_gpu_lease.py`, `test_pp_2_credentials.py`, `test_pp_8_assembly.py` | 0 | `160 passed in 22.93s` |
| 21 | pytest `test_pw_f4_render_worker.py`, `test_pw_f1_inspector_visual.py` | 0 | `60 passed in 53.51s` |
| 22 | pytest `test_f18_render_video_pipeline.py`, `test_f20_worker_activity.py`, `tests/integration/adapt/f/test_adapt_f_render.py` | 0 | `141 passed in 4.22s` |
| 23 | pytest `test_pw_w2_launcher_def.py`, `test_pw_w1_launcher_core.py`, `test_pw_h0_harness.py` | 0 | `58 passed in 16.09s` |
| 24 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7524 passed, 2561 subtests passed in 22.77s` |
| 25 | probe `gpu_lease.py` (lease, PP-1) | 0 | không có AssertionError |
| 26 | probe `ports.json` | 0 | không có AssertionError |
| 27 | probe `render_video.py` và `lease.py` | 0 | không có AssertionError |
| 28 | probe wiring, assembly, activity_handler | 0 | không có AssertionError |
| 29 | probe PP-2 | 0 | không có AssertionError |
| 30 | probe PW-F4 | 0 | không có AssertionError |
| 32 | probe báo cáo này | 0 | không có AssertionError |
| 33 | `git diff --check` | 0 | không có cảnh báo |

## 4. Ánh xạ yêu cầu nghiệm thu (1)

1. `lease.py`: `GpuLeaseWaitExpired`; test `test_acquire_waiting_expires_after_wait_seconds_and_leaves_no_lease`.
2. `gpu_lease.py`: `wait_seconds`, `Condition`, `acquire_waiting`, `waiting_port`; các test mới trong `test_pp_1_gpu_lease.py` (chờ rồi lấy suất, hết hạn, lease rò thu hồi, 10 luồng 2 suất đỉnh không quá 2, `acquire` vẫn ném ngay, wait 0, constructor từ chối wait sai, `waiting_port` ổn định).
3. `ports.json` và `ports_config.py`: `test_pp_2_credentials.py` (thiếu khoá, giá trị sai, `ports.json` thật wait 180, revision 2).
4. `assembly.py`: `test_pp_8_assembly.py` (`_wait_seconds` bằng ports_config; từ chối khi wait + ceil(timeout) >= start_to_close).
5. `wiring/render.py`: `test_pw_w2_launcher_def.py` (`deps.render._lease is runtime.gpu_lease.waiting_port()`); PW-F4 giữ nguyên.
6. `render_video.py`: `test_f18_render_video_pipeline.py` (code `gpu_lease_wait_expired`, retryable False, renderer không được gọi, không attempt nào được ghi).
7. `activity_handler.py`: `test_f20_worker_activity.py` (disposition failed, kind `CAPACITY_UNAVAILABLE`, retryable False).

Phản ví dụ đã loại trừ:
- Không chờ trong workflow, không đổi `gpu.slots`, không thêm khoá profile.
- `acquire` không chờ (probe `gpu_lease_ready` không treo; test `acquire` vẫn ném ngay khi có luồng đang chờ).
- Dùng `Condition` thay vì `sleep` cố định; chờ có trần `wait_seconds`.
- `wait_seconds` mặc định 0 nên các nơi dựng `LocalGpuLease(slots, ttl)` vẫn chạy.
- `GpuLeaseWaitExpired` retryable False; không thêm kind mới.
- Giữ kiểm tra `wait + ceil(render timeout) < start_to_close`.
- Test vòng chờ dùng clock thật, không dùng `ManualClock`, không monkeypatch mã production; không sửa `tests/real`.

## 5. Giới hạn

- Không chạy `tests/real`; không push hay merge.
- `PRODUCTION_ACTIVATION_BLOCKED` giữ nguyên.
- Số 10 luồng song song là tính toán của Control, chưa đo thật; huỷ activity không truyền xuống luồng đang chờ (MINOR, backlog).
- Báo cáo không chứa bí mật.
