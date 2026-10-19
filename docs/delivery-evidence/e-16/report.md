# Báo cáo bằng chứng E-16

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 6edd27271fc7408d857d4dcaafbfbae308c7f73f
- Nguồn quyền: IMPL-PLAN-E Auditor PASS và slice E-16 trong docs/implementation/e/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py -q -p no:cacheprovider (chạy với khung stub ở các bước 1 đến 8)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 21 failed, 2 passed in 0.50s
- Chi tiết: Các test CreateVoiceTrack, CreateWordTiming và require_current_timing fail do phương thức stub ném NotImplementedError; 2 test pass gồm test_outbox_failure_rolls_back_voice_invocation_and_receipt (chờ RuntimeError mà NotImplementedError kế thừa RuntimeError) và test_sources_have_no_clock_io_or_adapter_imports (kiểm tra ranh giới tĩnh import). Xác nhận hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection.

## GREEN

- Lệnh thực thi: python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py -q -p no:cacheprovider (chạy sau khi hoàn thiện FakeAligner và VoicePipeline)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 23 passed in 0.13s

## Thay đổi

- Năm tệp thuộc owned paths và vai trò từng tệp:
  - src/voice/ports/aligner.py: Định nghĩa pure port AlignerPort (giao thức align nhận AlignmentRequest trả AlignmentResult), exception AlignerError, dataclass AlignmentRequest và AlignmentResult (tuân thủ CT-SUB-001, không I/O, không clock).
  - src/voice/adapters/fake_aligner.py: Triển khai FakeAligner in-memory cho test, hỗ trợ các mode: 'ok' (chia đều thời lượng theo từ, chuẩn hóa NFC, casefold, bỏ dấu câu ở biên), 'reorder' (đảo thứ tự từ), 'drop_last' (thiếu từ cuối), 'beyond_duration' (từ vượt quá thời lượng voice) và mô phỏng AlignerError.
  - src/voice/application/voice_pipeline.py: Định nghĩa và cài đặt VoicePipeline với 3 phương thức: create_voice_track (kiểm binding script, kiểm duration policy, resolve route, chạy TTS attempts, đo duration, ghi VoiceTrack + TtsInvocationRecord + PipelineReceipt + outbox VoiceReady trong một UoW), create_word_timing (yêu cầu voice đã commit, kiểm binding script, gọi aligner, validate word timing, check coverage, build gap report, build language evidence, ghi WordTiming + TimingValidationReport + LanguageEvidence + PipelineReceipt + outbox WordTimingReady trong một UoW), và require_current_timing (kiểm tra tính hợp lệ của timing mới nhất so với script fingerprint và voice hash hiện hành, chống stale timing theo TST-MEDIA-INV-007).
  - tests/integration/voice/test_e16_voice_timing_pipeline.py: Bộ kiểm thử tích hợp 23 test cases in-process kiểm chứng toàn bộ quy trình tạo VoiceTrack, xử lý thất bại, replay idempotency, tạo WordTiming, ràng buộc coverage/duration, rollback transaction khi outbox lỗi, và vô hiệu hóa timing cũ khi thay đổi script hoặc voice.
  - docs/delivery-evidence/e-16/report.md: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py -q -p no:cacheprovider | 0 | 23 passed in 0.13s |
| 2 | git diff --check | 0 | PASS (không output, không trailing whitespace) |

## Ánh xạ phản ví dụ -> test

- Gọi TTS trước khi kiểm fingerprint: test_fingerprint_mismatch_is_rejected_before_any_tts_call
- Outbox ngoài UoW: test_outbox_failure_rolls_back_voice_invocation_and_receipt và test_outbox_failure_rolls_back_timing_report_evidence_and_receipt
- Gửi lặp tạo voice thứ hai: test_same_operation_key_and_payload_replays_receipt_without_second_voice
- Timing cũ sau khi đổi voice: test_voice_change_after_timing_rejects_old_timing_and_new_timing_needs_new_command
- Timing khi chưa có voice: test_create_word_timing_without_voice_is_rejected_and_aligner_not_called

## Quyết định mặc định (D8)

1. track_key do caller cấp; kind voice, word_timing, tts_invocation, timing_report, language_evidence ghi theo track_key, receipt theo khoá workspace:command:operation_key;
2. receipt_ref = 'receipt-' + 32 ký tự đầu của request_hash({command, request});
3. voice_artifact_ref = 'voice-artifact-<voice_hash>' là GIẢ ĐỊNH đến khi có artifact store (CONV-E-02), không lưu byte âm thanh;
4. thời lượng voice đo qua hàm measure_duration_ms được inject, ffprobe thật ở CONV-E-02 và CP7-E-04;
5. TTS lỗi hoặc duration ngoài policy ghi invocation record trong UoW riêng, không receipt, không event, retry do G quyết;
6. replay CreateWordTiming kiểm lại binding với script và voice hiện tại, lệch thì TimingBindingError;
7. lệch locale chỉ ghi finding language_mismatch, F quyết;
8. timing_artifact_ref và validation_report_ref dẫn xuất từ hash nội dung;
9. không persistence PostgreSQL (CONV-E-01), không event vô hiệu hóa timing;
10. AlignerPort chỉ có port và fake, công cụ aligner chờ CP7-E-02.

## coveredIds

- CT-TTS-001
- CT-SUB-001
- CT-RND-002
- TST-MEDIA-INV-007 (phía E)

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture, mã controlplane hay domain/ports khác của E.
- Không gọi dịch vụ thật.
