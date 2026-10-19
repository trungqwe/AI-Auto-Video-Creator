# Báo cáo bằng chứng E-08

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 5646473e81669af7143ea98e81869927ec761f5f
- Nguồn quyền: IMPL-PLAN-E Auditor PASS, slice E-08 trong docs/implementation/e/slices.md; binding d-e-f-voice-timing và fixture payloads.json.

## RED

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e08_voice_track.py -q -p no:cacheprovider (chạy trên khung tối thiểu bước 13 trước khi bổ sung hành vi)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 52 failed, 11 passed in 0.46s
- Chi tiết các test FAILED (52 test) kèm thông điệp assertion rút gọn:
  - 	est_binding_version_constant_matches_binding: AssertionError: assert '' == '1.0.0'
  - 	est_constants_match_binding[VoiceTrackRequest-required0-optional0]: AssertionError: VoiceTrackRequest assert mappingproxy({})
  - 	est_constants_match_binding[VoiceTrackResult-required1-optional1]: AssertionError: VoiceTrackResult assert mappingproxy({})
  - 	est_drift_comparison_detects_mutated_binding: AssertionError: VOICE_TRACK_REQUEST_REQUIRED must not be empty
  - 	est_fixture_invalid_cases_report_expected_error: AssertionError: missing_script_fingerprint assert [] == [('missing_required', 'script_fingerprint')]
  - 	est_missing_script_fingerprint_is_missing_required: AssertionError: assert [] == [('missing_required', 'script_fingerprint')]
  - 	est_duration_must_be_integer_not_text_or_bool[65s, True, False, 65000.0, None, [65000]] (6 cases): AssertionError: assert [] == [('wrong_type', 'actual_duration_ms')]
  - 	est_sha256_fields_require_lowercase_hex[...] (6 cases): AssertionError: assert [] == [('wrong_type', 'script_fingerprint')]
  - 	est_non_mapping_payload_is_wrong_type: AssertionError: assert [] == [('wrong_type', '$')]
  - 	est_optional_hints_and_style_are_accepted_and_kept: AssertionError: assert [] == [('wrong_type', 'pronunciation_hints')]
  - 	est_compute_voice_hash_is_lowercase_sha256_hex: AssertionError: assert '' == 'cee4eb2a...'
  - 	est_compute_voice_hash_rejects_non_bytes[...] (4 cases): Failed: DID NOT RAISE TypeError
  - 	est_verify_script_binding_rejects_mismatched_fingerprint: Failed: DID NOT RAISE ScriptBindingError
  - 	est_verify_script_binding_rejects_other_script_version: Failed: DID NOT RAISE ScriptBindingError
  - 	est_verify_script_binding_rejects_invalid_request: Failed: DID NOT RAISE VoiceTrackValidationError
  - 	est_verify_script_binding_trusts_fingerprint_from_d_and_never_recomputes: Failed: DID NOT RAISE ScriptBindingError
  - 	est_voice_track_is_frozen_with_result_fields_and_per_video_retention: AssertionError: assert False where False = isinstance(None, VoiceTrack)
  - 	est_voice_track_rejects_non_per_video_retention: Failed: DID NOT RAISE ValueError
  - 	est_voice_track_copies_mutable_inputs: AssertionError: assert False where False = isinstance(None, VoiceTrack)
  - 	est_voice_track_from_payload_rejects_fixture_invalid_cases: Failed: DID NOT RAISE VoiceTrackValidationError
  - 	est_voice_track_direct_construction_is_validated: Failed: DID NOT RAISE VoiceTrackValidationError
  - 	est_voice_track_to_payload_round_trips: AssertionError: assert False where False = isinstance(None, VoiceTrack)
  - 	est_voice_track_ignores_unknown_fields_in_payload: AssertionError: assert False where False = isinstance(None, VoiceTrack)
  - 	est_check_duration_without_policy_is_input_not_ready: Failed: DID NOT RAISE VoiceTrackRejected
  - 	est_check_duration_outside_range_reports_finding: AssertionError: 0 assert None is not None
  - 	est_check_duration_range_comes_only_from_policy: AttributeError: 'NoneType' object has no attribute 'code'
  - 	est_check_duration_rejects_non_integer_duration[...] (5 cases): Failed: DID NOT RAISE ValueError
  - 	est_check_duration_rejects_malformed_policy[...] (6 cases): Failed: DID NOT RAISE ValueError
  - 	est_sources_import_only_stdlib_and_voice_ports: AssertionError: assert 'voice.ports.script_text' in ['__future__', 'dataclasses', 'types']
  - 	est_only_compute_voice_hash_hashes_in_voice_track_source: AssertionError: compute_voice_hash must hash with sha256
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection; các lỗi đều do oracle kiểm thử hành vi.

## Thay đổi

4 tệp thuộc owned paths được tạo/cập nhật:
- src/voice/domain/voice_track.py:
  - Hằng đặc tả khớp binding: BINDING_VERSION, VOICE_TRACK_REQUEST_REQUIRED, VOICE_TRACK_REQUEST_OPTIONAL, VOICE_TRACK_RESULT_REQUIRED, VOICE_TRACK_RESULT_OPTIONAL.
  - Hằng mã lỗi: MISSING_REQUIRED, WRONG_TYPE, INPUT_NOT_READY, SCRIPT_FINGERPRINT_MISMATCH, SCRIPT_VERSION_MISMATCH, VOICE_DURATION_OUT_OF_RANGE.
  - Hằng RETENTION_PER_VIDEO = 'per_video'.
  - Lớp lỗi và cấu trúc dữ liệu: ValidationIssue, VoiceTrackValidationError, ScriptBindingError, VoiceTrackRejected, DurationFinding.
  - Hàm kiểm tra boundary: matches_type,
alidate_voice_track_request,
alidate_voice_track_result.
  - Giá trị bất biến VoiceTrack (frozen,
etention_class='per_video', deepcopy usage_metrics và warnings,
rom_payload, 	o_payload).
  - Hàm nghiệp vụ:
erify_script_binding (so sánh trực tiếp fingerprint từ D, không tính lại), compute_voice_hash (sha256 hex chữ thường), check_duration (policy None → INPUT_NOT_READY, ngoài khoảng → VOICE_DURATION_OUT_OF_RANGE).
- src/voice/ports/script_text.py:
  - Dataclass ScriptText frozen (chứa script_version_id, 	ext, script_fingerprint).
  - Port đọc ScriptTextPort là Protocol runtime_checkable với phương thức get_text(script_version_id: str) -> ScriptText.
- 	ests/unit/voice/test_e08_voice_track.py:
  - Bộ kiểm thử unit toàn diện gồm 63 test bao phủ binding drift, fixture valid/invalid, kiểu dữ liệu, fingerprint mismatch/trust, bất biến frozen, duration policy guard, và kiểm tra tĩnh AST.
- docs/delivery-evidence/e-08/report.md:
  - Báo cáo bằng chứng chuyển giao của slice E-08.

## Ánh xạ acceptance

| Yêu cầu acceptance | Kiểm thử xác minh | Trạng thái |
|---|---|---|
| Hằng đặc tả VoiceTrackRequest/Result khớp binding | 	est_constants_match_binding, 	est_drift_comparison_detects_mutated_binding | PASS |
| Validator chạy đủ case fixture invalid (missing_script_fingerprint → missing_required, duration_as_text / duration_as_boolean → wrong_type field ctual_duration_ms) | 	est_fixture_invalid_cases_report_expected_error, 	est_missing_script_fingerprint_is_missing_required, 	est_duration_must_be_integer_not_text_or_bool | PASS |
| ScriptTextPort Protocol | 	est_script_text_port_is_runtime_protocol, 	est_script_text_is_frozen | PASS |
|
erify_script_binding từ chối fingerprint lệch (script_fingerprint_mismatch), version lệch | 	est_verify_script_binding_rejects_mismatched_fingerprint, 	est_verify_script_binding_rejects_other_script_version | PASS |
| Không tự tính lại fingerprint script trong E | 	est_verify_script_binding_trusts_fingerprint_from_d_and_never_recomputes, 	est_only_compute_voice_hash_hashes_in_voice_track_source | PASS |
| compute_voice_hash sha256 hex thường | 	est_compute_voice_hash_is_lowercase_sha256_hex, 	est_compute_voice_hash_rejects_non_bytes | PASS |
| VoiceTrack frozen với
etention_class per_video | 	est_voice_track_is_frozen_with_result_fields_and_per_video_retention, 	est_voice_track_rejects_non_per_video_retention | PASS |
| check_duration: policy None → INPUT_NOT_READY, ngoài khoảng →
oice_duration_out_of_range | 	est_check_duration_without_policy_is_input_not_ready, 	est_check_duration_outside_range_reports_finding, 	est_check_duration_range_comes_only_from_policy | PASS |
| Khoảng 61000–70000 chỉ trong fixture test-only, không có hằng số trong mã | 	est_sources_have_no_duration_range_constant, 	est_range_detector_flags_counterexamples | PASS |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/voice/test_e08_voice_track.py -q -p no:cacheprovider | 0 | 63 passed in 0.09s |
| 2 | git diff --check | 0 | PASS (không có output, không có trailing whitespace, diff sạch) |

## Quyết định mặc định (D8)

1. ScriptText là dataclass frozen do port trả, fingerprint do D tính, E chỉ so sánh (CONV-E-07).
2.
erify_script_binding nhận request dạng Mapping, kiểm binding trước, kiểm thêm script_version_id khớp (script_version_mismatch).
3. check_duration biên bao gồm, policy hoặc biên None → INPUT_NOT_READY, trong khoảng trả None, ngoài khoảng trả DurationFinding.
4. Khoảng 61000–70000 chỉ nằm trong test, nhãn test-only GIẢ ĐỊNH.
5. Chỉ dùng stdlib, không import controlplane.
6. VoiceTrack sao chép sâu usage_metrics và warnings ở biên,
etention_class chỉ là intent per_video, cleanup thuộc I.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10; CP7 tài nguyên thật (D5)
- ROADMAP-OPEN-008/TEST-OPEN-006
- TTS primary/fallback (TECH-OPEN-004)
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock.
- Không gọi mạng hay TTS thật.
- SHA commit báo trong worker_done, không ghi trong tệp này.
