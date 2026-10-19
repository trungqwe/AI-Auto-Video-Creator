# Báo cáo bằng chứng E-06

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 6945c76b1b309084663e2e0a6b2b668bebad88fc
- Nguồn quyền: IMPL-PLAN-E Auditor PASS, slice E-06 trong docs/implementation/e/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e06_image_transform.py -q -p no:cacheprovider
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 74 failed, 1 passed in 1.24s
- Chi tiết các test FAILED kèm thông điệp ngắn:
  - FAILED test_weapon_request_carries_category_policy_revision_and_policy_action: AssertionError: assert False (where False = isinstance(None, TransformResult))
  - FAILED test_actions_come_from_policy_not_from_constants: IndexError: list index out of range
  - FAILED test_category_without_action_is_input_not_ready[policy_actions0-categories0-weapon]: Failed: DID NOT RAISE ImageSafetyError
  - FAILED test_category_without_action_is_input_not_ready[policy_actions1-categories1-weapon]: Failed: DID NOT RAISE ImageSafetyError
  - FAILED test_category_without_action_is_input_not_ready[policy_actions2-categories2-child]: Failed: DID NOT RAISE ImageSafetyError
  - FAILED test_missing_policy_or_port_is_input_not_ready: Failed: DID NOT RAISE ImageSafetyError
  - FAILED test_success_result_references_original_and_processed: AttributeError: 'NoneType' object has no attribute 'status'
  - FAILED test_non_image_is_not_applicable_and_port_is_not_called[clip]: AssertionError: assert None == SafetyNotApplicable(media_kind='clip', ...)
  - FAILED test_non_image_is_not_applicable_and_port_is_not_called[audio]: AssertionError: assert None == SafetyNotApplicable(media_kind='audio', ...)
  - FAILED test_non_image_is_not_applicable_and_port_is_not_called[video]: AssertionError: assert None == SafetyNotApplicable(media_kind='video', ...)
  - FAILED test_non_image_is_not_applicable_and_port_is_not_called[]: AssertionError: assert None == SafetyNotApplicable(media_kind='', ...)
  - FAILED test_media_kind_must_be_text[None]: Failed: DID NOT RAISE ImageSafetyError
  - FAILED test_media_kind_must_be_text[3]: Failed: DID NOT RAISE ImageSafetyError
  - FAILED test_media_kind_must_be_text[image]: Failed: DID NOT RAISE ImageSafetyError
  - FAILED test_user_visual_hook_is_skipped_but_source_thumbnail_still_runs: AssertionError: assert None == TransformSkipped(reason='hook_already_blurred')
  - FAILED test_user_visual_hook_flag_must_be_bool[None]: Failed: DID NOT RAISE ImageSafetyError
  - FAILED test_user_visual_hook_flag_must_be_bool[yes]: Failed: DID NOT RAISE ImageSafetyError
  - FAILED test_user_visual_hook_flag_must_be_bool[1]: Failed: DID NOT RAISE ImageSafetyError
  - FAILED test_assessment_must_require_transform: Failed: DID NOT RAISE ImageSafetyError
  - FAILED test_transform_raising_is_failure_and_does_not_leak_text: AssertionError: assert False (where False = isinstance(None, TransformResult))
  - FAILED test_bad_transform_outputs_are_failure_never_success[still_required]: AssertionError: assert False (where False = isinstance(None, TransformResult))
  - FAILED test_bad_transform_outputs_are_failure_never_success[unreadable]: AssertionError: assert False (where False = isinstance(None, TransformResult))
  - FAILED test_bad_transform_outputs_are_failure_never_success[post_transform_failed]: AssertionError: assert False (where False = isinstance(None, TransformResult))
  - FAILED test_bad_transform_outputs_are_failure_never_success[bad_result]: AssertionError: assert False (where False = isinstance(None, TransformResult))
  - FAILED test_bad_transform_outputs_are_failure_never_success[replaces_original]: AssertionError: assert False (where False = isinstance(None, TransformResult))
  - FAILED test_bad_transform_outputs_are_failure_never_success[same_ref_new_hash]: AssertionError: assert False (where False = isinstance(None, TransformResult))
  - FAILED test_inconclusive_post_assessment_is_warning_not_success: AttributeError: 'NoneType' object has no attribute 'status'
  - FAILED test_only_safe_post_assessment_yields_success: AttributeError: 'NoneType' object has no attribute 'status'
  - FAILED test_original_ref_is_never_replaced: IndexError: list index out of range
  - FAILED test_models_are_frozen_and_normalized: IndexError: list index out of range
  - FAILED test_output_profile_is_copied_and_read_only: Failed: DID NOT RAISE TypeError
  - FAILED test_policy_rejects_invalid_values[kwargs0..7]: Failed: DID NOT RAISE ImageSafetyError (8 ca kiểm thử)
  - FAILED test_region_rejects_invalid_values[kwargs0..6]: Failed: DID NOT RAISE ImageSafetyError (7 ca kiểm thử)
  - FAILED test_request_constructor_rejects_invalid_values[override0..10]: Failed: DID NOT RAISE ImageSafetyError (11 ca kiểm thử)
  - FAILED test_result_constructor_enforces_status_invariants[override0..14]: Failed: DID NOT RAISE ImageSafetyError (15 ca kiểm thử)
  - FAILED test_result_constructor_accepts_valid_success_warning_failure: AssertionError: assert 'success' is <TransformStatus.SUCCESS: 'success'>
  - FAILED test_transform_port_is_runtime_checkable_protocol: Failed: DID NOT RAISE ImageSafetyError
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection nào (RED đúng oracle trên khung tối thiểu).

## Thay đổi

- 3 tệp owned:
  - src/voice/domain/image_transform.py
  - tests/unit/voice/test_e06_image_transform.py
  - docs/delivery-evidence/e-06/report.md
- Danh mục API:
  - TransformStatus: StrEnum xác định 3 trạng thái kết quả chuyển đổi (SUCCESS, WARNING, FAILURE).
  - TransformRegion: frozen dataclass mô tả vùng nhạy cảm cần xử lý (category, confidence, mask_ref).
  - TransformPolicy: frozen dataclass chứa revision và ánh xạ hành động theo category (revision, actions).
  - TransformRequest: frozen dataclass đại diện yêu cầu xử lý ảnh gửi tới port (source_ref, regions, categories, actions, transform_policy_revision, output_profile).
  - TransformOutput: frozen dataclass chứa kết quả thô trả về từ port (processed_ref, evidence_ref, processor_version, post_assessment).
  - TransformResult: frozen dataclass ràng buộc bất biến trạng thái chuyển đổi thành phẩm (status, original_ref, processed_ref, evidence_ref, processor_version, post_assessment, warnings).
  - TransformSkipped: frozen dataclass đại diện trường hợp bỏ qua xử lý do cờ hook (reason).
  - TransformPort: runtime_checkable Protocol định nghĩa giao diện cổng chuyển đổi nhạy cảm (transform).
  - transform_sensitive_image: hàm nghiệp vụ chuyển đổi ảnh nhạy cảm theo chính sách và đánh giá hậu kỳ (CT-PROC-006).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/voice/test_e06_image_transform.py -q -p no:cacheprovider | 0 | 75 passed in 0.09s |
| 2 | python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider | 0 | 9 passed, 49 subtests passed in 0.07s |
| 3 | git diff --check | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Phản ví dụ đã loại trừ

1. **Transform lỗi vẫn ghi success:** Loại trừ bởi `test_transform_raising_is_failure_and_does_not_leak_text`, `test_bad_transform_outputs_are_failure_never_success`, `test_only_safe_post_assessment_yields_success` và `test_result_constructor_enforces_status_invariants`. Khi port ném ngoại lệ, trả dữ liệu lỗi, hoặc post_assessment không đạt SAFE thì kết quả luôn là FAILURE (hoặc WARNING nếu UNCERTAIN/DETECTION_FAILED), không bao giờ ghi SUCCESS.
2. **Hằng blur cho vũ khí:** Loại trừ bởi `test_actions_come_from_policy_not_from_constants`, `test_category_without_action_is_input_not_ready` và `test_module_has_no_action_constant_no_io_cleanup_or_foreign_imports`. Hành động hoàn toàn phân giải động từ TransformPolicy được truyền vào; thiếu hành động ném INPUT_NOT_READY và không chứa bất kỳ hằng kiểu che ảnh nào trong mã nguồn domain.
3. **Clip bị transform:** Loại trừ bởi `test_non_image_is_not_applicable_and_port_is_not_called`. Khi media_kind khác 'image' (ví dụ clip, audio, video, rỗng), hàm lập tức trả về SafetyNotApplicable và port tuyệt đối không được gọi.
4. **Ảnh gốc bị thay bằng bản đã xử lý:** Loại trừ bởi `test_original_ref_is_never_replaced` và các ca kiểm thử `replaces_original` / `same_ref_new_hash`. original_ref luôn được bảo toàn nguyên vẹn tham chiếu gốc; nếu bản xử lý có ref trùng ảnh gốc thì kết quả bị đánh dấu thất bại `processed_replaces_original`.

## Quyết định mặc định (D8)

1. E-06 tự định nghĩa TransformPolicy (revision + ánh xạ category→tên hành động) vì ImageSafetyPolicy của E-05 không có hành động và không thuộc owned paths; tên hành động là chuỗi mờ do policy cung cấp, giá trị trong test chỉ là fixture.
2. assessment phải là TRANSFORM_REQUIRED, ngược lại ném constraint_violation.
3. post_assessment SAFE → success, UNCERTAIN/DETECTION_FAILED → warning (vẫn kèm processed_ref), TRANSFORM_REQUIRED/UNREADABLE/TRANSFORM_FAILED → failure với outcome TRANSFORM_FAILED và original_usable True theo bảng CT-PROC-005.
4. failure không trả processed_ref, evidence_ref, processor_version (đều là None).
5. ref đã xử lý trùng ref ảnh gốc → failure processed_replaces_original.
6. thông điệp ngoại lệ của port không được chép vào kết quả để tránh lộ secret.
7. user_visual_hook=True bỏ qua với lý do hook_already_blurred, thumbnail từ nguồn (cờ False) vẫn chạy.
8. mọi lỗi đầu vào dùng ImageSafetyError của E-05.

## Danh sách chờ user (pendingUserCheckpoint)

- ROADMAP-OPEN-006 (policy image safety và hành động transform theo category)
- CP7-E-03 (detector và transform thật)
- USER-CKPT-D9-D10
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, không chạy tests/m1 và tests/m2.
- Không sửa pyproject.toml, uv.lock, migration, composition root, image_safety.py.
- Không gọi dịch vụ thật; không đọc tệp ảnh thật.
- Không push hay merge vào main/backup.