# Báo cáo bằng chứng F-18

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: ddeec203cadc4982286cbfa02a4882905967b7d1
- Nguồn quyền: IMPL-PLAN-F Auditor PASS và slice F-18 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/integration/render/test_f18_render_video_pipeline.py -q -p no:cacheprovider (trên stub trung tính: render_video và reconcile_render ném NotImplementedError STUB-F18)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 24 failed, 4 passed in 0.68s
- Các dòng FAILED tiêu biểu: FAILED tests/integration/render/test_f18_render_video_pipeline.py::test_success_gives_succeeded_attempt_outbox_event_and_returns_the_lease; FAILED tests/integration/render/test_f18_render_video_pipeline.py::test_reconcile_resolves_to_succeeded_when_hash_and_playback_match; FAILED tests/integration/render/test_f18_render_video_pipeline.py::test_direct_retry_from_outcome_unknown_is_refused_before_lease_and_renderer
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED hợp lệ do hành vi chưa có ở stub trung tính.

## GREEN

- Lệnh thực thi: python -m pytest tests/integration/render/test_f18_render_video_pipeline.py -q -p no:cacheprovider
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 28 passed in 0.24s

## Thay đổi

- src/render/ports/lease.py: GpuLeasePort (acquire, release) cho LOCK-DESKTOP-GPU, GpuLease, GpuLeaseUnavailable.
- src/render/ports/renderer.py: RendererPort.run(spec), RendererOutcome (trạng thái, output ref, sha256, metrics, lỗi), RendererTimeout, OutputObservationPort.
- src/render/adapters/fake_renderer.py: FakeRenderer tiêm lỗi trước, trong, sau side effect; FakeOutputStorage không xoá, không ghi đè.
- src/render/application/render_video.py: RenderPipeline với render_video và reconcile_render; InMemoryRenderUnitOfWork.
- tests/integration/render/test_f18_render_video_pipeline.py: 28 ca kiểm thử.
- docs/delivery-evidence/f-18/report.md: báo cáo bằng chứng này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/integration/render/test_f18_render_video_pipeline.py -q -p no:cacheprovider | 0 | 28 passed in 0.24s |
| 2 | python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider | 0 | 12 passed, 75 subtests passed in 0.19s |
| 3 | python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py -q -p no:cacheprovider | 0 | 36 passed in 0.20s |
| 4 | python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cacheprovider | 0 | 38 passed in 0.15s |
| 5 | probe không còn marker STUB-F18 | 0 | PASS (không có output, không còn marker STUB-F18) |
| 6 | probe tiếng Việt của report.md | 0 | PASS (UTF-8 không BOM, tiếng Việt đầy đủ dấu, không ký tự thay thế) |
| 7 | git diff --check | 0 | PASS (không có output, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Hai UoW: attempt được lưu STARTED và commit trước khi gọi renderer; kết quả lưu ở UoW thứ hai. Crash giữa chừng để lại STARTED, lệnh RenderVideo kế tiếp bị từ chối attempt_in_progress; phục hồi attempt STARTED treo thuộc G (CONV-F-05).
2. render_attempt_id là khoá idempotency; G cấp render_attempt_id, output_artifact_ref, receipt_ref. Id đã lưu thì replay, không gọi renderer, không lấy lease.
3. Thứ tự gate: grant, replay, package và report passing đúng fingerprint (package_not_validated), attempt OUTCOME_UNKNOWN (reconcile_required) hoặc đang chạy (attempt_in_progress), rồi mới lấy lease. validation_context tuỳ chọn: khi có thì validate lại ngay trước khi render (F-17 mục 8), không lưu report mới.
4. RendererTimeout cho OUTCOME_UNKNOWN; exception khác và outcome không SUCCEEDED cho FAILED. SUCCEEDED chỉ khi output_ref khớp, tệp tồn tại, sha256 khớp và probe decodable; ngược lại FAILED (output_missing, output_hash_mismatch, output_not_decodable). Output mồ côi không bao giờ ready vì retry dùng output mới.
5. ReconcileRender dùng OutputProbePort của F-13 cùng OutputObservationPort; expected_sha256 là đầu vào từ G hoặc I vì renderer chưa trả receipt. Thiếu expected_sha256 hoặc bằng chứng không kết luận thì giữ OUTCOME_UNKNOWN và không ghi gì.
6. Không xoá, không ghi đè: FakeOutputStorage từ chối ghi đè (OutputAlreadyExists), chỉ có write, observe, probe; tệp partial được giữ lại.
7. Lỗi renderer được che bằng secret_values của command và các regex của F-11; ProblemDetail và event chỉ chứa mã và ref.
8. GpuLeasePort chỉ có acquire và release cho LOCK-DESKTOP-GPU, số slot không nằm trong mã; thiếu slot cho GpuLeaseNotAvailable (retryable, category capacity) để G đặt WAITING_CAPABILITY.
9. memory.py và repositories.py nằm ngoài owned paths nên bảng attempt_index nằm trong InMemoryRenderUnitOfWork của render_video.py (cùng cách F-17); PostgreSQL chờ CONV-F-01.
10. Test import fixture từ test_f17_resolve_validate_pipeline.py để không nhân đôi dữ liệu.

## Ánh xạ phản ví dụ

- Lease không trả khi renderer ném lỗi: test_crash_before_or_during_the_side_effect_is_failed_without_ready_output, test_lease_is_returned_when_settling_the_attempt_raises, test_new_attempt_cannot_reuse_an_earlier_output_ref_and_the_lease_is_returned.
- Retry trực tiếp từ OUTCOME_UNKNOWN: test_direct_retry_from_outcome_unknown_is_refused_before_lease_and_renderer, test_reconcile_without_conclusive_evidence_keeps_outcome_unknown.
- Attempt mới ghi đè output cũ: test_new_attempt_cannot_reuse_an_earlier_output_ref_and_the_lease_is_returned, test_retry_after_reconcile_failed_makes_a_new_attempt_with_a_new_output, test_fake_storage_has_no_delete_and_refuses_overwrite.
- Xoá tệp partial: test_crash_before_or_during_the_side_effect_is_failed_without_ready_output, test_partial_file_or_hash_mismatch_is_failed_not_ready_and_the_file_is_kept.
- Render package chưa validate: test_package_without_a_passing_report_is_refused_before_lease_and_renderer.

## coveredIds

- CT-RND-004, CT-STATE-011, TST-SEC-INV-012, TST-E2E-001 (đoạn render), TST-CTR-INV-001.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10.
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- Không chạy full suite, không chạy tests/m1 hay tests/m2.
- Không sửa tệp ngoài owned paths; không gọi dịch vụ thật; FFmpeg thật và LeaseManager thật chờ CONV-F-02 và CP7.
- Attempt STARTED treo do crash tiến trình chưa có đường phục hồi trong F; thuộc G (CONV-F-05).
