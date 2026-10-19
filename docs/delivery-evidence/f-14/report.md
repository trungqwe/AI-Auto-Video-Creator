# Báo cáo bằng chứng F-14

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `0591304d66208f1b9c445a437d793b1c1bb7210b`
- Nguồn quyền: IMPL-PLAN-F Auditor PASS, slice F-14 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovider` (chạy trên stub trung tính ở bước 8)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `94 failed, 15 passed, 10 subtests passed in 1.47s`
- Các dòng FAILED tiêu biểu:
  1. `VisualHookTests.test_passes_inside_hook_range`: `AssertionError: <GateStatus.NOT_EVALUATED: 'not_evaluated'> is not <GateStatus.PASSED: 'passed'>`
  2. `VisualHookTests.test_similarity_below_threshold_fails`: `AssertionError: <GateStatus.NOT_EVALUATED: 'not_evaluated'> is not <GateStatus.FAILED: 'failed'>`
  3. `VisualHookTests.test_missing_inputs_not_evaluated`: `AssertionError: False is not true : STUB-NEUTRAL`
  4. `ThumbnailTests.test_asset_mismatch_fails`: `AssertionError: <GateStatus.NOT_EVALUATED: 'not_evaluated'> is not <GateStatus.FAILED: 'failed'>`
  5. `EvaluateContentGatesTests.test_returns_seven_results_in_gate_order_and_inspects_once`: `AssertionError: Tuples differ: () != (<GateName.VISUAL_HOOK_PRESENT: 'VISUAL_HOOK_PRESENT'>, ...)`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED chạy hoàn toàn trên stub trung tính.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `52 passed, 67 subtests passed in 0.12s`

## Thay đổi

- `src/render/ports/output_inspector.py`: Protocol `OutputInspectorPort.inspect(output_ref, package)` và 10 dataclass frozen kw_only cho evidence (`VisualHookEvidence`, `AudioHookEvidence`, `ThumbnailEvidence`, `SubtitleEvidence`, `KaraokeWordObservation`, `KaraokeEvidence`, `LanguageEvidence`, `DisclosureObservation`, `DisclosureEvidence`, `OutputEvidence`).
- `src/render/domain/content_gates.py`: 7 hàm kiểm tra gate nội dung (`check_visual_hook_present`, `check_audio_hook_present`, `check_thumbnail_present`, `check_subtitle_burned_in`, `check_karaoke_timing_valid`, `check_english_output_valid`, `check_inference_disclosure_present`), hàm gom `evaluate_content_gates`, DTO `ExpectedLanguageRevisions`, cùng các helper nội bộ; không dùng hằng số cứng và không chứa chuỗi 'en' hay marker stub.
- `tests/unit/render/test_f14_content_gates.py`: 10 lớp kiểm thử với 52 test methods (67 subtests) bao quát 7 gate nội dung, đối tượng giả `FakeInspector`, kiểm thử hình dạng evidence frozen/kw_only và kiểm tra vệ sinh mã nguồn (không hằng số ngưỡng, không import ngoài slice).
- `docs/delivery-evidence/f-14/report.md`: báo cáo bằng chứng này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovider` | 0 | 52 passed, 67 subtests passed |
| 2 | `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | 12 passed, 75 subtests passed |
| 3 | `python -m pytest tests/unit/render/test_f12_quality_report.py -q -p no:cacheprovider` | 0 | 45 passed, 129 subtests passed |
| 4 | `python -c "import pathlib; assert 'STUB-' not in pathlib.Path('src/render/domain/content_gates.py').read_text(encoding='utf-8')"` | 0 | Sạch mọi marker stub |
| 5 | `git diff --check` | 0 | Không có lỗi định dạng hay khoảng trắng thừa |

## Quyết định mặc định (D8)

1. Ngưỡng đọc từ `QualityPolicy.thresholds` theo từng gate (`min_similarity`, `min_level_db`, `min_frames_with_text`, `tolerance_ms`, `required_language`); thiếu ngưỡng hay đầu vào -> `not_evaluated` kèm lý do bắt đầu bằng `INPUT_NOT_READY`.
2. Evidence tổng là `None` -> `not_evaluated` kèm `INPUT_NOT_READY:evidence`; trường evidence thành phần là `None` -> `failed` (riêng karaoke thiếu quan sát hoàn toàn -> `not_evaluated` kèm `karaoke_observation_missing`, quan sát thiếu một phần hoặc lệch quá `tolerance_ms` -> `failed`).
3. Visual hook và audio hook phải nằm trọn trong `hook_time_range` (`start_ms >= hook.start_ms` và `end_ms <= hook.end_ms`) (GIẢ ĐỊNH cho visual, vì spec chỉ nêu rõ ràng cho audio).
4. Thumbnail: thời điểm `time_ms` nằm trong `hook_time_range` của package (hai đầu bao gồm, không hằng 0–3 giây) và `asset_ref` phải bằng `hook_placement.thumbnail_ref`.
5. Locale khớp theo quy ước F-07 (chuẩn hoá `_` thành `-`, casefold, `required_language` không có vùng thì khớp subtag chính); `declared_language` bị bỏ qua không được dùng làm bằng chứng; `script_fingerprint`, `voice_hash`, `subtitle_text_hash` kỳ vọng do caller truyền qua `ExpectedLanguageRevisions` vì `RenderPackageRecord` không mang các trường này.
6. Segment có `segment_id` và `claim_mode` là hình dạng F-local (theo `ScriptSegment` của phân hệ D, phân hệ F không import D).

## Ánh xạ phản ví dụ

- Thumbnail ngoài vùng hook vẫn pass: `ThumbnailTests.test_not_hardcoded_to_first_three_seconds` (loại trừ: time_ms 1000 nằm trong 0–3s nhưng ngoài hook 2000–5000ms bị FAILED `thumbnail_outside_hook_range`).
- Evidence voice cũ vẫn pass: `EnglishOutputTests.test_stale_revision_fails` (loại trừ: voice_hash khác kỳ vọng bị FAILED `language_evidence_revision_mismatch:voice_hash`).
- Chỉ language=en tự khai vẫn pass: `EnglishOutputTests.test_self_declared_language_is_not_evidence` (loại trừ: thiếu locale thực tế mà chỉ có declared_language='en' bị FAILED).
- Segment suy luận không disclosure vẫn pass: `InferenceDisclosureTests.test_inference_without_disclosure_fails`, `InferenceDisclosureTests.test_creative_hypothesis_requires_disclosure`, `InferenceDisclosureTests.test_every_applicable_segment_needs_disclosure` (loại trừ: segment inference/creative_hypothesis thiếu observation hiển thị bị FAILED `disclosure_missing`).
- Karaoke lệch quá tolerance_ms vẫn pass: `KaraokeTests.test_deviation_over_tolerance_fails` (loại trừ: độ lệch 81ms vượt ngưỡng 80ms bị FAILED `karaoke_timing_out_of_tolerance`).

## coveredIds

- `CT-QC-001`
- `CT-QC-002`
- `TST-QC-INV-019`

## Danh sách chờ user (pendingUserCheckpoint)

- Ngưỡng policy thật cho hook/âm thanh/karaoke.
- Đo thật ở CP7-F-01 và CP7-F-02.
- USER-CKPT-D9-D10.
- CP7 tài nguyên thật (D5).
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture.
- Không sửa quality_report.py.
- Chỉ stdlib, không gọi dịch vụ thật.
