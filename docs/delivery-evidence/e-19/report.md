# Báo cáo bằng chứng E-19

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: cfd868a1406b38b34a1c05230e60b26e82692726
- Nguồn quyền: IMPL-PLAN-E Auditor PASS và slice E-19 trong docs/implementation/e/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e19_trace_projection.py -q -p no:cacheprovider (chạy với khung stub ở bước 1 và 4)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 28 failed, 7 passed in 0.43s
- Chi tiết các test FAILED tiêu biểu kèm thông điệp:
  - FAILED tests/unit/voice/test_e19_trace_projection.py::test_trace_voice_traces_script_route_provider_model_revision_and_receipt: NotImplementedError trong trace_voice
  - FAILED tests/unit/voice/test_e19_trace_projection.py::test_trace_timing_traces_voice_hash_script_fingerprint_report_and_language_evidence: NotImplementedError trong trace_timing
  - FAILED tests/unit/voice/test_e19_trace_projection.py::test_trace_processed_media_traces_inputs_spec_revision_and_processor_identity: NotImplementedError trong trace_processed_media
  - FAILED tests/unit/voice/test_e19_trace_projection.py::test_queries_never_call_provider_and_only_read: NotImplementedError trong trace_voice
  - FAILED tests/unit/voice/test_e19_trace_projection.py::test_reader_must_provide_the_read_ports: NotImplementedError trong trace_voice
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 7 test (các test kiểm tra ProcessingContractError khi thiếu processor identity, MediaEntry kiểm tra kiểu và output_kind, cùng test AST cô lập mã nguồn) đã PASS. Tất cả 28 test thất bại đều do method stub ném NotImplementedError.

## GREEN

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e19_trace_projection.py -q -p no:cacheprovider (chạy sau khi cài đặt logic hoàn chỉnh)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 35 passed in 0.11s

## Thay đổi

- Ba tệp thuộc owned paths và vai trò từng tệp:
  - src/voice/projections/trace_queries.py: Cài đặt projection truy vết read-only của voice, timing và processed media qua cổng TraceReader tiêm vào; gồm các dataclass VoiceEntry, TimingEntry, MediaEntry, TraceReader protocol, các view VoiceTrace, TimingTrace, LanguageEvidenceView, InputRef, ProcessedMediaTrace, RevisionRef; các hàm truy vết trace_voice, trace_timing, trace_processed_media; kiểm tra tham số truy vấn, lọc nghiêm ngặt theo workspace và key/operation_id, bảo tồn lịch sử revision tăng dần, redact triệt để secret/URL credentials/unredacted traceback, và không bao giờ gọi hay import provider/adapter.
  - tests/unit/voice/test_e19_trace_projection.py: Bộ kiểm thử 35 test cases bao quát: truy ngược đầy đủ các trường VoiceTrack/WordTiming/ProcessedMedia, route facts None không bịa, lịch sử revision và lựa chọn bản cũ, lọc nghiêm ngặt workspace_id, redact secret/traceback/URL, gắn LanguageEvidence chỉ khi khớp timing, từ chối ProcessingResult thiếu processor_identity, phân loại retention_class per_video/reusable/diagnostic, kiểm tra 0 lượt gọi provider (fake đếm), từ chối tham số không hợp lệ, reader phải cài cổng, view frozen và JSON-safe, và AST kiểm tra không import adapter/ứng dụng/mạng và không gọi hàm ghi.
  - docs/delivery-evidence/e-19/report.md: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.
- Ánh xạ phản ví dụ sang test:
  - Query kích hoạt TTS -> test_queries_never_call_provider_and_only_read và test_module_is_read_only_and_isolated
  - Trả output workspace khác -> test_trace_voice_returns_only_entries_of_the_asked_workspace_and_key, test_trace_timing_lists_history_and_filters_workspace, test_trace_processed_media_lists_history_and_filters_workspace
  - Trace thiếu processor identity -> test_result_without_processor_identity_cannot_become_a_trace_entry và test_trace_processed_media_traces_inputs_spec_revision_and_processor_identity

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/voice/test_e19_trace_projection.py -q -p no:cacheprovider | 0 | 35 passed in 0.11s |
| 2 | python -m pytest tests/unit/voice -q -p no:cacheprovider | 0 | 964 passed, 49 subtests passed in 1.59s |
| 3 | git diff --check | 0 | PASS (không output, không trailing whitespace) |

## Quyết định mặc định (D8)

1. Cổng TraceReader nằm trong trace_queries.py vì owned paths chỉ có hai tệp nguồn, mỗi entry mang workspace_id vì OutputRepository của E-15 không lưu workspace, adapter thật chờ CONV-E-01;
2. Provider, model, route do reader cung cấp vì TtsInvocationRecord của E-14 chưa có trong nhánh, thiếu thì trả None không bịa (GIẢ ĐỊNH);
3. LanguageEvidence chỉ gắn khi khớp voice_hash, script_fingerprint, timing_artifact_ref;
4. Retention: voice và word_timing là per_video, media theo retention_intent của output_kind (reusable, per_video, diagnostic);
5. Redact: định danh chỉ giữ khi khớp regex định danh và không chứa từ khoá bí mật, warning chứa từ khoá bí mật hoặc traceback thành [redacted], URL mất userinfo và query, usage_metrics chỉ giữ số với tên an toàn;
6. Mặc định trả revision mới nhất, tham số revision chọn bản cũ, history liệt kê mọi revision tăng dần;
7. Bản ghi của workspace khác hoặc không tồn tại đều trả None;

## coveredIds

- acceptance §10 mục 1 của contract 07

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) - chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture, mã controlplane.
- Chỉ dùng stdlib và domain của voice/controlplane.
- Không gọi dịch vụ thật.
