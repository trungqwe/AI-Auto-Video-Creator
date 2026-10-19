# Báo cáo bằng chứng E-05

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: e336d92b9146b73d42da5f0346a55eef6c8d4386
- Nguồn quyền: IMPL-PLAN-E Auditor PASS, slice E-05 trong docs/implementation/e/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e05_image_safety.py -q -p no:cacheprovider
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 27 failed, 23 passed in 0.33s
- Chi tiết các test FAILED kèm thông điệp:
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_sensitive_image_set[safe] - AssertionError: assert None == 'policy-test-1'
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_sensitive_image_set[child] - AssertionError: child, assert (<SafetyOutcome.SAFE: 'SAFE'>, True) == (<SafetyOutcome.TRANSFORM_REQUIRED: 'TRANSFORM_REQUIRED'>, False)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_sensitive_image_set[gore] - AssertionError: gore, assert (<SafetyOutcome.SAFE: 'SAFE'>, True) == (<SafetyOutcome.TRANSFORM_REQUIRED: 'TRANSFORM_REQUIRED'>, False)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_sensitive_image_set[weapon] - AssertionError: weapon, assert (<SafetyOutcome.SAFE: 'SAFE'>, True) == (<SafetyOutcome.TRANSFORM_REQUIRED: 'TRANSFORM_REQUIRED'>, False)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_sensitive_image_set[uncertain_clean] - AssertionError: uncertain_clean, assert (<SafetyOutcome.SAFE: 'SAFE'>, True) == (<SafetyOutcome.UNCERTAIN: 'UNCERTAIN'>, True)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_sensitive_image_set[uncertain_sensitive] - AssertionError: uncertain_sensitive, assert (<SafetyOutcome.SAFE: 'SAFE'>, True) == (<SafetyOutcome.UNCERTAIN: 'UNCERTAIN'>, True)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_sensitive_image_set[uncertain_no_confidence] - AssertionError: uncertain_no_confidence, assert (<SafetyOutcome.SAFE: 'SAFE'>, True) == (<SafetyOutcome.UNCERTAIN: 'UNCERTAIN'>, True)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_sensitive_image_set[detector_failed] - AssertionError: detector_failed, assert (<SafetyOutcome.SAFE: 'SAFE'>, True) == (<SafetyOutcome.DETECTION_FAILED: 'DETECTION_FAILED'>, True)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_sensitive_image_set[detector_raises] - AssertionError: detector_raises, assert (<SafetyOutcome.SAFE: 'SAFE'>, True) == (<SafetyOutcome.DETECTION_FAILED: 'DETECTION_FAILED'>, True)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_sensitive_image_set[detector_bad_result] - AssertionError: detector_bad_result, assert (<SafetyOutcome.SAFE: 'SAFE'>, True) == (<SafetyOutcome.DETECTION_FAILED: 'DETECTION_FAILED'>, True)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_sensitive_image_set[detection_missing] - AssertionError: detection_missing, assert (<SafetyOutcome.SAFE: 'SAFE'>, True) == (<SafetyOutcome.DETECTION_FAILED: 'DETECTION_FAILED'>, True)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_sensitive_image_set[unreadable] - AssertionError: unreadable, assert (<SafetyOutcome.SAFE: 'SAFE'>, True) == (<SafetyOutcome.UNREADABLE: 'UNREADABLE'>, False)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_only_clean_result_is_safe_and_transform_failed_is_never_produced - AssertionError: assert ['safe', 'child', ...] == ['safe'] (Left contains 11 more items)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_detector_exception_text_is_not_leaked - AssertionError: assert 'skeleton_placeholder' == 'detector_raised'
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_confidence_boundary_follows_policy_threshold - AssertionError: assert <SafetyOutcome.SAFE: 'SAFE'> is <SafetyOutcome.UNCERTAIN: 'UNCERTAIN'>
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_transform_required_original_usable_follows_policy_flag - AssertionError: assert (<SafetyOutcome.SAFE: 'SAFE'>, True) == (<SafetyOutcome.TRANSFORM_REQUIRED: 'TRANSFORM_REQUIRED'>, True)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_non_image_is_not_applicable_and_detector_is_not_called[clip] - AssertionError: assert ImageSafetyAssessment(...) == SafetyNotApplicable(media_kind='clip', ...)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_non_image_is_not_applicable_and_detector_is_not_called[audio] - AssertionError: assert ImageSafetyAssessment(...) == SafetyNotApplicable(media_kind='audio', ...)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_non_image_is_not_applicable_and_detector_is_not_called[video] - AssertionError: assert ImageSafetyAssessment(...) == SafetyNotApplicable(media_kind='video', ...)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_non_image_is_not_applicable_and_detector_is_not_called[] - AssertionError: assert ImageSafetyAssessment(...) == SafetyNotApplicable(media_kind='', ...)
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_media_kind_must_be_text[None] - Failed: DID NOT RAISE ImageSafetyError
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_media_kind_must_be_text[3] - Failed: DID NOT RAISE ImageSafetyError
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_media_kind_must_be_text[image] - Failed: DID NOT RAISE ImageSafetyError
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_missing_policy_is_input_not_ready_and_detector_is_not_called - Failed: DID NOT RAISE ImageSafetyError
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_policy_of_wrong_type_is_rejected - Failed: DID NOT RAISE ImageSafetyError
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_callable_detector_result_is_used_once - AssertionError: assert 0 == 1
  - FAILED tests/unit/voice/test_e05_image_safety.py::test_models_are_frozen_and_normalized_to_tuples - AssertionError: assert () == ('child', 'weapon')
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection nào (RED là sai oracle trên khung tối thiểu).

## Thay đổi

- 3 tệp owned:
  - src/voice/domain/image_safety.py
  - tests/unit/voice/test_e05_image_safety.py
  - docs/delivery-evidence/e-05/report.md
- Danh mục API:
  - SafetyOutcome: StrEnum với 6 trạng thái CT-PROC-005 (SAFE, TRANSFORM_REQUIRED, UNCERTAIN, DETECTION_FAILED, TRANSFORM_FAILED, UNREADABLE)
  - DetectionStatus: StrEnum (completed, failed, unreadable)
  - ImageDetection: frozen dataclass (status, categories, confidence)
  - ImageSafetyPolicy: frozen dataclass không có giá trị mặc định (revision, confidence_threshold, transform_categories, require_transform_before_use)
  - ImageSafetyAssessment: frozen dataclass ràng buộc original_usable theo bảng CT-PROC-005 (outcome, original_usable, reason, warnings, categories, confidence, policy_revision)
  - SafetyNotApplicable: frozen dataclass (media_kind, reason)
  - ImageSafetyError: ngoại lệ kế thừa ValueError (code, reason)
  - original_usable_for: hàm xác định original_usable từ outcome và require_transform_before_use
  - assess_image_safety: hàm nghiệp vụ đánh giá an toàn ảnh (CT-PROC-005)

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/voice/test_e05_image_safety.py -q -p no:cacheprovider | 0 | 50 passed in 0.06s |
| 2 | python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider | 0 | 9 passed, 49 subtests passed in 0.07s |
| 3 | git diff --check | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Phản ví dụ đã loại trừ

1. **Uncertain hoặc detector lỗi bị ghi SAFE:** Loại trừ bởi `test_sensitive_image_set` và `test_only_clean_result_is_safe_and_transform_failed_is_never_produced`; khi confidence dưới ngưỡng policy hoặc detector gặp lỗi/ném ngoại lệ/trả dữ liệu sai, outcome luôn là UNCERTAIN hoặc DETECTION_FAILED, chỉ duy nhất ca sạch mới nhận SAFE.
2. **Clip được đánh giá safety:** Loại trừ bởi `test_non_image_is_not_applicable_and_detector_is_not_called`; `assess_image_safety` phát hiện media_kind khác 'image' sẽ trả về SafetyNotApplicable ngay lập tức mà không gọi detector và không kiểm tra policy.
3. **UNREADABLE vẫn dùng được:** Loại trừ bởi `test_sensitive_image_set[unreadable]` và `test_assessment_constructor_enforces_table_and_warnings`; trạng thái UNREADABLE bắt buộc có original_usable = False, vi phạm sẽ ném ImageSafetyError constraint_violation.
4. **Policy thiếu mà vẫn ra kết quả:** Loại trừ bởi `test_missing_policy_is_input_not_ready_and_detector_is_not_called`; khi policy là None, hàm ném ImageSafetyError mã INPUT_NOT_READY reason missing_policy fail-closed và không gọi detector.

## Quyết định mặc định (D8)

1. Detection là ImageDetection hoặc callable không đối số; E-05 không đọc tệp, tệp không đọc được do detector báo qua status unreadable, detector thật thuộc CP7-E-03.
2. media_kind là chuỗi khác 'image' trả SafetyNotApplicable, kiểm trước policy và không gọi detector, không phải chuỗi thì raise wrong_type.
3. Policy không có mặc định, thiếu thì ImageSafetyError code INPUT_NOT_READY reason missing_policy, giá trị policy trong test là GIẢ ĐỊNH.
4. Confidence thiếu hoặc dưới ngưỡng thì UNCERTAIN và ưu tiên hơn category.
5. TRANSFORM_REQUIRED có original_usable bằng not require_transform_before_use.
6. assess_image_safety không tạo TRANSFORM_FAILED (thuộc E-06) nhưng enum đủ 6 trạng thái.
7. Lỗi detector ghi reason cố định, không chép thông điệp ngoại lệ để không lộ secret.
8. Category được phát hiện nhưng không nằm trong policy.transform_categories không làm đổi kết quả SAFE và assessment chỉ lưu category khớp policy.

## Danh sách chờ user (pendingUserCheckpoint)

- ROADMAP-OPEN-006 (ngưỡng, category và cờ require_transform_before_use của policy image safety)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5) gồm CP7-E-03
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, không chạy tests/m1 và tests/m2.
- Không sửa pyproject.toml hay uv.lock.
- Không gọi dịch vụ thật hay detector thật.
- Không đọc tệp ảnh thật.
- Không sửa migration hay composition root.
