# Báo cáo bằng chứng E-10

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `c695121600c8d1b73e9153cbd26dab92cf2f6b18`
- Nguồn quyền: IMPL-PLAN-E Auditor PASS, slice E-10 trong docs/implementation/e/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/voice/test_e10_timing_coverage.py -q -p no:cacheprovider` (chạy với khung stub chưa có logic ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `47 failed, 4 passed in 0.42s`
- Chi tiết các test FAILED tiêu biểu kèm thông điệp nguyên văn:
  - `FAILED tests/unit/voice/test_e10_timing_coverage.py::test_tokenize_folds_case_and_strips_edge_punctuation`: `AssertionError: assert () == ('breaking', 'news', 'tonight', 'well-known', 'don’t', 'stop')`
  - `FAILED tests/unit/voice/test_e10_timing_coverage.py::test_missing_policy_is_input_not_ready`: `Failed: DID NOT RAISE TimingPolicyRejected`
  - `FAILED tests/unit/voice/test_e10_timing_coverage.py::test_missing_rule_field_is_input_not_ready[revision]`: `Failed: DID NOT RAISE TimingPolicyRejected`
  - `FAILED tests/unit/voice/test_e10_timing_coverage.py::test_malformed_rule_is_value_error[changes0]`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/unit/voice/test_e10_timing_coverage.py::test_wrong_argument_types_are_type_errors`: `Failed: DID NOT RAISE TypeError`
  - `FAILED tests/unit/voice/test_e10_timing_coverage.py::test_exact_words_are_complete`: `AssertionError: assert CoverageReport('', 0, 0, (), (), False) == CoverageReport('test-only-en-1', 3, 3, (), (), True)`
  - `FAILED tests/unit/voice/test_e10_timing_coverage.py::test_any_missing_word_is_not_complete`: `assert (False, 0, 0) == (False, 3, 2)`
  - `FAILED tests/unit/voice/test_e10_timing_coverage.py::test_any_extra_word_is_detected`: `assert (False, 0) == (False, 3)`
  - `FAILED tests/unit/voice/test_e10_timing_coverage.py::test_wrong_order_is_not_complete`: `assert (False, 0) == (False, 2)`
  - `FAILED tests/unit/voice/test_e10_timing_coverage.py::test_case_and_punctuation_do_not_shift_coverage`: `AssertionError: assert False is True`
  - `FAILED tests/unit/voice/test_e10_timing_coverage.py::test_normalized_text_must_equal_token`: `assert (False, (), ()) == (False, (1,), (1,))`
  - `FAILED tests/unit/voice/test_e10_timing_coverage.py::test_gaps_cover_leading_between_and_trailing_above_tolerance`: `AssertionError: assert GapReport((), ()) == GapReport((AlignmentGap(0, 200), AlignmentGap(300, 400), AlignmentGap(900, 1000)), ())`
  - `FAILED tests/unit/voice/test_e10_timing_coverage.py::test_low_confidence_words_use_policy_threshold`: `assert () == (LowConfidenceWord(0, 0.59), LowConfidenceWord(3, 0))`
  - `FAILED tests/unit/voice/test_e10_timing_coverage.py::test_gap_report_without_policy_input_is_input_not_ready`: `Failed: DID NOT RAISE TimingPolicyRejected`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 4 test kiểm tra tính bất biến của policy, quét mã nguồn bằng AST không có hằng số numeric ngoại trừ 0 và 1, kiểm tra tham số policy không có default và cô lập import chỉ dùng stdlib được phép đã PASS ngay từ đầu (`test_policy_is_frozen_and_has_no_hidden_defaults`, `test_module_has_no_numeric_policy_constants`, `test_policy_parameter_has_no_default`, `test_module_imports_only_allowed_stdlib`). Tất cả 47 test thất bại đều là `AssertionError` hoặc `Failed: DID NOT RAISE` do khung stub ban đầu chưa cài logic xử lý.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/voice/test_e10_timing_coverage.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic domain hoàn chỉnh)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `51 passed in 0.06s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/voice/domain/timing_coverage.py`: Triển khai thuần domain xử lý phủ từ (word coverage), khoảng trống (alignment gaps) và từ độ tin cậy thấp (low confidence words) theo CT-SUB-001. Bao gồm dataclass frozen `TokenizationPolicy`, `CoverageReport`, `AlignmentGap`, `LowConfidenceWord`, `GapReport`, ngoại lệ `TimingPolicyRejected` với mã lỗi `INPUT_NOT_READY`, và 3 hàm xử lý chính `tokenize_script`, `check_coverage`, `build_gap_report`. Không có giá trị mặc định cho policy và không chứa hằng số 100 ms trong mã nguồn.
  - `tests/unit/voice/test_e10_timing_coverage.py`: Bộ 51 test case toàn diện kiểm thử tokenization theo Unicode form / casefold / edge strip, xác thực policy missing hoặc sai định dạng ném `INPUT_NOT_READY` / `ValueError`, kiểm thử đối soát coverage chính xác, thiếu, thừa, sai thứ tự hoặc lệch normalized_text, kiểm thử khoảng trống (leading, between, trailing, biên ngưỡng), kiểm thử lọc độ tin cậy, tương thích fixture payload E-09, và quét AST đảm bảo không tồn tại hằng số policy ẩn.
  - `docs/delivery-evidence/e-10/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.
- Ánh xạ phản ví dụ -> test:
  - Bỏ sót một từ vẫn complete: `test_any_missing_word_is_not_complete`
  - Từ dư không bị phát hiện: `test_any_extra_word_is_detected`
  - Hằng 100 ms: `test_gap_threshold_comes_only_from_policy`, `test_gap_equal_to_tolerance_is_not_reported`, `test_module_has_no_numeric_policy_constants`
  - Viết hoa hoặc dấu câu làm lệch coverage: `test_case_and_punctuation_do_not_shift_coverage`, `test_tokenize_folds_case_and_strips_edge_punctuation`

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/voice/test_e10_timing_coverage.py -q -p no:cacheprovider` | 0 | `51 passed in 0.06s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Mọi quy tắc tokenization, `gap_tolerance_ms`, `min_confidence` là trường của `TokenizationPolicy` mặc định `None`, giá trị chỉ ở fixture test-only (GIẢ ĐỊNH tiếng Anh theo IMPL-PLAN-E §7).
2. Lý do `INPUT_NOT_READY`: `missing_policy`, `missing_<trường>`, `missing_voice_duration_ms`.
3. Bỏ dấu câu hai đầu theo tiền tố Unicode category của policy (`edge_strip_categories`), token rỗng sau khi bỏ thì loại.
4. `normalized_text` `None` hoặc khác token chuẩn hóa thì tính là cả thiếu và dư (`missing_indices` và `extra_indices`).
5. So khớp bằng `difflib.SequenceMatcher`, `complete` khi chuỗi token trùng hoàn toàn và không rỗng, script rỗng không bao giờ `complete`.
6. Gap dùng so sánh lớn hơn tuyệt đối (`> tolerance`), đầu tính từ 0, cuối tính đến `voice_duration_ms`, không có từ thì một gap `0..voice_duration_ms` nếu vượt ngưỡng.
7. Confidence thấp dùng so sánh nhỏ hơn tuyệt đối (`< minimum`), từ không có confidence không bị chấm.
8. `AlignmentGap.to_payload()` trả dictionary `{start_ms, end_ms}` tương thích cấu trúc `alignment_gaps` của WordTiming E-09.
9. Giá trị policy sai kiểu hoặc ngoài miền giá trị hợp lệ ném `ValueError`.

## coveredIds

- `CT-SUB-001 (word coverage, gap, confidence)`

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- ROADMAP-OPEN-008 khi chốt giá trị policy thật
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`, binding, fixture.
- Chỉ dùng thư viện chuẩn Python (stdlib).
- Không gọi dịch vụ thật.
