# Báo cáo bằng chứng E-17

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: ab7cb613044212edf40e03817b75d6d648823269
- Nguồn quyền: IMPL-PLAN-E Auditor PASS và slice E-17 trong docs/implementation/e/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/integration/voice/test_e17_media_processing_pipeline.py -q -p no:cacheprovider (chạy với khung stub ở bước 1 đến 4 và toàn bộ test ở bước 5 đến 13)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 44 failed, 1 passed in 1.03s
- Chi tiết các test FAILED tiêu biểu kèm thông điệp:
  - FAILED tests/integration/voice/test_e17_media_processing_pipeline.py::test_probe_media_records_report_and_receipt_without_event: NotImplementedError trong MediaPipeline.probe_media
  - FAILED tests/integration/voice/test_e17_media_processing_pipeline.py::test_assess_safe_image_records_assessment_and_event: NotImplementedError trong MediaPipeline.assess_image_safety
  - FAILED tests/integration/voice/test_e17_media_processing_pipeline.py::test_transform_verified_output_is_recorded_with_event: NotImplementedError trong MediaPipeline.transform_sensitive_image
  - FAILED tests/integration/voice/test_e17_media_processing_pipeline.py::test_normalize_image_records_new_rendition_and_event: NotImplementedError trong MediaPipeline.normalize_media
  - FAILED tests/integration/voice/test_e17_media_processing_pipeline.py::test_audio_bed_verified_output_is_recorded_with_event: NotImplementedError trong MediaPipeline.prepare_audio_bed
  - FAILED tests/integration/voice/test_e17_media_processing_pipeline.py::test_image_batch_continues_through_uncertain_failed_and_unreadable_images: NotImplementedError trong MediaPipeline.process_image_batch
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi cú pháp, collection. Duy nhất 1 test test_module_has_no_adapter_process_or_clock_imports đã PASS kiểm tra ranh giới nhập khẩu AST tĩnh. Tất cả 44 test nghiệp vụ thất bại chính xác theo oracle RED do phương thức stub ném NotImplementedError.

## GREEN

- Lệnh thực thi: python -m pytest tests/integration/voice/test_e17_media_processing_pipeline.py -q -p no:cacheprovider (chạy sau khi cài đặt đầy đủ logic ở các bước 15 đến 22)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 45 passed in 0.19s

## Thay đổi

- Ba tệp thuộc owned paths và vai trò từng tệp:
  - src/voice/application/media_pipeline.py: Triển khai lớp MediaPipeline với 5 command xử lý media và audio bed (probe_media, assess_image_safety, transform_sensitive_image, normalize_media, prepare_audio_bed) cùng process_image_batch. Mỗi command thực thi trong đúng một UnitOfWork (UoW) bao gồm bản ghi domain output mới, receipt bền vững (OperationReceipt) và outbox domain event chuẩn. Hỗ trợ phân loại thất bại (failed trước/trong side effect, outcome_unknown sau side effect trước receipt commit), chặn retry trực tiếp sau outcome_unknown bằng RetryNotAllowedError, bảo đảm replay idempotency trả về receipt cũ (replayed=True), và chỉ phát event MediaProcessingCompleted khi có bằng chứng verify hợp lệ từ Phân hệ I (VerifiedOutput).
  - tests/integration/voice/test_e17_media_processing_pipeline.py: Bộ kiểm thử tích hợp toàn diện gồm 45 test cases bao quát: các luồng thành công và lỗi của ProbeMedia (không tin declared extension/mime, cảnh báo unreadable/corrupt, lỗi port), AssessImageSafety (SAFE, UNCERTAIN, DETECTION_FAILED, UNREADABLE, từ chối clip), TransformSensitiveImage (đã verify, UNCERTAIN cảnh báo, lỗi port, thay ref gốc bị từ chối, unverified bị failed không event, hook user đã blur), NormalizeMedia (ảnh và clip, từ chối clip kèm blur, replay không chạy lại tool, tool báo OUTCOME_UNKNOWN chặn retry trực tiếp, crash sau side effect là OUTCOME_UNKNOWN, partial/hash lệch/probe output corrupt không phát event, idempotency), PrepareAudioBed (đã verify, thiếu loudness constraint, loudness lệch chuẩn, thay thế không cho phép, thay ref gốc, unverified, crash/outcome_unknown), process_image_batch (tiếp tục qua ảnh uncertain, lỗi detector, transform failed, unreadable không dừng batch) và kiểm tra tĩnh AST ranh giới import (cấm adapters, subprocess, socket, os, time, datetime, uuid, random).
  - docs/delivery-evidence/e-17/report.md: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.
- Ánh xạ phản ví dụ → test:
  - Ảnh lỗi detector được ghi safe: test_assess_uncertain_and_detector_failures_continue_with_warning và test_image_batch_continues_through_uncertain_failed_and_unreadable_images
  - Clip bị blur: test_assess_clip_is_rejected_without_writes, test_transform_clip_is_rejected_without_writes, test_normalize_clip_with_blur_is_rejected_without_tool_call
  - Retry trực tiếp từ outcome_unknown: test_normalize_outcome_unknown_from_tool_blocks_direct_retry và test_normalize_crash_after_side_effect_before_receipt_is_outcome_unknown
  - Bản gốc bị thay: test_normalize_tool_returning_original_ref_never_replaces_original và test_transform_processed_replacing_original_is_failed
  - Phát event khi output chưa verify: test_normalize_partial_or_hash_mismatch_is_not_ready, test_transform_unverified_output_is_failed_without_event, test_audio_bed_unverified_output_is_failed

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/integration/voice/test_e17_media_processing_pipeline.py -q -p no:cacheprovider | 0 | 45 passed in 0.19s |
| 2 | python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider | 0 | 9 passed, 49 subtests passed in 0.08s |
| 3 | python -m pytest tests/unit/voice -q -p no:cacheprovider | 0 | 929 passed, 49 subtests passed in 0.97s |
| 4 | git diff --check | 0 | PASS (không output, không trailing whitespace) |

## Quyết định mặc định (D8)

1. ProbeMedia chỉ ghi report và receipt, không phát event vì E-15 không có event cho probe và MediaProcessingCompleted cần artifact đã verify;
2. receipt là bản ghi append-only kind receipt (khóa operation_key) và chỉ mục receipt_by_request (khóa request fingerprint), kiểu E-local trong media_pipeline.py, chưa có bảng (CONV-E-01);
3. processing_operation_id bằng operation_key, aggregate_revision 1;
4. bằng chứng verify của I là tham số verified_outputs ánh xạ ref sang VerifiedOutput(content_sha256, size_bytes) (GIẢ ĐỊNH theo binding i-artifact-version); thiếu hoặc lệch hash thì failed và không event;
5. phân loại crash: lỗi trước hoặc trong side effect → failed; tool báo outcome_unknown hoặc commit lỗi sau khi side effect xong → outcome_unknown;
6. cùng operation_key trả lại receipt cũ (mọi disposition); khác key cùng request sau outcome_unknown bị RetryNotAllowedError cho tới khi G đối soát (CONV-E-05);
7. AudioBedPort là port E-local trong media_pipeline.py, binding thật mở ở CONV-E-07;
8. TRANSFORM_FAILED: receipt failed, lưu TransformResult, ảnh gốc dùng được theo domain, không event; hook đã blur chỉ ghi receipt kèm warning;
9. kiểm probe output sau normalize là tùy chọn (khi có ProbePort);
10. không có bản ghi intent trước side effect, nên kill tiến trình giữa chừng chờ persistence thật (CONV-E-01, CONV-E-05) — giới hạn đã biết.

## coveredIds

- TST-E2E-011 (phía E)
- CT-PROC-003, CT-PROC-004, CT-PROC-005, CT-PROC-006, CT-PROC-007
- CT-AUD-001

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5), FFmpeg và ffprobe thật ở CP7-E-04
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture, mã controlplane.
- Chỉ dùng stdlib và controlplane domain/application idempotency.
- Không gọi dịch vụ thật.
