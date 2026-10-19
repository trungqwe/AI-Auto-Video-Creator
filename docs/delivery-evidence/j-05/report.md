# Báo cáo bằng chứng J-05

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `b83d371b45f27f784aeeaa35fd36979636c75423`
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-05 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/config/test_j_bundle_resolution.py -q -p no:cacheprovider` (chạy khi stub bundle_resolution.py còn raise NotImplementedError và EffectiveConfigRevision chưa kiểm tra datetime naive)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `40 failed, 9 passed in 0.65s`
- Các test FAILED kèm thông điệp nguyên văn:
  - `tests/unit/config/test_j_bundle_resolution.py::test_naive_effective_at_raises_value_error_with_code FAILED (Failed: DID NOT RAISE ValueError)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_future_effective_at_is_ignored_and_not_applied_early FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_none_equal_or_past_effective_at_is_applied[None] FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_none_equal_or_past_effective_at_is_applied[effective_at1] FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_none_equal_or_past_effective_at_is_applied[effective_at2] FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_latest_effective_number_wins_per_scope FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_only_published_revisions_are_selected_when_not_committed[SUPERSEDED] FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_only_published_revisions_are_selected_when_not_committed[INVALIDATED] FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_only_published_revisions_are_selected_when_not_committed[DRAFT] FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_missing_required_scope_raises_missing_scope FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_revision_of_another_workspace_is_skipped_without_revealing_it FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_invalid_request_is_rejected_with_codes FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_job_snapshot_keeps_old_revision_and_fingerprint_after_new_publish FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_committed_without_pin_raises_missing_pin FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_committed_pin_to_invalidated_revision_raises FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_committed_pin_to_superseded_revision_is_used FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_committed_pin_to_draft_raises_missing_pin FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_committed_pin_to_foreign_or_other_scope_revision_is_missing_pin FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_committed_ignores_effective_at_of_pinned_revision FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_merge_order_is_workspace_module_provider_preset_policy FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_deep_merge_overrides_leaf_and_keeps_siblings_with_provenance FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_type_change_replaces_value_and_provenance_prefix FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_same_kind_scopes_merge_in_scope_key_order_regardless_of_input_order FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_prompt_scope_is_only_in_revision_refs FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_sensitive_key_in_selected_revision_raises_without_leaking[workspace-default-payload0] FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_sensitive_key_in_selected_revision_raises_without_leaking[workspace-default-payload1] FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_sensitive_key_in_selected_revision_raises_without_leaking[workspace-default-payload2] FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_sensitive_key_in_selected_revision_raises_without_leaking[workspace-default-payload3] FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_sensitive_key_in_selected_revision_raises_without_leaking[prompt-script-payload0] FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_sensitive_key_in_selected_revision_raises_without_leaking[prompt-script-payload1] FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_sensitive_key_in_selected_revision_raises_without_leaking[prompt-script-payload2] FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_sensitive_key_in_selected_revision_raises_without_leaking[prompt-script-payload3] FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_sensitive_key_in_pinned_revision_raises FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_non_sensitive_keys_and_unselected_revisions_do_not_raise FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_fingerprint_is_sha256_of_canonical_refs_and_values FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_result_is_independent_of_input_order_and_repeatable FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_fingerprint_changes_with_values_or_selected_revision FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_fingerprint_ignores_key_order_of_payload FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_inputs_are_not_mutated_and_result_does_not_alias_payloads FAILED (NotImplementedError: J-05 resolve_bundle)`
  - `tests/unit/config/test_j_bundle_resolution.py::test_contract_types_are_frozen_with_contract_fields FAILED (NotImplementedError: J-05 resolve_bundle)`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED hợp lệ do NotImplementedError và DID NOT RAISE.

## Thay đổi

- `src/controlplane/application/config_security/bundle_resolution.py`: định nghĩa dataclass frozen `EffectiveConfigRevision` (bọc `ConfigRevision` P5A 9 trường, từ chối datetime naive bằng `ValueError('naive_effective_at')`), `BundleRequest`, `ConfigBundle`; các ngoại lệ `MissingPinError`, `PinnedRevisionInvalidatedError`, `MissingScopeError`, `BundleSecretError`; hàm thuần `resolve_bundle` giải quyết cấu hình job stage kèm provenance theo cơ chế snapshot pinning (COMMITTED) hoặc thời gian hiệu lực (NOT_COMMITTED), hợp nhất cấu hình sâu theo thứ tự workspace < module < provider < preset < policy, prompt chỉ xuất hiện trong `revision_refs`, kiểm tra khóa nhạy cảm đệ quy và tính fingerprint SHA-256 từ JSON chuẩn hóa mà không gây đột biến hay alias dữ liệu đầu vào.
- `tests/unit/config/test_j_bundle_resolution.py`: bộ 49 test bao phủ toàn bộ các acceptance criteria về EffectiveConfigRevision, snapshot pinning, NOT_COMMITTED, cách ly workspace, thứ tự merge, deep merge kèm provenance, khóa nhạy cảm, fingerprint SHA-256 và tính thuần của module; docstring có dòng `coveredIds: CT-CFG-002, TST-INT-INV-004, TST-SEC-INV-020`.
- `docs/delivery-evidence/j-05/report.md`: báo cáo bằng chứng này.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/config/test_j_bundle_resolution.py -q -p no:cacheprovider` | 0 | `49 passed in 0.08s` |
| 2 | `git diff --check` | 0 | PASS (không output) |
| 3 | `python -c "import pathlib; r=pathlib.Path('docs/delivery-evidence/j-05/report.md').read_text(encoding='utf-8'); t=pathlib.Path('tests/unit/config/test_j_bundle_resolution.py').read_text(encoding='utf-8'); assert '## RED' in r and '## GREEN' in r and 'NotImplementedError' in r and chr(65533) not in r; assert 'coveredIds: CT-CFG-002, TST-INT-INV-004, TST-SEC-INV-020' in t"` | 0 | PASS (không output) |

## Quyết định mặc định (D8)

1. GIẢ ĐỊNH D8-J-10 thứ tự merge workspace < module < provider < preset < policy, dict merge sâu, kiểu khác thay hoàn toàn và xóa provenance cũ có tiền tố trùng đường dẫn, scope cùng kind merge theo scope_key.
2. revision_refs là config_revision_id đã sắp, prompt chỉ vào refs (không vào values).
3. provenance là dict đường dẫn chấm của lá giá trị sang config_revision_id.
4. Mã lỗi: naive_effective_at, naive_evaluation_time, invalid_snapshot_state, invalid_scope_kind (ValueError); missing_pin, pinned_revision_not_published, pinned_revision_invalidated, missing_scope, secret_in_bundle (ngoại lệ kế thừa Exception, không phải ValueError).
5. COMMITTED chấp nhận pin SUPERSEDED, bỏ qua effective_at, pin DRAFT bị từ chối bằng pinned_revision_not_published, pin trỏ revision workspace khác hoặc scope khác cho cùng mã missing_pin (không làm lộ sự tồn tại).
6. Khóa nhạy cảm dùng lại _contains_sensitive_key của J-03 để cùng một luật xác thực.
7. warnings luôn là tuple rỗng () vì CT-CFG-002 chưa nêu điều kiện cảnh báo.
8. ConfigRevision P5A và mọi __init__.py giữ nguyên, ánh xạ cột effective_at thuộc YC-HT-J-01.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10: danh sách thư viện và cách dựng lại runtime.
- CP7 tài nguyên thật (D5): kết nối Drive/OAuth, GPU, AI trả phí.
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, lockfile, __init__.py hay các tệp ngoài owned paths.
- Không ghi DB, không đọc đồng hồ hệ thống (datetime.now, utcnow, today), không gọi dịch vụ thật.
