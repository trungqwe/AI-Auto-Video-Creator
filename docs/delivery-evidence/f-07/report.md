# Báo cáo bằng chứng F-07

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `a461b76e086b8d41ce4f0607da1e2c2460d3c90f`
- Nguồn quyền: IMPL-PLAN-F Auditor PASS, slice F-07 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f07_preconditions_artifacts_language.py -q -p no:cacheprovider` (chạy trên khung module khi các hàm check_* còn trả [])
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `79 failed, 18 passed in 0.79s`
- Chi tiết các dòng FAILED tiêu biểu từ bước 10:
  - `FAILED tests/unit/render/test_f07_preconditions_artifacts_language.py::test_state_other_than_verified_is_not_verified[DECLARED]`: `AssertionError: assert [] == [Finding(condition=7, code='artifact_not_verified', field='input_artifacts[0]')]`
  - `FAILED tests/unit/render/test_f07_preconditions_artifacts_language.py::test_missing_entries_report_each_artifact_in_order`: `AssertionError: assert [] == [Finding(condition=7, code='artifact_not_verified', field='input_artifacts[0]'), ...]`
  - `FAILED tests/unit/render/test_f07_preconditions_artifacts_language.py::test_hash_mismatch`: `AssertionError: assert [] == [Finding(condition=7, code='artifact_hash_mismatch', field='input_artifacts[2].sha256')]`
  - `FAILED tests/unit/render/test_f07_preconditions_artifacts_language.py::test_size_mismatch`: `AssertionError: assert [] == [Finding(condition=7, code='artifact_size_mismatch', field='input_artifacts[2].size_bytes')]`
  - `FAILED tests/unit/render/test_f07_preconditions_artifacts_language.py::test_output_path_outside_staging_root_is_rejected[..\\x]`: `AssertionError: assert [] == [Finding(condition=8, code='output_path_outside_staging_root', field='output_path_ref')]`
  - `FAILED tests/unit/render/test_f07_preconditions_artifacts_language.py::test_empty_refs_is_evidence_missing`: `AssertionError: assert [] == [Finding(condition=5, code='language_evidence_missing', field='language_validation_refs')]`
  - `FAILED tests/unit/render/test_f07_preconditions_artifacts_language.py::test_missing_filter_and_encoder_are_reported_in_order`: `AssertionError: assert [] == [Finding(condition=9, code='tool_capability_incompatible', field='compatibility_requirements.required_filters'), Finding(condition=9, code='tool_capability_incompatible', field='compatibility_requirements.required_encoders')]`
  - `FAILED tests/unit/render/test_f07_preconditions_artifacts_language.py::test_capability_none_or_wrong_type_is_input_not_ready[None]`: `AssertionError: assert [] == [Finding(condition=9, code='INPUT_NOT_READY', field='capability')]`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 18 test passed gồm các kiểm tra DTO frozen, cấu trúc Finding, import ranh giới và trường hợp hợp lệ. Tất cả 79 test thất bại đều là AssertionError do khung module chưa cài đặt logic nghiệp vụ.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f07_preconditions_artifacts_language.py -q -p no:cacheprovider` (chạy sau khi hoàn tất cài đặt logic nghiệp vụ)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `97 passed in 0.13s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/render/domain/preconditions_artifacts.py`: Cài đặt miền nghiệp vụ tiền điều kiện cho artifact verify, output path, bằng chứng ngôn ngữ và tương thích công cụ theo CT-RND-003 số 5, 7, 8, 9, bao gồm:
    - Hằng số mã lỗi chuẩn và điều kiện: `INPUT_NOT_READY`, `ARTIFACT_NOT_VERIFIED`, `ARTIFACT_HASH_MISMATCH`, `ARTIFACT_SIZE_MISMATCH`, `REQUIRED_ARTIFACT_NOT_IN_INPUTS`, `OUTPUT_PATH_NOT_ISSUED`, `OUTPUT_PATH_OUTSIDE_STAGING_ROOT`, `LANGUAGE_EVIDENCE_MISSING`, `LANGUAGE_EVIDENCE_UNRESOLVED`, `LANGUAGE_EVIDENCE_REVISION_MISMATCH`, `LANGUAGE_MISMATCH`, `TOOL_CAPABILITY_INCOMPATIBLE`, `CONDITION_LANGUAGE` (5), `CONDITION_ARTIFACTS` (7), `CONDITION_OUTPUT_PATH` (8), `CONDITION_TOOLS` (9).
    - Các DTO frozen: `Finding(condition, code, field)`, `VerifiedArtifact(sha256, size_bytes, state)`, `IssuedOutputPath(staging_root, path)`, `LanguageEvidenceView`, `LanguageEvidencePolicy`, `ToolCapability(filters, encoders)`.
    - `check_artifacts_verified`: Xác minh mọi input artifact có state `ArtifactLocationState.VERIFIED` khớp hash và size; kiểm tra `voice_artifact_ref` và `word_timing_ref` nằm trong danh sách inputs.
    - `check_output_path`: Kiểm tra đường dẫn output do I cấp có nằm trong staging root hay không bằng chuẩn hóa từ vựng với `PureWindowsPath`, từ chối `..`, khác ổ đĩa, UNC, thiết bị reserved, ký tự điều khiển, URI protocol `://` và đường dẫn trùng staging root.
    - `check_language_evidence`: Xác minh bằng chứng ngôn ngữ được resolve, ràng buộc chính xác với revision siêu dữ liệu và mã băm voice/script/subtitle, đối chiếu locale với required_language (không dùng trường `language` tự khai).
    - `check_preset_tool_compat`: Đối chiếu các bộ lọc và bộ mã hóa bắt buộc (`required_filters`, `required_encoders`) của preset với khả năng của công cụ (`ToolCapability`).
  - `tests/unit/render/test_f07_preconditions_artifacts_language.py`: Bộ kiểm thử toàn diện 97 test cases bao phủ đầy đủ các nhóm tiền điều kiện artifact verification, lexical output path trong staging root, bằng chứng ngôn ngữ tiếng Anh/locale, tương thích công cụ preset, kiểm tra ranh giới import (chỉ stdlib và controlplane.domain.statemachine) và khai báo coveredIds.
  - `docs/delivery-evidence/f-07/report.md`: Báo cáo bằng chứng thực thi gói F-07.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/render/test_f07_preconditions_artifacts_language.py -q -p no:cacheprovider` | 0 | `97 passed in 0.13s` |
| 2 | `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | `12 passed, 75 subtests passed in 0.11s` |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `Finding(condition, code, field)` tương đương F-06, condition là số điều kiện CT-RND-003 (5, 7, 8, 9).
2. DTO F-local `VerifiedArtifact`, `IssuedOutputPath(staging_root, path)`, `LanguageEvidenceView`, `LanguageEvidencePolicy`, `ToolCapability(filters, encoders)` là GIẢ ĐỊNH, mở qua CONV-F-07 và CONV-F-11; policy mang `required_language` cùng `script_fingerprint`, `voice_hash`, `subtitle_text_hash` kỳ vọng vì `RenderPackage` chỉ giữ ref.
3. Đầu vào None (`verified`, `issued_paths`, `evidence_by_ref`, `policy`, `capability`) hoặc policy/requirement sai dạng cho đúng một finding `INPUT_NOT_READY`, fail-closed.
4. Artifact không `VERIFIED` chỉ báo `artifact_not_verified`, không so hash/size.
5. Path chỉ chuẩn hóa từ vựng bằng `PureWindowsPath`, symlink thật thuộc I và CP7; đường dẫn trùng đúng staging root bị từ chối; ký tự `<>:|?*` trong thành phần cũng bị từ chối.
6. Locale: `required_language` không có vùng khớp primary subtag của locale báo cáo; có vùng thì phải bằng nhau (không phân biệt hoa thường, `_` tương đương `-`).
7. `compatibility_requirements` thiếu khóa nghĩa là không yêu cầu (GIẢ ĐỊNH về `required_filters`/`required_encoders`).

## Ánh xạ phản ví dụ

- `AVAILABLE_UNVERIFIED` → `test_state_other_than_verified_is_not_verified`
- `..\x` → `test_output_path_outside_staging_root_is_rejected`
- Metadata `language=en` tự khai → `test_self_declared_language_is_not_evidence`
- Evidence của voice cũ → `test_evidence_of_old_voice_is_rejected_after_voice_changes` và `test_stale_revision_is_mismatch`
- Thiếu policy → `test_policy_none_is_input_not_ready_even_when_refs_empty`

## coveredIds

- `TST-INT-INV-008 (phía F)`
- `TST-QC-INV-019 (phía F)`
- `TST-SEC-INV-020 (phía F)`
- `CT-RND-003 số 5, 7, 8, 9`
- `CT-RND-006 (phía F)`

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- Mở binding qua CONV-F-07 cho staging root, output path, language evidence
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture.
- Chỉ stdlib và controlplane.domain.statemachine.
- Không gọi dịch vụ thật.
