# Báo cáo bằng chứng E-04

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: e336d92b9146b73d42da5f0346a55eef6c8d4386
- Nguồn quyền: IMPL-PLAN-E Auditor PASS, slice E-04 trong docs/implementation/e/slices.md (CT-PROC-004).

## RED

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e04_media_analysis.py -q -p no:cacheprovider
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 66 failed, 20 passed in 0.79s
- Chi tiết các test FAILED kèm thông điệp chính:
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_result_is_frozen_and_normalized: AssertionError: assert 'semantic_tags' is <AnalysisKind.SEMANTIC_TAGS: 'semantic_tags'>
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_unit_interval_rejects_out_of_range[...]: Failed: DID NOT RAISE ProcessingContractError (18 ca out of range cho confidence và coverage: 1.5, -0.1, 1.0000001, 2, -1, nan, inf, -inf, 10**400)
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_unit_interval_rejects_wrong_type[...]: Failed: DID NOT RAISE ProcessingContractError (10 ca wrong type: True, False, '0.5', [0.5], {'v': 0.5})
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_none_field_is_missing_required[...]: Failed: DID NOT RAISE ProcessingContractError (9 ca cho đủ 9 trường ANALYSIS_FIELDS)
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_from_mapping_missing_field[...]: Failed: DID NOT RAISE ProcessingContractError (9 ca cho đủ 9 trường ANALYSIS_FIELDS)
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_from_mapping_builds_result_and_rejects_non_mapping: Failed: DID NOT RAISE ProcessingContractError
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_text_fields_reject_blank_and_wrong_type[...]: Failed: DID NOT RAISE ProcessingContractError (4 ca cho analysis_id, model, model_version, spec_revision)
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_kind_rejects_unknown_and_wrong_type: Failed: DID NOT RAISE ProcessingContractError
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_input_ref_rules: Failed: DID NOT RAISE ProcessingContractError
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_failure_flags_rules: Failed: DID NOT RAISE ProcessingContractError
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_append_first_result_creates_revision_one: AssertionError: assert None == AnalysisRevision(revision=1, ...) (h1.get('an-1') trả None)
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_same_input_model_version_spec_returns_old_history: AssertionError: assert h2 is h1
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_new_model_version_or_spec_adds_revision_and_keeps_old[...]: AssertionError: assert None is AnalysisRevision(revision=1, ...) (3 ca h2.get('an-1') trả None)
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_history_never_shrinks_and_keeps_prefix: AssertionError: assert ['an-1', 'an-2', 'an-3', 'an-4', 'an-5', 'an-6'] == ['an-1', 'an-2', 'an-4', 'an-6']
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_revisions_are_isolated_per_input_hash_and_kind: AssertionError: assert [1, 2, 3, 4, 5] == [1, 2, 1, 1, 1]
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_returning_to_earlier_model_does_not_create_duplicate: AssertionError: assert h.append(...) is h
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_analysis_id_reuse_is_rejected_without_overwrite: Failed: DID NOT RAISE ProcessingContractError
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_append_rejects_non_result: Failed: DID NOT RAISE ProcessingContractError
  - FAILED tests/unit/voice/test_e04_media_analysis.py::test_revision_and_history_constructor_validation: Failed: DID NOT RAISE ProcessingContractError
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection nào (RED là sai oracle trên khung tối thiểu).

## Thay đổi

- 3 tệp owned:
  - src/voice/domain/media_analysis.py
  - tests/unit/voice/test_e04_media_analysis.py
  - docs/delivery-evidence/e-04/report.md
- Danh mục API đã triển khai trong src/voice/domain/media_analysis.py:
  - AnalysisKind: enum.StrEnum (5 giá trị: keyframes_shots, transcript_ocr, entities_faces_objects, motion_scene_audio_energy, semantic_tags)
  - AnalysisResult: dataclass(frozen=True) đủ 9 trường (analysis_id, input_ref, analysis_kind, model, model_version, spec_revision, confidence, coverage, failure_flags) kèm from_mapping và kiểm tra chặt chẽ
  - AnalysisRevision: dataclass(frozen=True) (revision, result) với kiểm tra revision int >= 1 và result là AnalysisResult
  - AnalysisHistory: dataclass(frozen=True) append-only với 3 phương thức công khai append, revisions, get (không có hàm sửa/xóa/cập nhật)
  - ANALYSIS_FIELDS: tuple hằng số chứa tên 9 trường của AnalysisResult

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/voice/test_e04_media_analysis.py -q -p no:cacheprovider | 0 | 86 passed in 0.11s |
| 2 | python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider | 0 | 9 passed, 49 subtests passed in 0.05s |
| 3 | python -m pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cacheprovider | 0 | 65 passed in 0.10s |
| 4 | git diff --check | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Phản ví dụ đã loại trừ

1. **Model mới ghi đè kết quả cũ:** Loại trừ bởi `test_new_model_version_or_spec_adds_revision_and_keeps_old` và `test_same_input_model_version_spec_returns_old_history`. Model hoặc version mới thêm revision mới và bản cũ giữ nguyên identity truy được qua get/revisions; trùng cấu hình trả đúng đối tượng lịch sử cũ.
2. **Confidence 1.5 hợp lệ:** Loại trừ bởi `test_unit_interval_rejects_out_of_range` và `test_unit_interval_rejects_wrong_type`. Giá trị confidence và coverage ngoài [0,1] (1.5, -0.1, inf, nan, bool, chuỗi) bị từ chối bằng ProcessingContractError.
3. **Lịch sử bị rút gọn:** Loại trừ bởi `test_history_never_shrinks_and_keeps_prefix`, `test_public_api_has_no_edit_or_delete`, và `test_history_is_immutable`. AnalysisHistory bất biến, tiền tố lịch sử được bảo toàn nguyên vẹn, không có bất kỳ phương thức sửa, xóa, hay cập nhật nào trong API công khai.
4. **Analysis clip gắn safety state:** Loại trừ bởi `test_clip_analysis_has_no_safety_state` và `test_module_source_has_no_mutation_safety_or_io`. Không có trường, thuộc tính, chuỗi hoặc trạng thái safety nào trong AnalysisResult, AnalysisHistory hay mã nguồn module.

## Quyết định mặc định (D8)

- (a) Thêm trường spec_revision vì yêu cầu nghiệm thu nêu 'cùng input, model, version và spec'.
- (b) Trường model chứa tên model hoặc tool, model_version chứa phiên bản.
- (c) input_ref là ArtifactRef(ref, content_sha256) dùng lại từ processing.py.
- (d) Revision đánh số từ 1 theo chuỗi (input ref, input hash, loại phân tích).
- (e) Append trả đúng đối tượng lịch sử cũ khi trùng input+loại+model+version+spec, không ghi đè kết quả cũ kể cả khi confidence khác.
- (f) Tái dùng analysis_id cho phiên bản khác bị từ chối constraint_violation.
- (g) Quay lại model cũ không tạo bản trùng.
- (h) Confidence/coverage nhận int hoặc float hữu hạn trong [0,1], bool/NaN/inf/ngoài khoảng bị từ chối.
- (i) Không có trạng thái safety trong kết quả phân tích.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không sửa pyproject.toml, uv.lock, migration, composition root, src/voice/domain/processing.py.
- Không gọi dịch vụ thật hay model thật.
- E-04 chỉ là contract miền, chưa persistence (CONV-E-01).
