# Báo cáo bằng chứng J-03

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `2f4646097605e31871a73832e6fd0a7cbda289d3`
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-03 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/config/test_j_publish_plan.py -q -p no:cacheprovider` (chạy khi plan_publish là stub raise NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `55 failed, 5 passed in 0.58s`
- Các test FAILED kèm thông điệp nguyên văn:
  - `tests/unit/config/test_j_publish_plan.py::test_empty_scope_gives_number_one_without_supersede FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_scope_with_revisions_gives_max_plus_one_and_supersedes_published[1] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_scope_with_revisions_gives_max_plus_one_and_supersedes_published[2] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_scope_with_revisions_gives_max_plus_one_and_supersedes_published[3] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_supersedes_the_published_revision_not_the_highest_number FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_draft_counts_for_number_but_is_never_superseded FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_scope_without_published_revision_supersedes_nothing FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_number_ignores_concurrency_revision_field FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_valid_scope_kinds_are_accepted[module] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_valid_scope_kinds_are_accepted[policy] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_valid_scope_kinds_are_accepted[preset] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_valid_scope_kinds_are_accepted[prompt] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_valid_scope_kinds_are_accepted[provider] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_valid_scope_kinds_are_accepted[workspace] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_unknown_scope_kind_raises_invalid_scope_kind[] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_unknown_scope_kind_raises_invalid_scope_kind[Workspace] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_unknown_scope_kind_raises_invalid_scope_kind[account] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_unknown_scope_kind_raises_invalid_scope_kind[secret] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_unknown_scope_kind_raises_invalid_scope_kind[unknown] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_unknown_scope_kind_raises_invalid_scope_kind[config] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_base_other_than_max_raises_stale_base_revision[None] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_base_other_than_max_raises_stale_base_revision[0] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_base_other_than_max_raises_stale_base_revision[1] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_base_other_than_max_raises_stale_base_revision[2] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_base_other_than_max_raises_stale_base_revision[4] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_empty_scope_requires_base_none[0] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_empty_scope_requires_base_none[1] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_revisions_of_other_scopes_are_ignored_for_empty_scope FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_base_taken_from_another_scope_is_stale FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_other_scopes_do_not_change_number_or_supersede_target FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_content_hash_equals_request_hash_of_payload FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_effective_at_is_passed_through_without_clock FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_inputs_are_not_mutated FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_sensitive_key_at_any_depth_raises_secret_in_config[payload0] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_sensitive_key_at_any_depth_raises_secret_in_config[payload1] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_sensitive_key_at_any_depth_raises_secret_in_config[payload2] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_sensitive_key_at_any_depth_raises_secret_in_config[payload3] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_sensitive_key_at_any_depth_raises_secret_in_config[payload4] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_sensitive_key_at_any_depth_raises_secret_in_config[payload5] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_sensitive_key_at_any_depth_raises_secret_in_config[payload6] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_sensitive_key_at_any_depth_raises_secret_in_config[payload7] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_sensitive_key_at_any_depth_raises_secret_in_config[payload8] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_sensitive_key_at_any_depth_raises_secret_in_config[payload9] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_sensitive_key_at_any_depth_raises_secret_in_config[payload10] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_sensitive_key_at_any_depth_raises_secret_in_config[payload11] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_sensitive_key_at_any_depth_raises_secret_in_config[payload12] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_non_sensitive_keys_are_accepted FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_valid_rollback_adds_marker_and_keeps_old_revisions_untouched FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_rollback_with_different_payload_is_rejected FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_rollback_to_invalidated_or_draft_target_is_rejected[INVALIDATED] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_rollback_to_invalidated_or_draft_target_is_rejected[DRAFT] FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_rollback_to_missing_number_is_rejected FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_rollback_target_must_be_in_the_same_scope FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_rollback_with_stale_base_is_rejected FAILED (NotImplementedError: J-03 plan_publish)`
  - `tests/unit/config/test_j_publish_plan.py::test_validation_is_a_tuple FAILED (NotImplementedError: J-03 plan_publish)`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED do NotImplementedError.

## Thay đổi

- `src/controlplane/application/config_security/publish_plan.py`: hằng SCOPE_KINDS, SENSITIVE_KEY_NAMES, ROLLBACK_PREFIX; các ngoại lệ StaleBaseRevisionError, SecretInConfigError, RollbackTargetInvalidError; dataclass frozen PublishRequest (9 trường) và PublishPlan (5 trường); hàm thuần plan_publish tính số phiên bản kinh doanh tiếp theo, xác định revision bị supersede, kiểm tra khóa nhạy cảm đệ quy ở mọi độ sâu, xác thực tính hợp lệ của rollback target và gán nhãn ROLLBACK_OF:N vào validation mà không sửa đổi dữ liệu đầu vào.
- `tests/unit/config/test_j_publish_plan.py`: bộ 60 test bao phủ các acceptance criteria, lineage, stale base, scope kind, sensitive keys ở mọi độ sâu, rollback validation và contract types; docstring có dòng coveredIds: CT-CFG-001, CT-STATE-013, TST-INT-INV-004.
- `docs/delivery-evidence/j-03/report.md`: báo cáo bằng chứng này.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/config/test_j_publish_plan.py -q -p no:cacheprovider` | 0 | `60 passed in 0.11s` |
| 2 | `git diff --check` | 0 | PASS (không output) |
| 3 | `python -c "import pathlib; r=pathlib.Path('docs/delivery-evidence/j-03/report.md').read_text(encoding='utf-8'); t=pathlib.Path('tests/unit/config/test_j_publish_plan.py').read_text(encoding='utf-8'); assert '## RED' in r and '## GREEN' in r and 'NotImplementedError' in r and chr(65533) not in r; assert 'coveredIds: CT-CFG-001, CT-STATE-013, TST-INT-INV-004' in t"` | 0 | PASS (không output) |

## Quyết định mặc định (D8)

1. Khóa nhạy cảm so khớp casefold, bỏ ký tự không phải chữ số/chữ cái, khớp hậu tố sáu tên (password, secret, token, api_key, private_key, credential) nên apiKey, x-api-key, client_secret bị chặn còn max_tokens, token_budget, secret_handle_ref thì không; chỉ xét khóa, không xét giá trị.
2. Thứ tự kiểm tra: scope_kind (ValueError invalid_scope_kind), khóa nhạy cảm (SecretInConfigError), base_config_revision_number (StaleBaseRevisionError), rollback (RollbackTargetInvalidError).
3. DRAFT tính vào số lớn nhất của scope nhưng không bị supersede; revision bị supersede là revision PUBLISHED có số lớn nhất trong scope.
4. Rollback từ chối bằng RollbackTargetInvalidError khi revision đích bị thiếu, có trạng thái INVALIDATED, DRAFT hoặc content_hash khác với payload request; đích có trạng thái PUBLISHED hoặc SUPERSEDED cùng hash được chấp nhận; rollback hợp lệ thêm marker ROLLBACK_OF:N vào validation và phát hành revision số mới mà không sửa revision cũ.
5. effective_at chuyển nguyên từ request sang plan, không đọc đồng hồ hệ thống.
6. Ba lỗi nghiệp vụ (StaleBaseRevisionError, SecretInConfigError, RollbackTargetInvalidError) được định nghĩa trong publish_plan.py vì chưa có sẵn trong mã, kế thừa trực tiếp Exception (không phải ValueError); thông điệp là mã cố định, không chứa giá trị payload để tránh rò rỉ dữ liệu nhạy cảm.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10: danh sách thư viện và cách dựng lại runtime.
- CP7 tài nguyên thật (D5): kết nối Drive/OAuth, GPU, AI trả phí.
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, lockfile, __init__.py hay các tệp ngoài owned paths.
- Không ghi DB, không đọc đồng hồ hệ thống, không gọi dịch vụ thật.
