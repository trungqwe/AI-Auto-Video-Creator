# Báo cáo bằng chứng D-12

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `773af60b0f148d6212f261abeb57c71fb5bde4b7`
- Nguồn quyền: IMPL-PLAN-D Auditor PASS, slice D-12 trong docs/implementation/d/slices.md, ủy quyền AI_SETUP.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d12_output_metadata.py -q -p no:cacheprovider` (chạy với skeleton chưa có validation)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `42 failed, 13 passed, 2 subtests passed in 0.17s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn:
  - `FAILED tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_duplicate_hashtags_ignoring_case_are_rejected`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(count=0) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_hashtag_count_must_be_three_or_four`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(count=1) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_hashtag_count_must_be_three_or_four`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(count=2) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_hashtag_count_must_be_three_or_four`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(count=5) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_hashtag_count_must_be_three_or_four`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(count=6) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_hashtag_count_must_be_three_or_four`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(bad='Metro') tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_hashtag_shape_is_validated`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(bad='#') tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_hashtag_shape_is_validated`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(bad='') tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_hashtag_shape_is_validated`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(bad='#Two Words') tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_hashtag_shape_is_validated`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(bad='#a#b') tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_hashtag_shape_is_validated`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(bad=7) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_hashtag_shape_is_validated`: `AssertionError: OutputMetadataError not raised`
  - `FAILED tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_hashtags_must_be_a_tuple`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(language='vi') tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_language_must_be_english`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(language='fr') tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_language_must_be_english`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(language='') tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_language_must_be_english`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(revision=0) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_metadata_revision_must_be_positive_int`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(revision=-1) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_metadata_revision_must_be_positive_int`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(revision=True) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_metadata_revision_must_be_positive_int`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(revision='1') tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_metadata_revision_must_be_positive_int`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(revision=1.0) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_metadata_revision_must_be_positive_int`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(override={'source_job_ref': ''}) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_source_refs_are_required`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(override={'source_output_refs': ()}) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_source_refs_are_required`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(override={'source_output_refs': ['variant-validation-001']}) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_source_refs_are_required`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(override={'source_output_refs': ('',)}) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_source_refs_are_required`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(field='title', bad='') tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_title_and_caption_must_be_non_blank_strings`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(field='title', bad='   ') tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_title_and_caption_must_be_non_blank_strings`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(field='title', bad=None) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_title_and_caption_must_be_non_blank_strings`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(field='caption', bad='') tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_title_and_caption_must_be_non_blank_strings`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(field='caption', bad='   ') tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_title_and_caption_must_be_non_blank_strings`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(field='caption', bad=None) tests/unit/creative/test_d12_output_metadata.py::OutputMetadataFieldTests::test_title_and_caption_must_be_non_blank_strings`: `AssertionError: OutputMetadataError not raised`
  - `FAILED tests/unit/creative/test_d12_output_metadata.py::FilenameSafeRepresentationTests::test_display_representation_is_unchanged_after_sanitize`: `AssertionError: unexpectedly identical: OutputMetadata(...)`
  - `FAILED tests/unit/creative/test_d12_output_metadata.py::FilenameSafeRepresentationTests::test_filename_safe_comes_only_from_port`: `AssertionError: Lists differ: [] != ['Breaking: City Opens New Metro Line?', ...]`
  - `SUBFAILED(override={'title': ''}) tests/unit/creative/test_d12_output_metadata.py::FilenameSafeRepresentationTests::test_filename_safe_representation_validates_fields`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(override={'caption': ''}) tests/unit/creative/test_d12_output_metadata.py::FilenameSafeRepresentationTests::test_filename_safe_representation_validates_fields`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(override={'hashtags': ['c']}) tests/unit/creative/test_d12_output_metadata.py::FilenameSafeRepresentationTests::test_filename_safe_representation_validates_fields`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(override={'hashtags': ('',)}) tests/unit/creative/test_d12_output_metadata.py::FilenameSafeRepresentationTests::test_filename_safe_representation_validates_fields`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(result='') tests/unit/creative/test_d12_output_metadata.py::FilenameSafeRepresentationTests::test_invalid_port_output_is_rejected`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(result=None) tests/unit/creative/test_d12_output_metadata.py::FilenameSafeRepresentationTests::test_invalid_port_output_is_rejected`: `AssertionError: OutputMetadataError not raised`
  - `SUBFAILED(result=42) tests/unit/creative/test_d12_output_metadata.py::FilenameSafeRepresentationTests::test_invalid_port_output_is_rejected`: `AssertionError: OutputMetadataError not raised`
  - `FAILED tests/unit/creative/test_d12_output_metadata.py::FilenameSafeRepresentationTests::test_metadata_rejects_non_representation_filename_safe`: `AssertionError: OutputMetadataError not raised`
  - `FAILED tests/unit/creative/test_d12_output_metadata.py::FilenameSafeRepresentationTests::test_port_output_is_not_post_processed_by_d`: `AssertionError: unexpectedly None`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection nào (RED sử dụng skeleton chưa có validation, quyết định D8).

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d12_output_metadata.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `19 passed, 38 subtests passed in 0.03s`

## Thay đổi

- Ba tệp thuộc owned paths:
  - `src/creative/domain/output_metadata.py`: triển khai value object `OutputMetadata` (frozen dataclass), `FilenameSafeRepresentation`, port `FilenameSanitizerPort` (Protocol) và ngoại lệ `OutputMetadataError`.
  - `tests/unit/creative/test_d12_output_metadata.py`: bộ kiểm thử đơn vị gồm 19 test (38 subtests) bao phủ toàn bộ các trường, validation, tính bất biến, và ranh giới port.
  - `docs/delivery-evidence/d-12/report.md`: báo cáo bằng chứng chuyển giao.
- Ánh xạ phản ví dụ sang test:
  - Chấp nhận 5 hoặc 2 hashtag: bị loại trừ bởi `test_hashtag_count_must_be_three_or_four` (ném `OutputMetadataError` cho 0, 1, 2, 5, 6 hashtag; chấp nhận 3 và 4).
  - Mất bản hiển thị gốc: bị loại trừ bởi `test_display_representation_is_unchanged_after_sanitize` (bản gốc không đổi và có `filename_safe` là None, bản sao mới giữ nguyên title, caption, hashtags ban đầu).
  - Phân hệ D tự đặt quy tắc filename: bị loại trừ bởi `test_port_output_is_not_post_processed_by_d` (truyền nguyên văn kết quả port trả về) và `test_module_defines_no_filename_rules_of_its_own` (AST quét module nguồn xác nhận không import module ngoài `dataclasses`/`typing` và không gọi các phương thức biến đổi chuỗi `translate`, `maketrans`, `replace`, `sub`, `normalize`, `encode`).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/creative/test_d12_output_metadata.py -q -p no:cacheprovider` | 0 | 19 passed, 38 subtests passed in 0.03s |
| 2 | `python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider` | 0 | 9 passed, 46 subtests passed in 0.04s |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Language đúng `'en'` (GIẢ ĐỊNH, không suy luận ngôn ngữ từ nội dung).
2. Hashtag bắt đầu bằng `'#'`, tối thiểu 2 ký tự, không chứa khoảng trắng, không chứa `'#'` thứ hai, không trùng lặp không phân biệt hoa thường (GIẢ ĐỊNH).
3. `source_output_refs` là tuple chuỗi không rỗng, tối thiểu một ref (GIẢ ĐỊNH).
4. `filename_safe` gồm title, caption, hashtags theo CT-AI-009.
5. Phân hệ D chỉ kiểm tra giá trị port trả về là chuỗi không rỗng, không tự áp đặt quy tắc filename riêng.
6. Khai báo docstring `coveredIds: CT-AI-009` trong module và test theo quy định.

## Port D-local tạm

- `FilenameSanitizerPort` là port tạm của phân hệ D vì storage contract của phân hệ I chưa có binding (CONV-D-07).
- Kiểm thử dùng test double `FakeFilenameSanitizer` và `FixedFilenameSanitizer`, hiện chưa có wiring thật vào infrastructure hay storage adapter của I.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`.
- Không thêm thư viện ngoài (chỉ dùng Python stdlib: `dataclasses`, `typing`).
- Không gọi dịch vụ thật.
