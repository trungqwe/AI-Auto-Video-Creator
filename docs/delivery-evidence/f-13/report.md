# Báo cáo bằng chứng F-13

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `0591304d66208f1b9c445a437d793b1c1bb7210b`
- Nguồn quyền: IMPL-PLAN-F Auditor PASS, slice F-13 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f13_technical_gates.py -q -p no:cacheprovider` (chạy trên stub trung tính ở bước 4)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `96 failed, 16 passed, 10 subtests passed in 0.92s`
- Các dòng FAILED tiêu biểu:
  1. `FilePlayableTests.test_missing_probe_result_or_undecodable_output_fails`: `AssertionError: <GateStatus.PASSED: 'passed'> is not <GateStatus.FAILED: 'failed'>`
  2. `FilePlayableTests.test_non_measurement_object_is_a_type_error`: `AssertionError: TypeError not raised`
  3. `DurationRangeTests.test_inclusive_boundaries`: `AssertionError: <GateStatus.PASSED: 'passed'> is not <GateStatus.FAILED: 'failed'>`
  4. `OutputProfileTests.test_landscape_output_fails_for_portrait_profile`: `AssertionError: <GateStatus.PASSED: 'passed'> is not <GateStatus.FAILED: 'failed'>`
  5. `EvaluateTechnicalGatesTests.test_unreadable_probe_result_fails_every_measured_gate`: `AssertionError: Lists differ: [<GateStatus.PASSED: 'passed'>, ...] != [<GateStatus.FAILED: 'failed'>, ...]`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED chạy trên stub trung tính ở bước 4.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f13_technical_gates.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `38 passed, 99 subtests passed in 0.10s`

## Thay đổi

- `src/render/ports/output_probe.py`: OutputMeasurements frozen và OutputProbePort Protocol.
- `src/render/domain/technical_gates.py`: GateName, GateStatus, GateResult khai báo tương đương F-12, 4 hàm gate và evaluate_technical_gates.
- `tests/unit/render/test_f13_technical_gates.py`: 10 lớp test với 38 test methods và 99 subtests.
- `docs/delivery-evidence/f-13/report.md`: báo cáo bằng chứng này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/render/test_f13_technical_gates.py -q -p no:cacheprovider` | 0 | 38 passed, 99 subtests passed in 0.10s |
| 2 | `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | 12 passed, 75 subtests passed in 0.10s |
| 3 | `python -c "import pathlib; assert 'STUB-' not in pathlib.Path('src/render/domain/technical_gates.py').read_text(encoding='utf-8')"` | 0 | Sạch mọi marker stub |
| 4 | `git diff --check` | 0 | Không có khoảng trắng thừa hay lỗi định dạng |

## Quyết định mặc định (D8)

1. Policy là mapping phẳng có `duration_range_ms` [min, max] số nguyên hai đầu bao gồm và `min_voice_level`; việc ánh xạ từ `QualityPolicy` của F-12 do caller làm (GIẢ ĐỊNH).
2. Ngưỡng được kiểm trước số đo: ngưỡng thiếu hoặc sai dạng → `not_evaluated` kèm `INPUT_NOT_READY`, số đo thiếu hoặc sai → `failed`.
3. `FILE_PLAYABLE` yêu cầu `decodable` là `True` và đủ `duration_ms`, `width`, `height`, `fps`, `video_codec`, `container`.
4. `audio_level` cùng đơn vị với `min_voice_level` và phải lớn hơn nghiêm ngặt (GIẢ ĐỊNH).
5. `expected_profile` bắt buộc đủ 6 khóa `container`, `video_codec`, `audio_codec`, `width`, `height`, `fps`; so chuỗi không phân biệt hoa thường, `fps` so bằng `math.isclose`.
6. Thứ tự gate `FILE_PLAYABLE`, `DURATION_RANGE`, `VOICE_AUDIBLE`, `OUTPUT_PROFILE_VALID` khớp thứ tự F-12.
7. Ngoại lệ do probe ném ra không bị bắt trong domain.

## Ánh xạ phản ví dụ

- Video 70001 ms pass → `test_inclusive_boundaries` và `test_too_long_video_fails_only_the_duration_gate`.
- Output ngang pass cho profile dọc → `test_landscape_output_fails_for_portrait_profile`.
- Hằng 61000 đặt cứng trong mã → `test_threshold_comes_from_the_policy` và `test_modules_hold_no_threshold_or_profile_values`.
- Số đo thiếu mà gate pass → `test_each_missing_core_measurement_fails`, `test_missing_measurements_fail`, `test_unreadable_probe_result_fails_every_measured_gate`.

## coveredIds

- `CT-QC-001`: FILE_PLAYABLE, DURATION_RANGE, OUTPUT_PROFILE_VALID, VOICE_AUDIBLE; acceptance §8 mục 5.

## Danh sách chờ user (pendingUserCheckpoint)

- Khoảng 61–70 giây hai đầu bao gồm là GIẢ ĐỊNH (plan.md).
- Đơn vị và ngưỡng `audio_level`.
- `USER-CKPT-D9-D10`.
- CP7 ffprobe và byte thật (D5).
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture.
- Chỉ stdlib, không gọi dịch vụ thật.
