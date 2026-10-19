# Báo cáo bằng chứng D-08

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `dd68637ba76c9e3213de9b564226e2e69f35f230`
- Nguồn quyền: IMPL-PLAN-D Auditor PASS, slice D-08.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d08_script_version.py -q -p no:cacheprovider` (chạy với khung script.py chưa có hành vi)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `60 failed, 2 passed in 0.95s`
- Chi tiết các test FAILED chọn lọc kèm thông điệp assertion nguyên văn:
  - `FAILED tests/unit/creative/test_d08_script_version.py::test_claim_modes_are_exactly_the_four_contract_values`: `AssertionError: assert set() == {'creative_hy... 'transition'}`
  - `FAILED tests/unit/creative/test_d08_script_version.py::test_voice_track_input_types_match_binding`: `AssertionError: assert set() == {'pronunciati...t_version_id'}`
  - `FAILED tests/unit/creative/test_d08_script_version.py::test_drift_comparison_detects_mutated_binding`: `AssertionError: assert {} != {}`
  - `FAILED tests/unit/creative/test_d08_script_version.py::test_valid_script_builds_frozen_ordered_version`: `assert False where False = isinstance(None, ScriptVersion)`
  - `FAILED tests/unit/creative/test_d08_script_version.py::test_all_inference_and_creative_segments_carry_disclosure`: `AttributeError: 'NoneType' object has no attribute 'segments'`
  - `FAILED tests/unit/creative/test_d08_script_version.py::test_model_self_assessment_fields_never_decide_validity`: `Failed: DID NOT RAISE ScriptRejected`
  - `FAILED tests/unit/creative/test_d08_script_version.py::test_source_backed_requires_resolved_source_ref`: `Failed: DID NOT RAISE ScriptRejected`
  - `FAILED tests/unit/creative/test_d08_script_version.py::test_every_source_ref_goes_through_the_d03_resolver`: `AssertionError: assert [] == [{'workspace_...id': 'a2-r1'}]`
  - `FAILED tests/unit/creative/test_d08_script_version.py::test_normalization_and_word_count`: `AssertionError: assert '  Hello\n\tworld  ' == 'Hello world'`
  - `FAILED tests/unit/creative/test_d08_script_version.py::test_fingerprint_is_sha256_over_normalized_narration_in_segment_order`: `AttributeError: 'NoneType' object has no attribute 'script_fingerprint'`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, SyntaxError hay lỗi collection; RED là sai oracle do khung chưa triển khai hành vi (hằng rỗng, hàm trả None, normalize trả text gốc, không raise ScriptRejected).

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d08_script_version.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `62 passed in 0.12s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/creative/domain/script.py`: Triển khai đầy đủ hằng `CLAIM_MODES`, `VOICE_TRACK_INPUT_TYPES`, các hằng mã lỗi; ngoại lệ miền `ScriptRejected`; frozen dataclass `LanguageVoicePolicy` (với validation language và speech_rate dương hữu hạn), `TargetRange` (min/max_seconds dương hữu hạn, min <= max); value object `ScriptSegment` (order, text, claim_mode, scene_intent, source_refs, disclosure, word_count, estimated_seconds); aggregate `ScriptVersion` bất biến (properties `scene_intents`, `narration`, `script_fingerprint` tính sha256 qua RFC 8785 `request_hash` trên `fingerprint_basis()`, hàm `to_voice_track_inputs()` chuyển đổi khớp schema VoiceTrackRequest của binding `d-e-f-voice-timing`); hàm tiện ích `normalize_narration` (NFKC chuẩn hoá khoảng trắng) và `count_words`; hệ thống helper phân tích cú pháp `_parse_raw`; hàm khởi dựng miền `build_script_version` kiểm tra nghiêm ngặt kiểu resolver/policy/target_range, schema thô, khớp ngôn ngữ, xác thực ref qua `RefResolver` D-03, bắt buộc ref cho `source_backed`, bắt buộc disclosure cho `inference` và `creative_hypothesis`, tính thời lượng ước lượng theo speech_rate và chặn ngoài khoảng target range.
  - `tests/unit/creative/test_d08_script_version.py`: Bộ kiểm thử đơn vị toàn diện gồm 62 bài kiểm thử bao phủ khai báo `coveredIds: CT-AI-004, CT-TTS-001`, đối chiếu hằng và kiểm tra drift so với binding `d-e-f-voice-timing`, allowlist import và tái sử dụng D-03 `RefResolver` / `request_hash`, tính đóng băng bất biến của ScriptVersion/ScriptSegment, kiểm tra duyệt 100% disclosure cho segment inference/creative_hypothesis, vô hiệu hoá trường tự đánh giá của model (không được quyết định tính hợp lệ), kiểm tra bắt buộc ref hợp lệ cho source_backed, bẫy ref ảo (hallucinated ref), kiểm thử schema và thứ tự ưu tiên kiểm tra, kiểm tra policy/target range và tính toán thời lượng = số từ / speech_rate (loại bỏ hằng số từ cố định và kiểm tra biên 61.0–70.0s), kiểm tra chuẩn hoá lời dẫn và tính fingerprint SHA-256 xác định không đổi khi chỉ đổi metadata không thuộc lời dẫn, và đối chiếu kiểu dữ liệu `to_voice_track_inputs()` với binding contract.
  - `docs/delivery-evidence/d-08/report.md`: Báo cáo bằng chứng chuyển giao của task D-08.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/creative/test_d08_script_version.py -q -p no:cacheprovider` | 0 | 62 passed in 0.12s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## coveredIds

`CT-AI-004, CT-TTS-001 (phía D)`

## Quyết định mặc định (D8)

1. speech_rate là từ trên giây của LanguageVoicePolicy; target range tính bằng giây, đóng hai đầu; cả hai là input của caller, thiếu → INPUT_NOT_READY;
2. fingerprint = request_hash({'narration': [lời dẫn NFKC đã gộp khoảng trắng theo thứ tự segment]}), không gồm ID, intent, claim, ref, hint;
3. mọi source ref (kể cả inference, creative_hypothesis, transition nếu có) phải qua RefResolver D-03, source_backed bắt buộc có ít nhất một ref;
4. disclosure tường minh là chuỗi không rỗng sau chuẩn hoá, kiểm xác định, không đọc trường tự đánh giá của model;
5. scene intent theo từng segment; thumbnail_transition là text D-local vì CT-MED-004 chưa có binding (CONV-D-07);
6. hình dạng pronunciation hint `{term, pronunciation}` là GIẢ ĐỊNH vì binding chỉ ghi `array`;
7. metadata model/prompt/provider usage của CT-AI-004 không lưu trong value object này, thuộc application D-14/D-15 (GIẢ ĐỊNH);
8. thời lượng 61–70 giây thật được kiểm ở F (CT-QC-001), ước lượng của D chỉ là validator đầu vào (errata m5-d mục a).

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock.
- Không gọi dịch vụ thật.