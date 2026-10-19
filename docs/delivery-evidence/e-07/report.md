# Báo cáo bằng chứng E-07

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: c695121600c8d1b73e9153cbd26dab92cf2f6b18
- Nguồn quyền: IMPL-PLAN-E Auditor PASS, slice E-07 trong docs/implementation/e/slices.md, CT-PROC-007 tại docs/09-contracts/07-media-processing-contracts.md §5

## RED

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e07_normalize_media.py -q -p no:cacheprovider (chạy trên khung stub trước khi cài đặt hành vi)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 94 failed, 12 passed in 1.34s
- Nhóm test FAILED (94 test) do assertion, DID NOT RAISE và AttributeError trên kết quả stub:
  - `test_step_maps_known_operation_to_enum_and_keeps_unknown_text`
  - `test_spec_and_steps_are_frozen_and_immutable`
  - `test_spec_copies_params_so_caller_mutation_cannot_change_fingerprint`
  - `test_spec_fingerprint_is_request_hash_of_spec_payload`
  - `test_same_spec_same_fingerprint_and_any_change_alters_it`
  - `test_operation_order_changes_fingerprint_but_params_key_order_does_not`
  - `test_spec_rejects_invalid_fields` (10 cases)
  - `test_step_rejects_invalid_fields` (8 cases)
  - `test_plan_is_frozen_with_lineage_and_new_output_ref`
  - `test_output_ref_equal_to_input_is_rejected`
  - `test_plan_rejects_inconsistent_lineage_or_fingerprints`
  - `test_same_input_spec_tool_version_gives_same_fingerprints_and_output_ref`
  - `test_different_tool_version_or_seed_changes_every_fingerprint`
  - `test_different_input_changes_plan_fingerprint_but_not_spec_fingerprint`
  - `test_plan_rejects_unknown_media_kind` (4 cases)
  - `test_plan_requires_artifact_ref_spec_and_focus_region_types`
  - `test_plan_rejects_operations_outside_the_enum` (2 cases)
  - `test_focus_region_validates_fields` (6 cases)
  - `test_crop_containing_focus_region_is_accepted`
  - `test_crop_that_loses_focus_region_is_rejected` (7 cases)
  - `test_second_crop_losing_focus_is_rejected_with_its_index`
  - `test_crop_without_focus_region_has_no_focus_constraint`
  - `test_focus_rule_is_also_checked_on_direct_plan_construction`
  - `test_crop_params_are_validated` (7 cases)
  - `test_clip_with_blur_or_recolor_is_rejected` (5 cases)
  - `test_clip_technical_normalization_is_accepted`
  - `test_shell_command_strings_are_rejected_everywhere` (11 cases)
  - `test_plan_has_no_command_like_fields_or_values`
  - `test_tool_outcome_is_frozen_with_four_fields`
  - `test_tool_outcome_rejects_inconsistent_fields` (11 cases)
  - `test_non_success_outcomes_carry_no_output`
  - `test_media_tool_port_is_runtime_protocol_and_fake_conforms`
  - `test_verify_tool_outcome_rejects_overwriting_original_or_wrong_output`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection; các lỗi đều do oracle kiểm thử hành vi.

## Thay đổi

4 tệp thuộc owned paths được tạo và cập nhật:
- `src/voice/domain/normalize.py`: Module domain thuần túy lập kế hoạch rendition cho NormalizeMedia (CT-PROC-007). Định nghĩa enum NormalizeOperation (8 giá trị: crop, resize, pad, color_conversion, transcode, audio_normalize, extract_frame, duration_trim); FocusRegion; NormalizeStep; NormalizeSpec frozen có spec_fingerprint tính bằng request_hash; RenditionPlan frozen có lineage_refs, plan_fingerprint, output_ref (mặc định rendition:<plan_fingerprint>, không được trùng input_ref), output_class là REUSABLE; plan_rendition; verify_tool_outcome; bảo vệ focus_region khi crop; từ chối safety transform đối với clip; kiểm tra chống chuỗi lệnh shell.
- `src/voice/ports/media_tool.py`: Định nghĩa ToolOutcome frozen (gồm status thuộc Disposition, output_ref, output_sha256, error với ràng buộc theo status); MediaToolPort là Protocol runtime_checkable cho adapter bên ngoài thực thi rendition plan.
- `tests/unit/voice/test_e07_normalize_media.py`: Bộ kiểm thử đơn vị toàn diện gồm 106 test bao phủ enum, tính bất biến frozen, tính toán fingerprint bằng request_hash, validation dữ liệu, lineage, focus rule, chặn safety transform trên clip, chặn injection shell command, ToolOutcome và MediaToolPort, cùng kiểm tra tĩnh AST đảm bảo không chạy tiến trình ngoài hay import cấm.
- `docs/delivery-evidence/e-07/report.md`: Báo cáo bằng chứng chuyển giao của slice E-07.

## Ánh xạ acceptance

| Yêu cầu acceptance | Kiểm thử xác minh | Trạng thái |
|---|---|---|
| NormalizeOperation (StrEnum 8 giá trị) | `test_operation_enum_has_exactly_eight_values`, `test_step_maps_known_operation_to_enum_and_keeps_unknown_text` | PASS |
| NormalizeSpec frozen, spec_fingerprint bằng request_hash | `test_spec_and_steps_are_frozen_and_immutable`, `test_spec_copies_params_so_caller_mutation_cannot_change_fingerprint`, `test_spec_fingerprint_is_request_hash_of_spec_payload`, `test_spec_rejects_invalid_fields`, `test_step_rejects_invalid_fields` | PASS |
| plan_rendition trả RenditionPlan frozen có lineage, output ref khác input (trùng -> lỗi) | `test_plan_is_frozen_with_lineage_and_new_output_ref`, `test_output_ref_equal_to_input_is_rejected`, `test_plan_rejects_inconsistent_lineage_or_fingerprints` | PASS |
| Cùng input/spec/tool_version -> cùng fingerprint; khác tool_version hoặc seed -> khác | `test_same_spec_same_fingerprint_and_any_change_alters_it`, `test_operation_order_changes_fingerprint_but_params_key_order_does_not`, `test_same_input_spec_tool_version_gives_same_fingerprints_and_output_ref`, `test_different_tool_version_or_seed_changes_every_fingerprint`, `test_different_input_changes_plan_fingerprint_but_not_spec_fingerprint` | PASS |
| Crop làm mất focus_region -> focus_rule_violation | `test_focus_region_validates_fields`, `test_crop_containing_focus_region_is_accepted`, `test_crop_that_loses_focus_region_is_rejected`, `test_second_crop_losing_focus_is_rejected_with_its_index`, `test_crop_without_focus_region_has_no_focus_constraint`, `test_focus_rule_is_also_checked_on_direct_plan_construction`, `test_crop_params_are_validated` | PASS |
| Clip kèm blur/recolor -> từ chối (safety_transform_not_applicable) | `test_clip_with_blur_or_recolor_is_rejected`, `test_clip_technical_normalization_is_accepted`, `test_plan_rejects_unknown_media_kind`, `test_plan_rejects_operations_outside_the_enum` | PASS |
| MediaToolPort Protocol trả ToolOutcome; verify_tool_outcome chặn trùng bản gốc | `test_tool_outcome_is_frozen_with_four_fields`, `test_tool_outcome_rejects_inconsistent_fields`, `test_non_success_outcomes_carry_no_output`, `test_media_tool_port_is_runtime_protocol_and_fake_conforms`, `test_verify_tool_outcome_rejects_overwriting_original_or_wrong_output` | PASS |
| Plan không chứa chuỗi lệnh shell; kiểm tra tĩnh AST thuần túy | `test_shell_command_strings_are_rejected_everywhere`, `test_ordinary_technical_values_are_not_mistaken_for_shell`, `test_plan_has_no_command_like_fields_or_values`, `test_sources_are_pure_and_never_run_processes` | PASS |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `git diff --check` | 0 | PASS (không có output, không có trailing whitespace, diff sạch) |
| 2 | `python -m pytest tests/unit/voice/test_e07_normalize_media.py -q -p no:cacheprovider` | 0 | 106 passed in 0.12s |
| 3 | `python -m pytest tests/unit/voice -q -p no:cacheprovider` | 0 | 357 passed, 49 subtests passed in 0.45s |

## Quyết định mặc định (D8)

1. Tọa độ crop tính theo pixel khung đầu vào, GIẢ ĐỊNH (IMPL-PLAN-E §7).
2. Không có focus_region thì crop không bị ràng buộc.
3. Blur và recolor không thuộc NormalizeOperation: clip bị từ chối mã safety_transform_not_applicable, ảnh và audio bị enum_violation, việc xử lý nhạy cảm thuộc E-06.
4. Không có bảng tương thích operation theo media_kind, để slice sau.
5. Chặn chuỗi shell bằng danh sách ký tự và tên công cụ, plan chỉ là dữ liệu, tool chạy qua MediaToolPort.
6. Output_ref mặc định là rendition:<plan_fingerprint>, tham số output_ref tùy chọn, trùng input thì lỗi.
7. Khóa dedup plan_fingerprint gồm ref, sha256 input và spec_fingerprint, không gồm focus_region và media_kind.
8. ToolOutcome.status dùng Disposition của E-02, trạng thái không thành công không mang output.
9. Chỉ dùng stdlib, voice.* và controlplane.application.idempotency.canonicalization.
10. Chưa wiring RegisterRendition (CT-MED-003) với C, thuộc CONV-E-07.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10 và CP7 tài nguyên thật (D5)
- CP7-E-04 FFmpeg thật
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock.
- Không gọi mạng hay công cụ media thật.
- SHA commit báo trong worker_done, không ghi trong tệp này.
