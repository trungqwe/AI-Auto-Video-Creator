# Báo cáo nghiệm thu PW-E3: ImageSafetyPolicy, NormalizeSpec và ActivityInputPort E

## 1. Mục tiêu và phạm vi
- **Mục tiêu:**
  + 1. `ImageSafetyPolicy` và `NormalizeSpec` dựng từ tham số profile production (khoá đã có; khoá thiếu thì ghi vào evidence và báo BLOCKED về Control, không bịa số); không `os.environ`.
  + 2. `ActivityInputPort` E production phân giải `input_refs` thành đầu vào có kiểu cho `CreateVoiceTrack`, `CreateWordTiming`, `ProbeMedia`, `AssessImageSafety`, `TransformSensitiveImage`, `NormalizeMedia`, `PrepareAudioBed`: script từ `ScriptTextPort`, ảnh từ từng item `selected_media` của fan-out, cue từ plan.
  + 3. `AssessImageSafety` trả cho mỗi ảnh một `output_ref` kiểu `image_safety_assessment`; ảnh cần che ra thêm item cho `TransformSensitiveImage`; ảnh không an toàn hoặc không chắc chắn không bao giờ thành safe và bị loại khỏi `NormalizeMedia` (DQ-11); thiếu ảnh sau khi loại thì dùng media seed dự phòng của selection.
  + 1. Chỉ sửa owned paths ở trên. Khi cuối tệp có lệnh làm việc của Orchestrator, đó là chỉ đạo chi tiết: làm đúng từng bước.
  + 2. Chạy đủ lệnh kiểm; ghi lại stdout/stderr và exit code.
  + 3. Commit local đúng một commit (không push, không merge).
  + 1. **CREATE** `src/voice/adapters/profile_media_policy.py`
  + 2. **EDIT** `src/voice/adapters/profile_media_policy.py`
  + 3. **CREATE** `src/voice/adapters/activity_inputs.py`
  + 1. Tiêu đề đúng: `# Báo cáo nghiệm thu PW-E3: ImageSafetyPolicy, NormalizeSpec và ActivityInputPort E`.
  + 2. `## 1. Mục tiêu và phạm vi`: bốn tệp owned paths và ba yêu cầu nghiệm thu.
  + 3. `## 2. Tệp đã đổi`: một dòng cho mỗi tệp trong 4 owned paths.
  + 1. Commit local đúng một commit với message: `feat(voice): media policy from production profile and ActivityInputPort E with image safety chain (PW-E3)` (không push, không merge).
  + 2. Gửi `worker_done` subject `IMPLEMENTED`, kèm SHA commit 40 ký tự, danh sách tệp đã sửa và stdout/stderr, exit code của từng lệnh kiểm.
- **Phạm vi:** Bốn tệp thuộc owned paths:
  + `src/voice/adapters/profile_media_policy.py`
  + `src/voice/adapters/activity_inputs.py`
  + `tests/integration/prod_wiring/test_pw_e3_media_inputs.py`
  + `docs/delivery-evidence/pw-e3/report.md`

## 2. Tệp đã đổi
- `src/voice/adapters/profile_media_policy.py`: Tạo mới adapter dựng các chính sách an toàn ảnh, biến đổi, chuẩn hóa và âm thanh từ tham số profile production (không os.environ, không fake, ném ProfileParameterMissing BLOCKED khi thiếu khoá).
- `src/voice/adapters/activity_inputs.py`: Tạo mới ProductionActivityInputs và handle_voice_activity thực thi cổng ActivityInputPort E, phân giải đầu vào cho 7 activity và điều phối chuỗi an toàn ảnh DQ-11.
- `tests/integration/prod_wiring/test_pw_e3_media_inputs.py`: Tạo mới bộ kiểm thử tích hợp trên PostgreSQL 18.6 thật và FFmpeg gyan.dev đã ghim (coveredIds: PW-E3-01, CT-MED-001, CT-MED-007).
- `docs/delivery-evidence/pw-e3/report.md`: Tạo mới báo cáo nghiệm thu kỹ thuật bằng chứng cho gói PW-E3.

## 3. Quyết định mặc định theo D8
- (a) `ImageSafetyPolicy.confidence_threshold` = `image_safety.thresholds.uncertain_range.max_exclusive`
- (b) `require_transform_before_use=True` là bất biến DQ-11, không phải ngưỡng số
- (c) hành động `reject` là hành động duy nhất được hỗ trợ cho `blur_without_region_action`, `uncertain_range.action`, `detector_failure_action`, giá trị khác thì BLOCKED
- (d) `NormalizeSpec` chỉ có bước `resize` theo `render.profile` (width, height), không crop/pad vì adapter FFmpeg hiện chưa có scale giữ tỷ lệ, tỷ lệ khung do F xử lý khi dựng
- (e) `tool_version` đọc từ `runtime.lock.json` `pins.ffmpeg.archive_name`
- (f) item của activity là ref đầu tiên theo `ref_type` trong `input_refs`
- (g) output_ref phụ `source_ref_id`, `produced_by`, `operation_key`, `assessment_ref`, `regions` mang dữ liệu nối giữa Assess, Transform, Normalize
- (h) ảnh bị loại được thay một-một bằng media seed của selection theo thứ tự, hết seed thì activity thành công không đầu ra, kèm cảnh báo `image_excluded:<lý do>`.

## 4. Mục mở
- OI-PW-E3-01 `FAN_OUT_FROM_OUTPUT` (activities.py, chủ PW-CAT1) chưa có `TransformSensitiveImage`, nên flow chỉ chạy nó một lần với mọi item `sensitive_image` trong input_refs, port lấy item đầu; Control cần lập gói sửa chủ để fan-out theo `sensitive_image`
- OI-PW-E3-02 `LUMA_RADIUS=40`, `LUMA_POWER=3` còn cứng trong `real_ffmpeg_media_tool.py` (ngoài owned paths), chưa nối `image_safety.boxblur`
- OI-PW-E3-03 `reassess` của `RealFfmpegMediaTool` phải được PW-W2 nối, nếu không ảnh đã che luôn ra DETECTION_FAILED và bị loại
- OI-PW-E3-04 regions không bền nếu lệnh Assess bị replay sau khi khởi động lại giữa commit và trả kết quả, hậu quả: ảnh bị loại và thay seed (fail-closed)
- OI-PW-E3-05 nguồn production của `MediaArtifactPort`, `PlanAudioPort`, `SelectionFallbackPort`, `verify_output` thuộc PW-W2 và các gói liên quan.

## 5. Bảng bằng chứng
| Bước | Lệnh | Exit code | Kết quả thực tế | Ghi chú |
| --- | --- | --- | --- | --- |
| Bước 18 | `python -m pytest tests/integration/prod_wiring/test_pw_e3_media_inputs.py -q -p no:cacheprovider` | 1 | 7 failed in 2.07s | RED đúng oracle với NotImplementedError('PW-E3 skeleton'); các test đỏ: test_pw_e3_policy_and_spec_are_built_from_the_production_profile, test_pw_e3_missing_profile_parameter_is_blocked, test_pw_e3_only_a_safe_image_is_usable_and_nothing_uncertain_becomes_safe, test_pw_e3_voice_duration_policy_comes_from_the_profile_and_checks_the_measured_wav, test_pw_e3_voice_probe_and_assess_inputs_come_from_the_ports, test_pw_e3_transform_normalize_and_audio_bed_inputs_come_from_the_ports, test_pw_e3_safety_chain_excludes_unsafe_images_and_blurs_with_the_pinned_ffmpeg |
| Bước 27 | `python -m pytest tests/integration/prod_wiring/test_pw_e3_media_inputs.py -q -p no:cacheprovider` | 0 | 7 passed in 2.63s | GREEN: Toàn bộ 7 bài test tích hợp PW-E3 đạt 100% |
| Bước 28 | `python -m pytest tests/integration/prod_wiring/test_pw_e3_media_inputs.py tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` | 0 | 23 passed, 89 subtests passed in 2.75s | GREEN: Đạt cả test tích hợp media inputs và layout cấu trúc gói voice |
| Bước 29 | `git diff --check` | 0 | Đạt (PASS) | Không có cảnh báo khoảng trắng thừa (trailing whitespace) |
| Bước 30 | `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8').lower() for p in ['src/voice/adapters/profile_media_policy.py', 'src/voice/adapters/activity_inputs.py']); assert 'fake' not in t and 'os.environ' not in t and 'from src.' not in t, 'PW-E3'"` | 0 | Đạt (PASS) | Kiểm tra tĩnh không chứa fake, os.environ và from src. trong hai tệp nguồn |
| Bước 31 | `python -c "import ast, pathlib; d = ast.get_docstring(ast.parse(pathlib.Path('tests/integration/prod_wiring/test_pw_e3_media_inputs.py').read_text(encoding='utf-8'))); assert any(l.startswith('coveredIds:') and all(c in l for c in ['PW-E3-01', 'CT-MED-001', 'CT-MED-007']) for l in d.splitlines()), 'coveredIds'"` | 0 | Đạt (PASS) | Kiểm tra docstring tệp test chứa đủ coveredIds: PW-E3-01, CT-MED-001, CT-MED-007 |
| Bước 33 | `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-e3/report.md').read_text(encoding='utf-8'); assert 'Báo cáo nghiệm thu PW-E3' in t and 'OI-PW-E3-01' in t and 'coveredIds' in t, 'report'"` | 0 | Đạt (PASS) | Kiểm tra tệp report.md giữ nguyên tiếng Việt có dấu và các đề mục bắt buộc |
| Bước 34 | `git diff --check` | 0 | Đạt (PASS) | Kiểm tra khoảng trắng thừa sau khi tạo report.md, sẵn sàng commit |

## 6. Ánh xạ coveredIds
| Covered ID | Mô tả nghiệm thu | Các test tương ứng trong test_pw_e3_media_inputs.py |
| --- | --- | --- |
| PW-E3-01 | Dựng ImageSafetyPolicy, NormalizeSpec từ profile production (không os.environ, thiếu khoá thì BLOCKED), phân giải đầu vào có kiểu cho 7 activity E và chuỗi an toàn ảnh đầu-cuối qua handle_voice_activity | 	est_pw_e3_policy_and_spec_are_built_from_the_production_profile, 	est_pw_e3_missing_profile_parameter_is_blocked, 	est_pw_e3_only_a_safe_image_is_usable_and_nothing_uncertain_becomes_safe, 	est_pw_e3_voice_duration_policy_comes_from_the_profile_and_checks_the_measured_wav, 	est_pw_e3_voice_probe_and_assess_inputs_come_from_the_ports, 	est_pw_e3_transform_normalize_and_audio_bed_inputs_come_from_the_ports, 	est_pw_e3_safety_chain_excludes_unsafe_images_and_blurs_with_the_pinned_ffmpeg |
| CT-MED-001 | Chuỗi an toàn ảnh loại trừ ảnh không an toàn, che mờ ảnh nhạy cảm bằng FFmpeg boxblur đã ghim; chỉ ảnh an toàn mới vào NormalizeMedia, ảnh bất định không bao giờ thành an toàn | 	est_pw_e3_safety_chain_excludes_unsafe_images_and_blurs_with_the_pinned_ffmpeg, 	est_pw_e3_only_a_safe_image_is_usable_and_nothing_uncertain_becomes_safe |
| CT-MED-007 | Ngưỡng thời lượng giọng nói lấy từ profile production và xác thực thời lượng file WAV đo được | 	est_pw_e3_voice_duration_policy_comes_from_the_profile_and_checks_the_measured_wav |
