# Báo cáo Nghiệm thu PW-E1: Lưu bền mọi kind của VoicePipeline và MediaPipeline

## 1. Mục tiêu và phạm vi PW-E1
- Mục tiêu: Mở rộng PostgresOutputRepository từ 2 kind (voice, word_timing) lên đủ 11 kind của VoicePipeline và MediaPipeline (voice, word_timing, tts_invocation, receipt, timing_report, language_evidence, probe_report, image_safety_assessment, processed_media, audio_bed_result, receipt_by_request), ánh xạ 1:1 vào 11 bảng của 0016_voice.sql mà không tạo migration mới.
- Phạm vi: Các tệp thuộc owned paths:
  + `src/voice/persistence/output_repository.py`
  + `tests/integration/prod_wiring/test_pw_e1_persistence.py`
  + `tests/integration/persistence/e/test_persist_e_postgres.py`
  + `docs/delivery-evidence/pw-e1/report.md`

## 2. Tệp đã đổi
- Tệp đã đổi: output_repository.py, test_pw_e1_persistence.py (mới), test_persist_e_postgres.py (đúng hai dòng), report.md; unit_of_work.py không đổi vì đơn vị công việc hiện có đã đủ (begin/commit/rollback, `reading()` đọc ngoài giao dịch cho receipt đầu pipeline)

## 3. Bảng ánh xạ 11 kind sang 11 bảng của 0016_voice.sql đúng như `_TABLES`
Bảng ánh xạ 11 kind sang 11 bảng của 0016_voice.sql:

| STT | Kind | Bảng PostgreSQL | Ghi chú khóa / cột | Kiểu bản ghi |
| --- | --- | --- | --- | --- |
| 1 | `voice` | `controlplane.cp_voice_tracks` | record_key, payload, voice_hash | VoiceTrack |
| 2 | `word_timing` | `controlplane.cp_word_timings` | record_key, payload, timing_artifact_ref | WordTimingRecord |
| 3 | `tts_invocation` | `controlplane.cp_tts_invocation_records` | record_key, payload | TtsInvocationRecord |
| 4 | `receipt` | `controlplane.cp_voice_receipts` | idempotency_key, aggregate_ref, request_hash | PipelineReceipt, OperationReceipt |
| 5 | `timing_report` | `controlplane.cp_timing_validation_reports` | record_key, payload | TimingValidationReport |
| 6 | `language_evidence` | `controlplane.cp_language_evidence` | record_key, payload | LanguageEvidence |
| 7 | `probe_report` | `controlplane.cp_probe_reports` | record_key, payload | ProbeReport |
| 8 | `image_safety_assessment` | `controlplane.cp_image_safety_assessments` | record_key, payload | ImageSafetyAssessment |
| 9 | `processed_media` | `controlplane.cp_processed_media` | record_key, payload | TransformResult, ProcessedRendition |
| 10 | `audio_bed_result` | `controlplane.cp_audio_bed_results` | record_key, payload | AudioBedResult |
| 11 | `receipt_by_request` | `controlplane.cp_analysis_results` | record_key, payload | OperationReceipt |

## 4. Quyết định mặc định đơn giản theo D8
- Quyết định mặc định đơn giản theo D8: receipt lưu JSON bản ghi trong cột aggregate_ref vì cp_voice_receipts không có cột payload, request_hash lấy từ bản ghi, chỉ một revision 1 cho mỗi khoá; receipt_by_request dùng cp_analysis_results vì là bảng duy nhất còn trống có dạng (record_key, revision, payload) và cần nhiều revision cho mỗi request fingerprint; 9 kind mới dùng mã hoá JSON tự mô tả có danh sách lớp cho phép; không thêm migration

## 5. Mục mở OI-PW-E1-01
- Mục mở OI-PW-E1-01: đề xuất PW-SCHEMA cân nhắc thêm cột payload cho cp_voice_receipts, không chặn PW-E1

## 6. Hai dòng đã đổi của test đã nghiệm thu
- Hai dòng đã đổi của test đã nghiệm thu: dòng 299 `uow.outputs.append('receipt', 'k', 1, object())` thành `uow.outputs.append('no_such_kind', 'k', 1, object())` và dòng 301 `uow.outputs.latest('receipt', 'k')` thành `uow.outputs.latest('no_such_kind', 'k')`; lý do: PW-E1 làm `receipt` thành kind hợp lệ nên test cần kind chắc chắn không hợp lệ; giữ nguyên `pytest.raises(UnsupportedKindError)` và mọi assertion khác

## 7. Bảng bằng chứng
### 7.1. Bảng lệnh kiểm tra bắt buộc và kết quả thực tế

| Bước | Lệnh kiểm tra | Exit Code | Kết quả thực tế |
| --- | --- | --- | --- |
| Bước 7 | `python -c "import pathlib; t = pathlib.Path('src/voice/persistence/output_repository.py').read_text(encoding='utf-8'); assert all(k in t for k in ['probe_report', 'processed_media', 'audio_bed_result', 'tts_invocation']) and 'from src.' not in t, 'PW-E1'"` | 0 | Đạt (PASS), tệp chứa đủ 4 kind và không có import 'from src.' |
| Bước 10 | `python -m pytest tests/integration/persistence/e/test_persist_e_postgres.py -q -p no:cacheprovider` | 0 | 19 passed in 7.89s |
| Bước 17 | `python -m pytest tests/integration/prod_wiring/test_pw_e1_persistence.py tests/integration/persistence/e/test_persist_e_postgres.py -q -p no:cacheprovider` | 0 | 24 passed in 10.15s (5 test PostgreSQL thật của PW-E1, 1 test kiểm tra kind tĩnh, 19 test PERSIST-E) |
| Bước 18 / 20 | `git diff --check` | 0 | Đạt (PASS), không có khoảng trắng thừa hay lỗi xuống dòng |

### 7.2. Ánh xạ coveredIds sang các test trong `test_pw_e1_persistence.py`

| Covered ID | Mô tả nghiệm thu | Các test tương ứng trong test_pw_e1_persistence.py |
| --- | --- | --- |
| `PW-E1-01` | PostgresOutputRepository hỗ trợ đầy đủ 11 kind của VoicePipeline và MediaPipeline trên PostgreSQL thật, kiểm thử giao dịch và idempotency | test_pw_e1_every_kind_of_both_pipelines_has_rows, test_pw_e1_replay_after_restart_returns_stored_receipt_and_writes_nothing, test_pw_e1_failure_midway_rolls_back_every_kind_and_the_outbox, test_pw_e1_repository_rejects_bad_kind_record_and_second_receipt_revision, test_pw_e1_supported_kinds_match_every_kind_the_pipelines_write |
| `CONV-E-01` | Lưu bền VoicePipeline trong PostgreSQL thật, replay và rollback | test_pw_e1_every_kind_of_both_pipelines_has_rows, test_pw_e1_replay_after_restart_returns_stored_receipt_and_writes_nothing, test_pw_e1_failure_midway_rolls_back_every_kind_and_the_outbox |
| `CT-MED-001` | Lưu bền MediaPipeline (probe, assess, transform, normalize, audio bed) trong PostgreSQL thật | test_pw_e1_every_kind_of_both_pipelines_has_rows, test_pw_e1_replay_after_restart_returns_stored_receipt_and_writes_nothing, test_pw_e1_failure_midway_rolls_back_every_kind_and_the_outbox |
