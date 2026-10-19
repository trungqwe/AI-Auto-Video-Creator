# Báo cáo bằng chứng E-13

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `df699e2d86efeff98f7214fac6cdb40420440ca5`
- Nguồn quyền: IMPL-PLAN-E Auditor PASS, slice E-13 trong `docs/implementation/e/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/voice/test_e13_audio_bed.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `57 failed, 6 passed in 0.71s`
- Chi tiết các test FAILED tiêu biểu kèm thông điệp AssertionError nguyên văn:
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_invalid_cue_is_rejected[start_equals_end]`: `Failed: DID NOT RAISE AudioBedError`
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_invalid_cue_is_rejected[start_bool]`: `Failed: DID NOT RAISE AudioBedError`
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_invalid_request_is_rejected[cues_empty]`: `Failed: DID NOT RAISE AudioBedError`
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_invalid_constraints_are_rejected[min_lufs_greater_than_max]`: `Failed: DID NOT RAISE AudioBedError`
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_missing_constraints_is_input_not_ready`: `Failed: DID NOT RAISE AudioBedRejected`
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_integrated_below_min_is_out_of_target`: `AssertionError: assert () == (LoudnessFinding(code='loudness_out_of_target', field='integrated_lufs', measured=-30.0),)`
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_true_peak_above_max_is_out_of_target`: `AssertionError: assert () == (LoudnessFinding(code='loudness_out_of_target', field='true_peak_dbtp', measured=0.0),)`
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_both_measurements_out_of_target`: `AssertionError: assert () == (LoudnessFinding(code='loudness_out_of_target', field='integrated_lufs', measured=-30.0), LoudnessFinding(code='loudness_out_of_target', field='true_peak_dbtp', measured=0.0))`
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_target_comes_from_argument_not_code`: `AssertionError: assert () == (LoudnessFinding(code='loudness_out_of_target', field='integrated_lufs', measured=-20.0),)`
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_matching_renditions_build_result`: `AssertionError: assert False where False = isinstance(None, AudioBedResult)`
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_track_swap_without_fallback_is_rejected`: `Failed: DID NOT RAISE AudioBedError`
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_substitution_recording_when_fallback_allowed`: `AssertionError: assert () == (Substitution(cue_index=0, change='track', original='artifact://music-a', replacement='artifact://music-b'),)`
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_track_outside_given_refs_is_rejected_even_with_fallback`: `Failed: DID NOT RAISE AudioBedError`
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_invalid_renditions_and_substitutions_structure_rejected`: `Failed: DID NOT RAISE AudioBedError`
  - `FAILED tests/unit/voice/test_e13_audio_bed.py::test_build_precedence_and_validation`: `Failed: DID NOT RAISE AudioBedRejected`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 6 test cấu trúc, kiểm tra bound None hợp lệ và quét AST không chứa hằng số cứng đã PASS ngay từ đầu (`test_valid_cue_is_frozen`, `test_request_allows_none_loudness_constraints`, `test_constraints_allow_none_bounds_at_construction`, `test_report_inside_target_has_no_findings`, `test_report_on_exact_boundaries_has_no_findings`, `test_module_has_no_hardcoded_loudness`). Tất cả 57 test thất bại đều là `AssertionError` hoặc `DID NOT RAISE` do các dataclass và hàm khung chưa cài đặt logic kiểm tra.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/voice/test_e13_audio_bed.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic validator hoàn chỉnh)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `63 passed in 0.07s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/voice/domain/audio_bed.py`: Cài đặt validator PrepareAudioBed hoàn chỉnh theo CT-AUD-001, bao gồm các dataclass immutable (`AudioCue`, `LoudnessConstraints`, `LoudnessReport`, `PreparedRendition`, `AudioBedRequest`, `AudioBedResult`, `LoudnessFinding`, `CueTiming`, `Substitution`), ngoại lệ `AudioBedError` và `AudioBedRejected`, cùng ba hàm nghiệp vụ thuần túy `validate_loudness_report`, `detect_substitutions`, `build_audio_bed_result`.
  - `tests/unit/voice/test_e13_audio_bed.py`: Bộ kiểm thử toàn diện 63 test cases bao phủ toàn bộ phản ví dụ, kiểm tra kiểu dữ liệu chặt chẽ (integer không nhận bool), tính bất biến frozen không alias mapping, phát hiện thay thế track/mood theo quyền fallback, thứ tự ưu tiên lỗi trong hàm build, và quét AST xác nhận không có hằng số loudness cứng.
  - `docs/delivery-evidence/e-13/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.
- Ánh xạ phản ví dụ → test:
  - Hằng -14 đến -16 LUFS trong mã: `test_module_has_no_hardcoded_loudness` (quét AST cấm hằng số khác 0 và regex r'-\s*1[46]\b') và `test_target_comes_from_argument_not_code` (chứng minh ngưỡng lấy từ tham số constraints truyền vào, không lấy từ hằng mã nguồn).
  - Đổi bài khi plan không cho fallback: `test_track_swap_without_fallback_is_rejected` (ném `substitution_not_allowed` khi đổi track hoặc mood với `fallback_allowed=False`).
  - Thay thế không được ghi lại: `test_substitution_recording_when_fallback_allowed` (xác nhận thay thế track và mood được ghi đầy đủ vào `AudioBedResult.substitutions`).
  - Cue có start lớn hơn hoặc bằng end hoặc âm: `test_invalid_cue_is_rejected[start_equals_end]`, `test_invalid_cue_is_rejected[start_greater_than_end]`, `test_invalid_cue_is_rejected[start_negative]`, `test_invalid_cue_is_rejected[end_negative]`.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/voice/test_e13_audio_bed.py -q -p no:cacheprovider` | 0 | `63 passed in 0.07s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Binding CT-AUD-001 chưa tồn tại nên hình dạng trường là GIẢ ĐỊNH theo slice và CONV-E-07.
2. `cues` trong `AudioBedRequest` phải không rỗng; mọi phần tử phải là `AudioCue`.
3. Cue chồng thời gian được phép (music và sfx được phép phát song song / chồng nhau).
4. `mood` và artifact ref của cue là tùy chọn/chuẩn hóa theo schema domain.
5. Chặn thay thế là kiểm tra trên renditions so với cue gốc của request; thay thế hợp lệ tự động ghi vào `substitutions`.
6. Thay thế track chỉ được dùng artifact ref có sẵn trong cues hoặc `fallback_artifact_refs`, kể cả khi `fallback_allowed` là True; tuyệt đối không chọn bài mới ngoài refs đã cho.
7. Ràng buộc loudness gồm `min_lufs`, `max_lufs`, `max_true_peak_dbtp`, biên so sánh là bao gồm (bằng biên coi là đạt).
8. `constraints` là None hoặc có bất kỳ bound nào là None → ném `AudioBedRejected(INPUT_NOT_READY, 'missing_loudness_constraints')`; constraints sai kiểu (như dict) → ném `AudioBedError(WRONG_TYPE, 'constraints')`.
9. Thứ tự ưu tiên trong `build_audio_bed_result`: kiểm tra `request` type -> `validate_loudness_report` (`INPUT_NOT_READY`, `loudness_out_of_target`) -> `detect_substitutions` (`substitution_not_allowed`) -> tạo `cue_timings` và trả `AudioBedResult`.
10. Số liệu loudness trong test chỉ là fixture test-only, không phải chính sách hay hằng số hệ thống.
11. Không dùng bool cho integer (`type(v) is int` và `not isinstance(v, bool)`).

## coveredIds

- `CT-AUD-001`

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5), gồm đo và nghe âm thanh thật ở CP7-E-05
- CONV-E-07 mở binding E↔F CT-AUD-001
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`, binding, fixture.
- Chỉ dùng thư viện chuẩn Python (stdlib).
- Không gọi dịch vụ thật, không chạy FFmpeg, không đo âm thanh thật.
