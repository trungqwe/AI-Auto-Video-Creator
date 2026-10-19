# Báo cáo bằng chứng E-12

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `f54199a752a19475f567738a7c70eb108d583316`
- Nguồn quyền: IMPL-PLAN-E Auditor PASS, slice E-12 trong docs/implementation/e/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/voice/test_e12_language_evidence.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `33 failed, 2 passed in 0.36s`
- Chi tiết các dòng FAILED tiêu biểu từ bước 7:
  - `FAILED tests/unit/voice/test_e12_language_evidence.py::test_valid_inputs_build_frozen_evidence`: `AssertionError: assert False where False = isinstance(None, LanguageEvidence)`
  - `FAILED tests/unit/voice/test_e12_language_evidence.py::test_subtitle_text_hash_is_sha256_of_word_texts_in_order`: `AttributeError: 'NoneType' object has no attribute 'subtitle_text_hash'`
  - `FAILED tests/unit/voice/test_e12_language_evidence.py::test_evidence_ref_is_request_hash_of_bound_fields`: `AttributeError: 'NoneType' object has no attribute 'evidence_ref'`
  - `FAILED tests/unit/voice/test_e12_language_evidence.py::test_revision_mismatch_is_raised[voice_differs_from_timing]`: `Failed: DID NOT RAISE RevisionMismatchError`
  - `FAILED tests/unit/voice/test_e12_language_evidence.py::test_missing_or_invalid_locale_report_is_input_not_ready[None-missing_locale_report]`: `Failed: DID NOT RAISE LanguageEvidenceRejected`
  - `FAILED tests/unit/voice/test_e12_language_evidence.py::test_locale_is_compared_with_expected_language[en-en-False]`: `AttributeError: 'NoneType' object has no attribute 'voice_locale_reported'`
  - `FAILED tests/unit/voice/test_e12_language_evidence.py::test_word_without_text_is_input_not_ready[texts0]`: `Failed: DID NOT RAISE LanguageEvidenceRejected`
  - `FAILED tests/unit/voice/test_e12_language_evidence.py::test_blank_expected_language_is_input_not_ready`: `Failed: DID NOT RAISE LanguageEvidenceRejected`
  - `FAILED tests/unit/voice/test_e12_language_evidence.py::test_boundary_errors_and_mapping_inputs`: `Failed: DID NOT RAISE VoiceTrackValidationError`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 2 test quét import và cấu trúc (`test_evidence_never_declares_english_valid`, `test_module_imports_only_allowed_modules`) đã PASS ngay từ đầu. Tất cả 33 test thất bại đều là `AssertionError`, `AttributeError` hoặc `DID NOT RAISE` do khung skeleton chưa cài logic xử lý.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/voice/test_e12_language_evidence.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic validator)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `35 passed in 0.07s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/voice/domain/language_evidence.py`: Cài đặt `LanguageEvidence` frozen bound với 7 trường revision và `evidence_ref` (`request_hash`), hàm `build_language_evidence` kiểm tra ranh giới, phát hiện `revision_mismatch`, kiểm tra `locale_report` vắng/sai kiểu, so khớp locale không phân biệt hoa thường và hỗ trợ prefix phụ/chính, tạo finding `language_mismatch` mà vẫn trả evidence khi khác biệt ngôn ngữ, và tuyệt đối không tự tuyên bố output hợp lệ.
  - `tests/unit/voice/test_e12_language_evidence.py`: Bộ kiểm thử toàn diện 35 test cases kiểm tra tính frozen, hash subtitle sha256 theo thứ tự từ, request_hash của 7 trường, tính duy nhất của `evidence_ref` khi đổi từng trường, phát hiện `revision_mismatch` với danh sách fields, độ ưu tiên `revision_mismatch` > `locale_mismatch`, kiểm tra thiếu/sai kiểu `locale_report`, so sánh `expected_language` với reported locale, tạo finding `language_mismatch`, kiểm tra vắng text từ hoặc `expected_language` rỗng, lỗi biên mapping/object và kiểm soát ranh giới import module.
  - `docs/delivery-evidence/e-12/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/voice/test_e12_language_evidence.py -q -p no:cacheprovider` | 0 | `35 passed in 0.07s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `subtitle_text_hash` = sha256 UTF-8 của text các từ nối bằng đúng một dấu cách, giữ nguyên chữ, theo thứ tự; từ thiếu hoặc rỗng text → `INPUT_NOT_READY` reason `missing_word_text`.
2. `locale_report` là mapping có khóa `voice_locale_reported` do adapter điền từ output provider (GIẢ ĐỊNH, chưa có binding, mở qua CONV-E-07); thiếu hoặc rỗng → `INPUT_NOT_READY` reason `missing_locale_report`, sai kiểu → reason `invalid_locale_report`.
3. `evidence_ref` = `request_hash` của 7 trường (`script_version_id`, `script_fingerprint`, `voice_hash`, `voice_locale_reported`, `subtitle_text_hash`, `timing_artifact_ref`, `expected_language`), không gồm findings.
4. `revision_mismatch` kiểm thêm `script_version_id` (chặt hơn spec, fail-closed) và liệt kê mọi trường lệch trong `.fields`; `revision_mismatch` được kiểm trước `locale_report`.
5. So khớp locale: chuẩn hóa strip, '_'→'-', casefold; khớp khi hai tag bằng nhau hoặc `expected_language` không có vùng và bằng subtag chính của locale báo cáo (en khớp en-US, en-US không khớp en-GB); lệch thì tạo finding `language_mismatch` mà vẫn trả evidence.
6. `expected_language` rỗng → `INPUT_NOT_READY` reason `missing_expected_language`.
7. E không có trường hay hằng tuyên bố hợp lệ ngôn ngữ; F kiểm `ENGLISH_OUTPUT_VALID`.

## Ánh xạ phản ví dụ

- Phản ví dụ 1: "Evidence tin expected_language khi locale báo khác" -> `test_locale_is_compared_with_expected_language` và `test_locale_mismatch_still_creates_evidence_with_finding`.
- Phản ví dụ 2: "evidence cho timing khớp script nhưng voice khác" -> `test_revision_mismatch_is_raised[timing_voice_differs]` và `test_revision_mismatch_is_raised[voice_differs_from_timing]`.
- Phản ví dụ 3: "evidence tự ghi English valid" -> `test_evidence_never_declares_english_valid`.

## coveredIds

- `TST-QC-INV-019 (phía E)`
- `CT-RND-002 language_validation_refs`

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- Mở binding locale_report qua CONV-E-07
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`, binding, fixture.
- Chỉ stdlib và import controlplane.application đã có.
- Không gọi dịch vụ thật.
