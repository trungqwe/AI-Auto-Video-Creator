# ADAPT-E-MEDIA-FIX4: Luật an toàn ảnh theo RG-13 (giữ tỉ lệ, logo_watermark, che mờ tối thiểu, ảnh chưa chắc dùng nguyên gốc)

Mã gói: `ADAPT-E-MEDIA-FIX4` (milestone CP7). Ngày thực hiện: 02/11/2026.

## 1. Phạm vi

Đã sửa hoặc tạo đúng 16 owned paths, không có tệp nào ngoài danh sách:

1. `src/voice/adapters/real_llm_image_safety.py`
2. `src/voice/adapters/real_ffmpeg_media_tool.py`
3. `src/voice/adapters/profile_media_policy.py`
4. `src/voice/adapters/activity_inputs.py`
5. `src/voice/domain/image_transform.py`
6. `src/controlplane/api/wiring/voice.py`
7. `tools/launcher/prod/profile.json`
8. `tests/integration/adapt/e_media/test_adapt_e_media_fix4_rg13.py` (tạo mới)
9. `tests/integration/adapt/e_media/test_adapt_e_media_tools.py`
10. `tests/integration/adapt/e_media/test_adapt_e_media_safety_scores.py`
11. `tests/unit/voice/test_e06_image_transform.py`
12. `tests/integration/prod_wiring/test_pw_e3_media_inputs.py`
13. `tests/integration/prod_wiring/test_pw_w2_fix8_render_image_safety.py`
14. `tests/integration/prod_wiring/pw_e2e_support.py`
15. `tests/real/test_cp7_image_safety_real.py` (chỉ sửa ghim, không chạy)
16. `docs/delivery-evidence/adapt-e-media-fix4/report.md` (tệp này)

`normalize_source` (của PW-D3-FIX3) không đổi, kể cả docstring. Không thêm khoá profile, không thêm hay đổi thư viện.

## 2. Nhóm lỗi OI-CP7-11-Q1

GIẢ ĐỊNH: tài liệu hiện hành không định nghĩa mã `OI-CP7-11-Q1`, nên mã này được dùng làm nhãn cho hai việc:

- Nhóm lỗi của gói này: ảnh ngang bị kéo giãn khi chuẩn hoá; che mờ đổi điểm ảnh ngoài vùng che; logo chưa là nhóm nhạy cảm (detector cũ trả DETECTION_FAILED); bản che bị loại; ảnh chưa chắc (UNCERTAIN) bị loại; vùng null không được hỏi lại.
- Câu hỏi chờ user quyết: FR-SEN-006 cho phép dùng cả ảnh lỗi nhận diện (DETECTION_FAILED lần đầu) và ảnh lỗi xử lý (TRANSFORM_FAILED), nhưng kế hoạch đã duyệt giữ loại hai trường hợp này vì an toàn hơn. Gói này giữ loại. Trạng thái: **chờ user quyết**, chưa được duyệt.

## 3. Thiết kế và các hàm đã đổi

- `real_ffmpeg_media_tool.py`: thêm `blur_radius(width, height) = min(max(4, s // 6), s // 4)` với `s` là cạnh ngắn (vào `__all__`); bỏ `LUMA_RADIUS`, `LUMA_POWER = 1`, thêm `BLUR_MIN_RADIUS = 4`, `BLUR_REGION_DIVISOR = 6`. `RealFfmpegMediaTool._plan_tail` đổi bước resize thành `scale='min(w,iw)':'min(h,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2` (không kéo giãn, không pad, không phóng to). `RealFfmpegMediaTool.transform` dùng `blur_radius(pw, ph)` cho từng vùng, `overlay=px:py:format=auto` (giữ nguyên điểm ảnh ngoài vùng) và băm thêm `graph` vào payload của `processed_ref`.
- `real_llm_image_safety.py`: `PROMPT_REVISION = 'image-safety-prompt-v3'`; `DEFAULT_CATEGORIES` và `CATEGORY_DEFINITIONS` thêm `logo_watermark`; `build_instructions` (đoạn detections mới: mỗi vùng một mục, vùng của `minor_child` là khuôn mặt); hàm mới `build_region_instructions`; tách `_load_object`, `_mask_ref`; `_parse_vision` và `parse_vision_output` nhận `transform_min` (có nhóm chắc thì chỉ giữ các nhóm chắc); hàm mới `_parse_regions`; `LlmImageSafetyDetector.__init__` nhận `transform_min`, `region_categories`, có `missing_regions`; `LlmImageSafetyDetector.__call__` và `_complete_regions` hỏi lại vùng đúng một lần, còn thiếu vùng thì `regions = ()` và `missing_regions` liệt kê nhóm thiếu.
- `profile_media_policy.py`: thêm `USE_ORIGINAL_ACTION = 'use_original'`; `build_image_safety_rules` đòi `uncertain_range.action == 'use_original'`, hai hành động còn lại vẫn `'reject'`; `image_disposition` trả `(USABLE, 'uncertain')` cho UNCERTAIN.
- `activity_inputs.py`: `ProductionActivityInputs._assess` truyền `transform_min=self._rules.uncertain_max_exclusive` và `region_categories=tuple(sorted(self._rules.blur_categories))`; `ProductionActivityInputs._verdict` trả `blurred` (SUCCESS), `blurred_with_warning` (WARNING) hoặc `transform_failed` (FAILURE hay không có bản che); bỏ `not_blurred_safe`.
- `image_transform.py`: `_POST_OUTCOMES[WARNING]` thêm `TRANSFORM_REQUIRED`; `_POST_FAILURE_REASON` bỏ `TRANSFORM_REQUIRED` (không còn `post_assessment_still_transform_required`).
- `wiring/voice.py`: closure `reassess` trong `voice_activity_deps` chỉ trả kết quả khi `res.outcome is not SafetyOutcome.DETECTION_FAILED`, còn lại rơi xuống bản `post_transform_not_reassessed`.
- `profile.json` (chỉ đổi giá trị): `meta.revision` 6; `categories` thêm `logo_watermark`; `reject_min_confidence` chỉ `nudity_sexual: 0.5`; `blur_min_confidence` gồm `minor_child`, `graphic_violence`, `weapon`, `hate_symbol`, `logo_watermark` đều 0.5; `uncertain_range.action = use_original`; `boxblur {luma_radius: 4, luma_power: 1}`; basis của ba mục là `DECIDED`.

## 4. Luật sau bản sửa

- Ảnh chưa chắc (UNCERTAIN) luôn dùng nguyên gốc (`uncertain`); không bao giờ coi là SAFE.
- Bản che luôn dùng được: `blurred` khi đánh giá lại sau che là SAFE; `blurred_with_warning` khi đánh giá lại không SAFE (chỉ ghi cảnh báo, không che lần hai, đánh giá lại gọi tuyến đúng một lần mỗi bản). Lỗi che (`TRANSFORM_FAILED`) thì loại với lý do `transform_failed`.
- `nudity_sexual` và DETECTION_FAILED lần đầu vẫn bị loại.
- Vùng null được hỏi lại đúng một lần; còn thiếu vùng thì không che một phần và ảnh bị loại với lý do `blur_without_region`.
- Logo đã xác nhận không còn bị nhóm chưa chắc đứng cạnh kéo thành UNCERTAIN (`transform_min`).

## 5. Bán kính che mờ cho vùng mẫu

- Vùng 200x100: cạnh ngắn 100, bán kính `min(max(4, 100 // 6), 100 // 4)` = `min(16, 25)` = **16**, `luma_power` 1.
- Vùng 32x32: cạnh ngắn 32, bán kính `min(max(4, 5), 8)` = **5**.

## 6. Lệnh đã chạy

Interpreter khoá của lane; `PYTEST_DEBUG_TEMPROOT` đặt theo quy định của lượt này.

| Bước | Lệnh | Exit code | Dòng tổng kết nguyên văn của pytest |
| --- | --- | --- | --- |
| 14 (RED, trên mã chưa sửa) | `python -m pytest tests/integration/adapt/e_media tests/unit/voice/test_e06_image_transform.py tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` | 1 | `22 failed, 191 passed, 89 subtests passed in 6.48s` |
| 25 | cùng lệnh như bước 14, sau bản sửa | 0 | `213 passed, 89 subtests passed in 16.03s` |
| 26 | `python -m pytest tests/integration/voice tests/integration/prod_ports/test_pp_7_vision_route.py tests/unit/voice/test_e05_image_safety.py tests/unit/voice/test_e07_normalize_media.py tests/unit/voice/test_e15_ports_memory.py tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider` | 0 | `434 passed in 38.71s` |
| 27 | `python -m pytest tests/integration/prod_wiring/test_pw_e3_media_inputs.py tests/integration/prod_wiring/test_pw_w2_fix8_render_image_safety.py -q -p no:cacheprovider` | 0 | `22 passed in 20.13s` |
| 28 | `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py tests/integration/prod_wiring/test_pw_w2_launcher_def.py -q -p no:cacheprovider` | 0 | `152 passed in 24.07s` |
| 29 | `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider` | 0 | `11 passed, 1 warning in 157.39s (0:02:37)` |
| 30 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7637 passed, 1 warning, 2561 subtests passed in 37.00s` |
| 31 đến 35 | probe `python -c` chỉ đọc cho ffmpeg tool, detector, policy/verdict/judge/reassess, profile.json, test mới và ghim | 0 | không áp dụng |
| 36 đến 38 | probe báo cáo (mã gói, `OI-CP7-11-Q1`) và probe chữ có dấu | 0 | không áp dụng |
| 39 | `git diff --check` | 0 | không áp dụng |

Ngoài ra toàn bộ 24 probe `python -c` trong danh sách lệnh kiểm bắt buộc của gói đều exit 0 (chạy bằng một script đọc đúng chuỗi lệnh từ spec). Bước 27 đến 29 chạy với PostgreSQL thử nghiệm và FFmpeg ghim `C:/ffmpeg/bin/ffmpeg.exe` thật, không skip.

## 7. Số ca test mới hỏng trên HEAD trước bản sửa và đạt sau

Trên HEAD 7fa09bf (bước 14, sau khi chỉ thêm và sửa test): **22 ca hỏng**, mọi lỗi là assert, TypeError hoặc AttributeError trong thân test, không có lỗi collect hay import:

- `test_adapt_e_media_fix4_rg13.py` (14 ca): `test_blur_radius_follows_the_shorter_side`, `test_normalize_fits_inside_the_frame_without_stretch_or_pad` (3 tham số), `test_blur_changes_only_the_pixels_inside_the_region`, `test_confirmed_group_is_blurred_and_an_unsure_logo_beside_it_is_ignored`, `test_a_blurred_copy_that_is_still_flagged_stays_usable_with_a_warning`, `test_an_unsure_image_uses_the_original`, `test_a_null_region_is_asked_again_exactly_once`, `test_a_region_that_stays_null_excludes_the_image_after_one_retry`, `test_a_group_still_missing_its_region_blurs_nothing`, `test_nudity_and_a_failed_detector_are_never_used`, `test_a_blur_that_cannot_be_made_is_excluded_as_transform_failed`, `test_reassess_runs_once_and_a_failed_detection_is_a_warning`.
- `test_adapt_e_media_safety_scores.py` (4 ca): `test_prompt_v3_is_verbatim`, `test_transform_min_keeps_only_the_confirmed_groups`, `test_region_instructions_ask_only_for_regions`, `test_detector_asks_for_missing_regions_once_and_blurs_nothing_when_one_is_still_missing`.
- `test_adapt_e_media_tools.py` (2 ca): `test_plan_operations_build_argv`, `test_transform_blur_builds_boxblur_filtergraph`.
- `test_e06_image_transform.py` (2 ca): `test_inconclusive_post_assessment_is_warning_not_success`, `test_only_safe_post_assessment_yields_success`.

Sau bản sửa (bước 25): cả 22 ca đạt, tổng nhóm `213 passed`; riêng `test_adapt_e_media_fix4_rg13.py` có 14 ca, đều đạt.

## 8. Giới hạn

- Nền ảnh trong khung do F-10-FIX6; luật không toàn nền và thay ảnh bị loại do PW-D3-FIX3 (phụ thuộc gói này). Tới khi F-10-FIX6 gộp, render cũ phủ khung và cắt ảnh ngang (không kéo giãn).
- `tests/real/test_cp7_image_safety_real.py` chỉ sửa ghim (boxblur 4 và 1, `blurred_with_warning`, `test_rg06_uncertain_never_safe` nay ghim ảnh UNCERTAIN dùng nguyên gốc), không chạy; lượt RG-06 thật sau gộp sẽ đo lại. Phép đo giảm cạnh 0,89 đến 0,99 trên ảnh JPEG chi tiết của nguyên mẫu Control chưa được Worker đo lại trong gói này.
- Ảnh UNREADABLE sau che vẫn là lỗi.
- OI-CP7-11-Q1 (FR-SEN-006) chờ user quyết; gói giữ loại ảnh lỗi nhận diện lần đầu và ảnh lỗi xử lý.
