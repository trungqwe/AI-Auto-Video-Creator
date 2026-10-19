# Báo cáo bằng chứng E-09

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `5646473e81669af7143ea98e81869927ec761f5f`
- Nguồn quyền: IMPL-PLAN-E Auditor PASS, slice E-09 trong docs/implementation/e/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `108 failed, 6 passed in 1.01s`
- Chi tiết các test FAILED tiêu biểu kèm thông điệp AssertionError nguyên văn:
  - `FAILED tests/unit/voice/test_e09_word_timing.py::test_fixture_valid_payloads_are_accepted`: `AssertionError: assert False where False = isinstance(None, WordTimingRecord)`
  - `FAILED tests/unit/voice/test_e09_word_timing.py::test_fixture_invalid_payloads_report_expected_error[words_out_of_order]`: `AssertionError: assert [] == [('constraint_violation', 'words')]`
  - `FAILED tests/unit/voice/test_e09_word_timing.py::test_fixture_invalid_payloads_report_expected_error[word_beyond_voice_duration]`: `AssertionError: assert [] == [('constraint_violation', 'words')]`
  - `FAILED tests/unit/voice/test_e09_word_timing.py::test_fixture_invalid_payloads_report_expected_error[missing_voice_hash]`: `AssertionError: assert [] == [('missing_required', 'voice_hash')]`
  - `FAILED tests/unit/voice/test_e09_word_timing.py::test_valid_payload_returns_record_with_fixture_values`: `AssertionError: assert False where False = isinstance(None, WordTimingRecord)`
  - `FAILED tests/unit/voice/test_e09_word_timing.py::test_record_is_frozen_and_does_not_alias_payload`: `AssertionError: assert False where False = isinstance(None, WordTimingRecord)`
  - `FAILED tests/unit/voice/test_e09_word_timing.py::test_invalid_words_are_rejected[end_equals_start]`: `AssertionError: assert [] == [('constraint_violation', 'words')]`
  - `FAILED tests/unit/voice/test_e09_word_timing.py::test_invalid_words_are_rejected[overlap]`: `AssertionError: assert [] == [('constraint_violation', 'words')]`
  - `FAILED tests/unit/voice/test_e09_word_timing.py::test_invalid_words_are_rejected[start_bool]`: `AssertionError: assert [] == [('wrong_type', 'words')]`
  - `FAILED tests/unit/voice/test_e09_word_timing.py::test_missing_required_field_is_reported[voice_hash]`: `AssertionError: assert [] == [('missing_required', 'voice_hash')]`
  - `FAILED tests/unit/voice/test_e09_word_timing.py::test_sha256_must_be_lowercase_hex[5-voice_hash]`: `AssertionError: assert [] == [('wrong_type', 'voice_hash')]`
  - `FAILED tests/unit/voice/test_e09_word_timing.py::test_invalid_segment_boundaries_are_rejected[overlap]`: `AssertionError: assert [] == [('constraint_violation', 'segment_boundaries')]`
  - `FAILED tests/unit/voice/test_e09_word_timing.py::test_non_object_payload_is_wrong_type[None]`: `AssertionError: assert [] == [('wrong_type', '$')]`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 6 test so sánh cấu trúc/binding và quét import đã PASS ngay từ đầu (`test_constants_match_binding`, `test_binding_version_and_constraints_match_binding`, `test_drift_comparison_detects_mutated_binding`, `test_fixture_has_required_cases_and_pinned_codes`, `test_word_and_boundary_constants_match_fixture_keys`, `test_module_imports_only_allowed_stdlib`). Tất cả 108 test thất bại đều là `AssertionError` do các hàm khung chưa cài logic xử lý.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic validator)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `114 passed in 0.11s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/voice/domain/word_timing.py`: Cài đặt validator WordTiming hoàn chỉnh theo binding `BINDING-D-E-F-VOICE-TIMING` (CT-SUB-001 bất biến 1), bao gồm hằng đặc tả, các dataclass immutable (`WordTimingIssue`, `WordTimingWord`, `SegmentBoundary`, `WordTimingRecord`), ngoại lệ `WordTimingError`, và hai hàm công khai `word_timing_issues`, `validate_word_timing`.
  - `tests/unit/voice/test_e09_word_timing.py`: Bộ kiểm thử toàn diện 114 test cases so khớp hằng đặc tả với binding JSON, phát hiện biến đổi binding trái phép, kiểm thử fixture valid/invalid, kiểm thử phản ví dụ mức từ và segment, kiểm thử kiểu dữ liệu, tính frozen không alias, và cô lập ranh giới import chỉ dùng stdlib được phép.
  - `docs/delivery-evidence/e-09/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.
- Hằng đặc tả khớp hoàn toàn binding `d-e-f-voice-timing.json`.
- Ánh xạ phản ví dụ -> test:
  - `end <= start`: `test_invalid_words_are_rejected[end_equals_start]` và `test_invalid_words_are_rejected[end_before_start]`.
  - Vượt `voice_duration_ms`: `test_invalid_words_are_rejected[end_beyond_duration]` và fixture `word_beyond_voice_duration`.
  - Hai từ chồng lấn: `test_invalid_words_are_rejected[overlap]`, `test_invalid_words_are_rejected[duplicate_span]` và fixture `words_out_of_order`.
  - Hằng lệch binding: `test_constants_match_binding` và `test_drift_comparison_detects_mutated_binding`.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider` | 0 | `114 passed in 0.11s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Mức từ: `start_ms`/`end_ms` bắt buộc integer không bool; `text`, `normalized_text` (string) và `confidence` (number trong [0,1]) tùy chọn vì binding chỉ khai báo items object.
2. Lỗi cấp từ dùng field `words`, lỗi segment dùng field `segment_boundaries`.
3. Chồng lấn: `start_ms` của từ sau phải >= `end_ms` của từ trước, vi phạm là `constraint_violation` (chặt hơn binding, GIẢ ĐỊNH theo plan §7).
4. `segment_boundaries`: `0 <= start < end`, `start >= end` của segment trước, `end <= voice_duration_ms` khi có; mảng rỗng được chấp nhận.
5. `voice_duration_ms` phải > 0 khi có, `None` coi như vắng, không có hằng sai số hay policy.
6. sha256 sai (hoa, sai độ dài, ký tự lạ, xuống dòng) -> `wrong_type` theo `tests/contract/binding_validator.py`.
7. `validate_word_timing` ném `WordTimingError` (`.issues`/`.code`/`.field`) hoặc trả `WordTimingRecord` frozen; `word_timing_issues` trả mọi lỗi không trùng.
8. Nội dung `alignment_gaps` không kiểm ở E-09 (thuộc E-10).

## coveredIds

- `CT-SUB-001 bất biến 1`

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- ROADMAP-OPEN-008/TEST-OPEN-006 khi nới quy tắc chồng lấn
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`, binding, fixture.
- Chỉ dùng thư viện chuẩn Python (stdlib).
- Không gọi dịch vụ thật, không chạy FFmpeg.
