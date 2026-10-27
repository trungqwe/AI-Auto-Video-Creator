# Báo cáo Nghiệm thu Kỹ thuật: PW-F4 (Phân hệ F)

## 1. Phạm vi và Nguồn kế hoạch

- **Mã nhiệm vụ:** `PW-F4`
- **Milestone:** M7 (Production Wiring)
- **Kế hoạch cơ sở:** `IMPL-PLAN-PROD-WIRING-V4` (đã được nghiệm thu và duyệt).
- **Mục tiêu kỹ thuật cốt lõi:**
  1. Đảm bảo một tiến trình render video chỉ `acquire` đúng một lần `LocalGpuLease`: `RenderPipeline.render_video` giữ lease và chuyển xuống cho `RealFfmpegRenderer.run` qua cờ `takes_held_lease = True`; `RealFfmpegRenderer` nhận lease đã giữ, không tự acquire hoặc release (với cấu hình `gpu.slots: 2`, một render chỉ chiếm đúng một khe).
  2. Bổ sung định tuyến activity trong `handle_activity` cho `reconcile_render` (kết luận các attempt `STARTED` mồ côi thành kết quả xác định dựa trên `orphan_after_seconds`) và `prepare_output_ready` (F-19); xử lý mã lỗi `OUTPUT_NOT_READY`.
  3. Xây dựng adapter sản xuất `RenderActivityInputs` (`ActivityInputPort` của F) để phân giải `input_refs` thành các lệnh có kiểu cho cả 6 activity: `resolve_render_package`, `validate_render_package`, `reconcile_render`, `render_video`, `inspect_output`, `prepare_output_ready`.
  4. Đảm bảo `inspect_output` đọc `segments` từ `cp_script_versions` qua `read_script_segments` và `word_timings` từ `cp_word_timings` theo `word_timing_ref`; thiếu dữ liệu phải báo lỗi có mã rõ ràng (`SCRIPT_NOT_FOUND`, `WORD_TIMING_NOT_FOUND`), tuyệt đối không truyền danh sách rỗng khi script có segment suy luận.

---

## 2. Thay đổi theo tệp

- **`src/render/application/render_video.py`:**
  - `RenderPipeline.render_video`: Chuyển lease đã acquire xuống renderer thông qua phương thức `_run_renderer` khi renderer khai báo `takes_held_lease = True`.
  - `RenderPipeline._verify`: Chuẩn hóa so sánh `outcome.output_ref` và `started.output_artifact_ref` (hỗ trợ phân cách đường dẫn Windows và Linux).
  - `ReconcileRenderCommand`: Thêm trường `orphan_after_seconds: int | None = None` kèm kiểm tra kiểu không âm trong `__post_init__`.
  - `RenderPipeline.reconcile_render`: Thêm hằng số `REASON_WORKER_LOST = 'worker_lost_after_start'`, đăng ký `OperationState.OUTCOME_UNKNOWN` vào `_RECONCILE_OUTCOMES`. Nếu attempt ở trạng thái `STARTED` và đã vượt quá `orphan_after_seconds`, chuyển thành `OUTCOME_UNKNOWN` với lý do `worker_lost_after_start` rồi tiến hành reconcile xác định (SUCCEEDED nếu output tồn tại decodable, FAILED nếu output thiếu). Nếu còn trẻ hơn `orphan_after_seconds`, ném `AttemptInProgress`.
- **`src/render/adapters/real_ffmpeg_renderer.py`:**
  - Khai báo thuộc tính lớp `takes_held_lease = True`.
  - Cập nhật phương thức `run(self, spec: RenderCommandSpec, *, lease: GpuLease) -> RendererOutcome`: Nhận `lease` keyword-only, kiểm tra kiểu `isinstance(lease, GpuLease)` trước khi verify pin FFmpeg.
  - Loại bỏ hoàn toàn các lệnh `self._lease.acquire()` và `self._lease.release()` trong renderer.
  - Trong `_rewrite_graph`: Thêm xử lý escape dấu hai chấm cho filter `subtitles` trên đường dẫn Windows (`\\:` -> `\\\\:`).
- **`src/render/worker/activity_handler.py`:**
  - Bổ sung định tuyến `reconcile_render` (`_run_reconcile`, `_reconcile_outcome`) và `prepare_output_ready` (`_run_prepare`, `_prepare_outcome`).
  - Thêm hằng số lỗi `OUTPUT_NOT_READY = 'output_not_ready'`, `NOTHING_TO_RECONCILE = 'nothing_to_reconcile'`, ref type `REF_TYPE_VIDEO_OUTPUT = 'video_output'`.
  - Cập nhật tuple `ACTIVITY_NAMES` bao gồm đầy đủ 6 activity.
  - `_command`: Cho phép `key_field` nhận `str | None` để hỗ trợ lệnh không gắn trực tiếp operation_key vào field cố định.
- **`src/render/adapters/activity_inputs.py`:**
  - Tạo mới module cài đặt `RenderActivityInputs` (`ActivityInputPort` của phân hệ F).
  - Phân giải `input_refs` thành lệnh có kiểu: `ResolveRenderPackageCommand`, `ValidateRenderPackageCommand`, `ReconcileRenderCommand`, `RenderVideoCommand`, `InspectOutputCommand`, `PrepareOutputReadyCommand`.
  - Đọc `segments` từ `cp_script_versions` bằng `read_script_segments(db, workspace_id, script_version_ref)`.
  - Đọc `word_timings` từ `cp_word_timings` bằng query SQL chuyên biệt theo `timing_artifact_ref`.
  - Xử lý các lỗi ref: `INPUT_REF_MISSING`, `INPUT_REF_AMBIGUOUS`, `SCRIPT_NOT_FOUND`, `WORD_TIMING_NOT_FOUND`, `WORD_TIMING_INVALID`, `SEGMENTS_EMPTY`.
- **`src/controlplane/application/orchestration/workflows/activities.py`:**
  - **Xác nhận KHÔNG ĐỔI:** Hai binding `reconcile_render` và `prepare_output_ready` cùng các stage tương ứng đã được tích hợp từ `PW-CAT1`, và `FAN_OUT_FROM_OUTPUT` không cần thay đổi.

---

## 3. Bảng từng dòng test đã đổi cùng lý do

| Tệp kiểm thử | Vị trí dòng | Thay đổi thực hiện | Lý do kỹ thuật |
|---|---|---|---|
| `tests/integration/render/test_f20_worker_activity.py` | 328 | Tham số hóa ca test `test_unknown_activity_name_returns_a_structured_problem_without_running_anything` rút gọn từ `['bogus_activity', 'RenderVideo', 'prepare_output_ready', 'reconcile_render']` còn `['bogus_activity', 'RenderVideo']`. | `reconcile_render` và `prepare_output_ready` nay là các activity được hỗ trợ chính thức bởi handler, không còn là activity không xác định. |
| `tests/integration/render/test_f20_worker_activity.py` | 341-342 | Cập nhật assertion `ah.ACTIVITY_NAMES` thành bộ 6 activity (`resolve_render_package`, `validate_render_package`, `reconcile_render`, `render_video`, `inspect_output`, `prepare_output_ready`). | Khớp với catalog workflow của F theo hợp đồng PW-F4. |
| `tests/integration/render/test_f20_worker_activity.py` | 467-548 | Thêm 6 ca kiểm thử mới: 4 ca reconcile (`test_reconcile_activity_settles_an_unknown_attempt_with_its_output`, `test_reconcile_activity_of_a_missing_output_is_a_definite_failed_attempt`, `test_reconcile_activity_gives_a_definite_result_for_an_orphaned_started_attempt`, `test_reconcile_activity_without_an_open_attempt_is_a_no_op_success`) và 2 ca prepare (`test_prepare_activity_returns_the_video_output_after_a_passing_qc`, `test_prepare_activity_after_a_failed_qc_is_not_ready`). | Kiểm thử bao phủ nhánh thực thi của 2 route activity mới trong `activity_handler`. |
| `tests/integration/adapt/f/test_adapt_f_render.py` | 87-99 | Trong `FakeLease`: Bỏ cờ `self.unavailable = False` và nhánh `raise GpuLeaseUnavailable()`. | `RealFfmpegRenderer` không tự acquire hay release lease nữa, quyền quản lý lease thuộc về `RenderPipeline`. |
| `tests/integration/adapt/f/test_adapt_f_render.py` | 108 | Thêm `self.held = GpuLease(lease_id='lease-held', owner_ref='render-attempt-1')` vào `Rig`. | Cung cấp lease đã được giữ sẵn bởi pipeline cho các lời gọi `renderer.run()`. |
| `tests/integration/adapt/f/test_adapt_f_render.py` | 169-308 | Mọi lời gọi `rig.renderer().run(...)` bổ sung đối số `lease=rig.held`. | `RealFfmpegRenderer.run()` yêu cầu `lease: GpuLease` là tham số bắt buộc (keyword-only). |
| `tests/integration/adapt/f/test_adapt_f_render.py` | 199, 213, 228, 236, 244 | Đổi assertion sự kiện lease của `rig.lease.events` thành `== []`. | `RealFfmpegRenderer` không tương tác với `FakeLease` của rig, chứng minh adapter không tự ý acquire/release. |
| `tests/integration/adapt/f/test_adapt_f_render.py` | 295-299 | Đổi ca `test_gpu_lease_unavailable_runs_nothing` thành `test_run_refuses_a_missing_lease_and_runs_nothing` kiểm tra `TypeError('lease must be a held GpuLease')`. | Ca kiểm thử GPU lease không khả dụng đã được bao phủ toàn diện ở `test_f18_render_video_pipeline.py` dòng 316-323; adapter cần xác nhận từ chối khi thiếu lease. |
| `tests/integration/adapt/f/test_adapt_f_render.py` | 301-309 | Đổi tên ca test thành `test_a_process_that_cannot_start_leaves_the_lease_to_the_caller` và assert `rig.lease.events == []`. | Tiến trình không khởi động được thì lease vẫn do caller quản lý, adapter không chạm vào lease. |
| `tests/integration/adapt/f/test_adapt_f_render.py` | 311-313 | Thêm ca test `test_renderer_declares_that_it_takes_a_held_lease`. | Kiểm tra contract cờ `takes_held_lease = True` của `RealFfmpegRenderer`. |

*Xác nhận: Không có bài kiểm tra nào bị xóa; không có bất kỳ oracle kiểm thử nào bị nới lỏng.*

---

## 4. Bạng chứng RED và GREEN thật

### 4.1. Bằng chứng RED trước khi sửa mã nguồn

#### Bước 3: RED của `tests/integration/adapt/f/test_adapt_f_render.py`
- **Lệnh thực thi:**
  ```bash
  python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider
  ```
- **Kết quả:** Exit code `1`
- **Thông tin lỗi xác thực oracle RED:**
  - 14 ca kiểm thử ném lỗi `TypeError: RealFfmpegRenderer.run() got an unexpected keyword argument 'lease'` do chữ ký `run()` cũ chưa nhận `lease`.
  - Ca kiểm thử `test_renderer_declares_that_it_takes_a_held_lease` ném lỗi `AttributeError: type object 'RealFfmpegRenderer' has no attribute 'takes_held_lease'`.
  - Tổng kết: `15 failed, 1 passed in 0.42s`. Không có lỗi cú pháp hay import.

#### Bước 11: RED của `tests/integration/render/test_f20_worker_activity.py`
- **Lệnh thực thi:**
  ```bash
  python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:cacheprovider
  ```
- **Kết quả:** Exit code `1`
- **Thông tin lỗi xác thực oracle RED:**
  - `test_supported_activity_names_are_the_six_f_commands` thất bại do `ah.ACTIVITY_NAMES` cũ chỉ có 4 tên:
    `AssertionError: assert ('resolve_render_package', 'validate_render_package', 'render_video', 'inspect_output') == ('resolve_render_package', 'validate_render_package', 'reconcile_render', 'render_video', 'inspect_output', 'prepare_output_ready')`.
  - 6 ca kiểm thử route mới thất bại vì `handle_activity` trả mã lỗi `UNKNOWN_ACTIVITY`.
  - Tổng kết: `7 failed, 15 passed in 0.58s`.

---

### 4.2. Bằng chứng GREEN sau khi hoàn thiện triển khai

#### Lệnh kiểm 1: Kiểm tra định dạng git diff
- **Lệnh thực thi:**
  ```bash
  git diff --check
  ```
- **Kết quả:** Exit code `0` (không có lỗi khoảng trắng, thụt đầu dòng hay xuống dòng thừa).

#### Lệnh kiểm 2: Chạy 5 tệp kiểm thử tích hợp và đơn vị của task
- **Lệnh thực thi:**
  ```bash
  python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py tests/integration/render/test_f20_worker_activity.py tests/integration/adapt/f/test_adapt_f_render.py tests/integration/render/test_f18_render_video_pipeline.py tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider
  ```
- **Kết quả:** Exit code `0`
- **Dòng tổng kết pytest:**
  ```text
  173 passed, 125 subtests passed in 37.34s
  ```

#### Lệnh kiểm 3: Xác minh symbol, định tuyến và ranh giới import
- **Lệnh thực thi:**
  ```bash
  python -c 'import pathlib; t = pathlib.Path(''src/render/worker/activity_handler.py'').read_text(encoding=''utf-8''); a = pathlib.Path(''src/render/adapters/activity_inputs.py'').read_text(encoding=''utf-8''); assert ''reconcile_render'' in t and ''prepare_output_ready'' in t and ''segments'' in a and ''from src.'' not in t, ''PW-F4'''
  ```
- **Kết quả:** Exit code `0`.

#### Kiểm thử chuyên biệt `test_pw_f4_render_worker.py` (Bước 23)
- **Lệnh thực thi:**
  ```bash
  python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py -q -p no:cacheprovider
  ```
- **Kết quả:** Exit code `0`
- **Dòng tổng kết pytest:**
  ```text
  12 passed in 33.77s
  ```

---

## 5. Bảng mã phủ (Coverage IDs)

| Mã phủ | Tên bài kiểm thử thực tế | Kết quả | Trọng tâm kiểm chứng |
|---|---|---|---|
| `PW-F4-01` | `test_one_render_takes_exactly_one_gpu_slot` | **PASSED** | Một render duy nhất chỉ `acquire` đúng 1 khe GPU (`gpu.acquires == 1`, `gpu.max_held == 1`). |
| `PW-F4-01` | `test_two_concurrent_renders_use_two_slots_and_the_third_waits` | **PASSED** | Hai render đồng thời dùng 2 khe (`gpu.slots: 2`), render thứ ba bị từ chối với `GpuLeaseNotAvailable` (`refused == 1`), sau khi nhả khe render lại thành công. |
| `PW-F4-01` | `test_f_activities_are_bound_and_staged` | **PASSED** | Cả 6 activity của F có trong catalog binding, gán đúng stage (`render`, `qc`) và có mặt đầy đủ trong `activity_handler.ACTIVITY_NAMES`. |
| `CT-QC-001` | `test_inspect_output_disclosure_gate_follows_the_script_segments` | **PASSED** | Script có segment `inference` và file ASS có dòng `Disclosure` -> cổng `INFERENCE_DISCLOSURE_PRESENT` đạt trạng thái **PASSED**; `InspectOutputCommand` có `segments` và `word_timings` đầy đủ. |
| `CT-QC-001` | `test_inspect_output_fails_when_the_ass_has_no_disclosure_line` | **PASSED** | Script có segment `inference` nhưng file ASS thiếu dòng `Disclosure` -> cổng `INFERENCE_DISCLOSURE_PRESENT` trả **FAILED**. |
| `CT-QC-001` | `test_inspect_output_is_not_applicable_for_a_source_backed_script` | **PASSED** | Script chỉ có segment `source_backed` -> cổng `INFERENCE_DISCLOSURE_PRESENT` trả **NOT_APPLICABLE** (không phải **FAILED**). |
| `CT-QC-001` | `test_inspect_output_without_script_or_timing_is_a_clear_error_not_empty_segments` | **PASSED** | Thiếu script ném lỗi có mã `SCRIPT_NOT_FOUND`; thiếu timing ném lỗi `WORD_TIMING_NOT_FOUND`. Không truyền danh sách rỗng để bypass gate. |
| `F-19` | `test_prepare_output_ready_runs_after_qc` | **PASSED** | `prepare_output_ready` chạy ngay sau `inspect_output`, trả về ref `video_output` đúng định dạng khi QC đạt và báo lỗi `output_not_ready` khi QC trượt. |

---

## 6. Mục mở và theo dõi

1. **Cấu hình `orphan_after_seconds`:** Khi wiring tổng thể dựng `RenderActivityInputs`, giá trị này cần được trích xuất từ cấu hình render timeout cộng thêm một khoảng grace period phù hợp thay vì đặt hằng số cố định.
2. **Đồng bộ danh sách `segments` cho `RealOutputInspector`:** `RealOutputInspector` nhận `segments` thông qua `InspectionInputs`, do đó tầng wiring phải đảm bảo khởi dựng inspector với cùng danh sách `segments` mà `ActivityInputPort` cung cấp cho `InspectOutputCommand`.
3. **Tiến trình render mới sau reconcile SUCCEEDED:** Theo thiết kế của pipeline F, sau khi `reconcile_render` kết luận một attempt thành công, nếu activity `render_video` được gọi lại với cùng gói package thì một attempt mới vẫn sẽ được tạo (xử lý logic điều phối này nằm ở workflow Control Plane thuộc phân hệ G, ngoài phạm vi của gói F).
4. **Nguồn dữ liệu đầu vào thực tế (`RenderInputSources`):** Các nguồn triển khai thực tế cho `workspace_id`, `plan_assets`, `script_versions` và `word_timings` sẽ được kết nối hoàn chỉnh tại slice wiring của Phân hệ A / G.
