# Báo cáo bằng chứng D-02

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `c73f90b87c3aa9bd038e9c1b71374ceb1b04a20f`
- Nguồn quyền: IMPL-PLAN-D Auditor PASS, slice D-02 trong docs/implementation/d/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d02_production_snapshot.py -q -p no:cacheprovider` (chạy với khung snapshot.py chưa có hành vi)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `58 failed, 10 passed in 0.53s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp assertion nguyên văn:
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_constants_match_binding`: `AssertionError: assert ({}, {}, {}, {}) == ({'snapshot_i...s': 'object'})`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_drift_comparison_detects_mutated_binding`: `AssertionError: SNAPSHOT_REQUIRED must not be empty`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_fixture_invalid_case_returns_expected_issue[missing_source_set_fingerprint]`: `AssertionError: assert [] == [('missing_re...fingerprint')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_fixture_invalid_case_returns_expected_issue[production_mode_outside_contract]`: `AssertionError: assert [] == [('enum_viola...uction_mode')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_fixture_invalid_case_returns_expected_issue[configuration_fingerprint_not_sha256]`: `AssertionError: assert [] == [('wrong_type...fingerprint')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_fixture_invalid_case_returns_expected_issue[source_refs_as_strings]`: `AssertionError: assert [] == [('wrong_type...source_refs')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_each_missing_required_field_is_reported`: `AssertionError: SNAPSHOT_REQUIRED must not be empty`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[production_mode-timeline-enum_violation]`: `AssertionError: assert [] == [('enum_viola...uction_mode')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[production_mode-Single_Article-enum_violation]`: `AssertionError: assert [] == [('enum_viola...uction_mode')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[production_mode-1-wrong_type]`: `AssertionError: assert [] == [('wrong_type...uction_mode')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[snapshot_id-5-wrong_type]`: `AssertionError: assert [] == [('wrong_type...snapshot_id')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[snapshot_id-None-wrong_type]`: `AssertionError: assert [] == [('wrong_type...snapshot_id')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[eligibility_reason-value5-missing_required]`: `AssertionError: assert [] == [('missing_re...lity_reason')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[source_set_fingerprint-0123456789ABCDEF...-wrong_type]`: `AssertionError: assert [] == [('wrong_type...fingerprint')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[source_set_fingerprint-63chars-wrong_type]`: `AssertionError: assert [] == [('wrong_type...fingerprint')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[source_set_fingerprint-65chars-wrong_type]`: `AssertionError: assert [] == [('wrong_type...fingerprint')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[source_set_fingerprint-non_hex_g-wrong_type]`: `AssertionError: assert [] == [('wrong_type...fingerprint')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[configuration_bundle_fingerprint-None-wrong_type]`: `AssertionError: assert [] == [('wrong_type...fingerprint')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[configuration_bundle_fingerprint-abc-wrong_type]`: `AssertionError: assert [] == [('wrong_type...fingerprint')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[snapshot_timestamp-yesterday-wrong_type]`: `AssertionError: assert [] == [('wrong_type...t_timestamp')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[snapshot_timestamp-no_offset-wrong_type]`: `AssertionError: assert [] == [('wrong_type...t_timestamp')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[snapshot_timestamp-month13-wrong_type]`: `AssertionError: assert [] == [('wrong_type...t_timestamp')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[source_refs-[1]-wrong_type]`: `AssertionError: assert [] == [('wrong_type...source_refs')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[source_refs-x-wrong_type]`: `AssertionError: assert [] == [('wrong_type...source_refs')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[index_revision_refs-['idx']-wrong_type]`: `AssertionError: assert [] == [('wrong_type...evision_refs')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[configuration_revision_refs-dict-wrong_type]`: `AssertionError: assert [] == [('wrong_type...evision_refs')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[batch_ref-5-wrong_type]`: `AssertionError: assert [] == [('wrong_type...batch_ref')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[video_job_ref-['job']-wrong_type]`: `AssertionError: assert [] == [('wrong_type...o_job_ref')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_field_counterexamples_are_rejected[recent_variant_exclusions-x-wrong_type]`: `AssertionError: assert [] == [('wrong_type...exclusions')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_non_mapping_payload_is_wrong_type`: `AssertionError: assert [] == [('wrong_type', '$')]`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_integer_type_rejects_bool`: `AssertionError: assert False is True`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_sha256_type_requires_64_lowercase_hex`: `AssertionError: assert False is True`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_build_returns_frozen_snapshot_that_passes_validator`: `AssertionError: assert isinstance(None, ProductionSnapshot)`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_optional_fields_are_omitted_when_absent`: `AttributeError: 'NoneType' object has no attribute 'to_payload'`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_each_binding_production_mode_builds[single_article]`: `AttributeError: 'NoneType' object has no attribute 'production_mode'`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_each_binding_production_mode_builds[multi_article_event]`: `AttributeError: 'NoneType' object has no attribute 'production_mode'`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_each_binding_production_mode_builds[from_then_to_now]`: `AttributeError: 'NoneType' object has no attribute 'production_mode'`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_build_from_fixture_inputs_matches_fixture_payload`: `AttributeError: 'NoneType' object has no attribute 'to_payload'`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_fingerprint_does_not_depend_on_ref_order`: `AttributeError: 'NoneType' object has no attribute 'source_set_fingerprint'`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_fingerprint_changes_with_revision_or_ref_set`: `AttributeError: 'NoneType' object has no attribute 'source_set_fingerprint'`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_fingerprint_is_computed_by_request_hash_on_sorted_refs`: `AssertionError: assert '' == 'ffffffffffff...ffffffffffff'`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_snapshot_cannot_be_mutated_after_creation`: `AttributeError: 'NoneType' object has no attribute 'source_refs'`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_later_changes_to_inputs_do_not_reach_snapshot`: `AttributeError: 'NoneType' object has no attribute 'to_payload'`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_missing_revision_id_is_input_not_ready[absent-source_refs]`: `Failed: DID NOT RAISE SnapshotRejected`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_missing_revision_id_is_input_not_ready[absent-index_revision_refs]`: `Failed: DID NOT RAISE SnapshotRejected`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_missing_revision_id_is_input_not_ready[absent-configuration_revision_refs]`: `Failed: DID NOT RAISE SnapshotRejected`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_missing_revision_id_is_input_not_ready[none-source_refs]`: `Failed: DID NOT RAISE SnapshotRejected`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_missing_revision_id_is_input_not_ready[none-index_revision_refs]`: `Failed: DID NOT RAISE SnapshotRejected`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_missing_revision_id_is_input_not_ready[none-configuration_revision_refs]`: `Failed: DID NOT RAISE SnapshotRejected`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_missing_revision_id_is_input_not_ready[empty-source_refs]`: `Failed: DID NOT RAISE SnapshotRejected`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_missing_revision_id_is_input_not_ready[empty-index_revision_refs]`: `Failed: DID NOT RAISE SnapshotRejected`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_missing_revision_id_is_input_not_ready[empty-configuration_revision_refs]`: `Failed: DID NOT RAISE SnapshotRejected`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_ref_outside_content_set_is_not_eligible[dedup_observation]`: `Failed: DID NOT RAISE SnapshotRejected`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_ref_outside_content_set_is_not_eligible[collected_document]`: `Failed: DID NOT RAISE SnapshotRejected`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_duplicate_observation_does_not_create_snapshot`: `AssertionError: assert [None] == []`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_content_ref_types_come_from_policy_without_hidden_default`: `AttributeError: 'NoneType' object has no attribute 'source_refs'`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_missing_policy_inputs_are_input_not_ready`: `Failed: DID NOT RAISE SnapshotRejected`
  - `FAILED tests/unit/creative/test_d02_production_snapshot.py::test_invalid_arguments_raise_value_error`: `Failed: DID NOT RAISE ValueError`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection; RED là sai oracle (hằng khác binding, validator không báo lỗi, build không trả ProductionSnapshot, DID NOT RAISE).

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d02_production_snapshot.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `68 passed in 0.08s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/creative/domain/snapshot.py`: Triển khai hằng đặc tả trường cấp 1 (`SNAPSHOT_REQUIRED`, `SNAPSHOT_OPTIONAL`, `SNAPSHOT_ENUM`, `SNAPSHOT_ITEMS`), `ValidationIssue`, `matches_type`, `validate_production_snapshot`, ngoại lệ `SnapshotRejected(code, reason)`, frozen dataclass `ProductionSnapshot` (12 trường kèm `to_payload`), `fingerprint_refs` (gọi `request_hash` trên danh sách ref đã sắp xếp theo 3 khoá) và `build_production_snapshot` (kiểm tra kiểu/giá trị tham số, `INPUT_NOT_READY` khi thiếu revision_id hoặc policy bắt buộc, `NOT_ELIGIBLE` khi ref nằm ngoài tập ref nội dung, chuẩn hoá và băm fingerprint xác định).
  - `tests/unit/creative/test_d02_production_snapshot.py`: Bộ kiểm thử đơn vị bao gồm kiểm tra hằng khớp contract binding JSON và chống trôi dạt (drift comparison), kiểm tra fixture valid/invalid, kiểm tra validator báo lỗi đúng loại (`missing_required`, `wrong_type`, `enum_violation`) và bỏ qua trường lạ, kiểm tra build snapshot trả về frozen dataclass, fingerprint không phụ thuộc thứ tự ref truyền vào, snapshot bất biến sau khởi tạo, từ chối quan sát bài trùng, kiểm tra không có thực thể `ArticleSnapshot`, và kiểm tra giới hạn import trong allowlist.
  - `docs/delivery-evidence/d-02/report.md`: Báo cáo bằng chứng chuyển giao của task D-02.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/creative/test_d02_production_snapshot.py -q -p no:cacheprovider` | 0 | 68 passed in 0.08s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `snapshot_id`, `snapshot_timestamp` (chuỗi RFC 3339 có offset), `content_ref_types`, `eligibility_reason` do caller cấp, không default ẩn.
2. Thiếu `revision_id`/`content_ref_types`/`eligibility_reason`/`source_refs`/`configuration_revision_refs` → `INPUT_NOT_READY` với machine reason ổn định, `index_revision_refs` được phép rỗng.
3. Ref ngoài `content_ref_types` ở `source_refs` → `NOT_ELIGIBLE` (reason `ref_type_not_content`), kiểm tra trước `INPUT_NOT_READY`.
4. Ref chuẩn hoá về 3 khoá (`ref_type`, `ref_id`, `revision_id`), dedupe, sắp xếp theo `(ref_type, ref_id, revision_id)`; `configuration_bundle_fingerprint` chỉ băm `configuration_revision_refs`.
5. `recent_variant_exclusions` là tập chuỗi khác rỗng đã sắp xếp (GIẢ ĐỊNH vì binding chỉ khoá 'array').
6. Tập `ref_type` nội dung và `'event_update_accepted'` trong test là GIẢ ĐỊNH theo plan IMPL-PLAN-D.
7. Tham số sai và production mode ngoài binding (kể cả `timeline`) → `ValueError`.
8. Chỉ dùng stdlib và `request_hash`, không thêm thư viện ngoài.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`.
- Không gọi dịch vụ thật.
- CoveredIds: CT-AI-001, TST-INT-INV-004 (mức domain), TST-INT-INV-005 (phía D).
