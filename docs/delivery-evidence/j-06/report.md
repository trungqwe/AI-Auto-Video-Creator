# Báo cáo bằng chứng J-06

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `d83ab6107189a14ba92fb3d8d81789f946b461a8`
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-06 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/config/test_j_external_account.py -q -p no:cacheprovider` (chạy khi external_account.py là stub)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `39 failed, 1 passed in 0.31s`
- Các test FAILED kèm thông điệp nguyên văn (NotImplementedError):
  - `tests/unit/config/test_j_external_account.py::test_to_view_returns_exactly_the_nine_ct_acc_001_keys FAILED (NotImplementedError: J-06 to_view)`
  - `tests/unit/config/test_j_external_account.py::test_to_view_status_is_lowercase[ENABLED] FAILED (NotImplementedError: J-06 to_view)`
  - `tests/unit/config/test_j_external_account.py::test_to_view_status_is_lowercase[DISABLED] FAILED (NotImplementedError: J-06 to_view)`
  - `tests/unit/config/test_j_external_account.py::test_to_view_status_is_lowercase[DEGRADED] FAILED (NotImplementedError: J-06 to_view)`
  - `tests/unit/config/test_j_external_account.py::test_to_view_status_is_lowercase[INVALID] FAILED (NotImplementedError: J-06 to_view)`
  - `tests/unit/config/test_j_external_account.py::test_to_view_status_is_lowercase[REVOKED] FAILED (NotImplementedError: J-06 to_view)`
  - `tests/unit/config/test_j_external_account.py::test_to_view_capabilities_is_sorted_list FAILED (NotImplementedError: J-06 to_view)`
  - `tests/unit/config/test_j_external_account.py::test_to_view_credential_metadata_has_only_present_updated_at_expires_at FAILED (NotImplementedError: J-06 to_view)`
  - `tests/unit/config/test_j_external_account.py::test_to_view_keeps_optional_keys_when_values_are_none FAILED (NotImplementedError: J-06 to_view)`
  - `tests/unit/config/test_j_external_account.py::test_to_view_and_account_leak_no_secret_or_handle FAILED (NotImplementedError: J-06 to_view)`
  - `tests/unit/config/test_j_external_account.py::test_allows_role_true_for_enabled_matching_workspace_and_granted_role FAILED (NotImplementedError: J-06 account_allows_role)`
  - `tests/unit/config/test_j_external_account.py::test_allows_role_false_unless_status_is_enabled[DISABLED] FAILED (NotImplementedError: J-06 account_allows_role)`
  - `tests/unit/config/test_j_external_account.py::test_allows_role_false_unless_status_is_enabled[DEGRADED] FAILED (NotImplementedError: J-06 account_allows_role)`
  - `tests/unit/config/test_j_external_account.py::test_allows_role_false_unless_status_is_enabled[INVALID] FAILED (NotImplementedError: J-06 account_allows_role)`
  - `tests/unit/config/test_j_external_account.py::test_allows_role_false_unless_status_is_enabled[REVOKED] FAILED (NotImplementedError: J-06 account_allows_role)`
  - `tests/unit/config/test_j_external_account.py::test_allows_role_false_for_ungranted_role FAILED (NotImplementedError: J-06 account_allows_role)`
  - `tests/unit/config/test_j_external_account.py::test_allows_role_false_for_other_workspace FAILED (NotImplementedError: J-06 account_allows_role)`
  - `tests/unit/config/test_j_external_account.py::test_allows_role_matches_exactly_without_wildcard FAILED (NotImplementedError: J-06 account_allows_role)`
  - `tests/unit/config/test_j_external_account.py::test_rotate_credential_returns_new_account_with_higher_version FAILED (NotImplementedError: J-06 rotate_credential)`
  - `tests/unit/config/test_j_external_account.py::test_rotate_credential_keeps_status_and_never_reactivates[ENABLED] FAILED (NotImplementedError: J-06 rotate_credential)`
  - `tests/unit/config/test_j_external_account.py::test_rotate_credential_keeps_status_and_never_reactivates[DISABLED] FAILED (NotImplementedError: J-06 rotate_credential)`
  - `tests/unit/config/test_j_external_account.py::test_rotate_credential_keeps_status_and_never_reactivates[DEGRADED] FAILED (NotImplementedError: J-06 rotate_credential)`
  - `tests/unit/config/test_j_external_account.py::test_rotate_credential_keeps_status_and_never_reactivates[INVALID] FAILED (NotImplementedError: J-06 rotate_credential)`
  - `tests/unit/config/test_j_external_account.py::test_rotate_credential_keeps_status_and_never_reactivates[REVOKED] FAILED (NotImplementedError: J-06 rotate_credential)`
  - `tests/unit/config/test_j_external_account.py::test_rotate_credential_rejects_equal_or_lower_version[3] FAILED (NotImplementedError: J-06 rotate_credential)`
  - `tests/unit/config/test_j_external_account.py::test_rotate_credential_rejects_equal_or_lower_version[2] FAILED (NotImplementedError: J-06 rotate_credential)`
  - `tests/unit/config/test_j_external_account.py::test_rotate_credential_rejects_equal_or_lower_version[0] FAILED (NotImplementedError: J-06 rotate_credential)`
  - `tests/unit/config/test_j_external_account.py::test_rotate_credential_rejects_equal_or_lower_version[-1] FAILED (NotImplementedError: J-06 rotate_credential)`
  - `tests/unit/config/test_j_external_account.py::test_rotate_and_reactivate_reject_non_int_version FAILED (NotImplementedError: J-06 rotate_credential)`
  - `tests/unit/config/test_j_external_account.py::test_rotate_and_reactivate_reject_blank_timestamp FAILED (NotImplementedError: J-06 rotate_credential)`
  - `tests/unit/config/test_j_external_account.py::test_reactivate_from_revoked_with_newer_version_returns_new_enabled_account FAILED (NotImplementedError: J-06 reactivate_with_new_credential)`
  - `tests/unit/config/test_j_external_account.py::test_reactivate_rejects_equal_or_older_credential_version[3] FAILED (NotImplementedError: J-06 reactivate_with_new_credential)`
  - `tests/unit/config/test_j_external_account.py::test_reactivate_rejects_equal_or_older_credential_version[2] FAILED (NotImplementedError: J-06 reactivate_with_new_credential)`
  - `tests/unit/config/test_j_external_account.py::test_reactivate_rejects_equal_or_older_credential_version[0] FAILED (NotImplementedError: J-06 reactivate_with_new_credential)`
  - `tests/unit/config/test_j_external_account.py::test_reactivate_rejects_non_revoked_account[ENABLED] FAILED (NotImplementedError: J-06 reactivate_with_new_credential)`
  - `tests/unit/config/test_j_external_account.py::test_reactivate_rejects_non_revoked_account[DISABLED] FAILED (NotImplementedError: J-06 reactivate_with_new_credential)`
  - `tests/unit/config/test_j_external_account.py::test_reactivate_rejects_non_revoked_account[DEGRADED] FAILED (NotImplementedError: J-06 reactivate_with_new_credential)`
  - `tests/unit/config/test_j_external_account.py::test_reactivate_rejects_non_revoked_account[INVALID] FAILED (NotImplementedError: J-06 reactivate_with_new_credential)`
  - `tests/unit/config/test_j_external_account.py::test_reactivation_is_not_a_status_graph_edge_and_restores_routing FAILED (NotImplementedError: J-06 account_allows_role)`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED hợp lệ do NotImplementedError.

## Thay đổi

- `src/controlplane/domain/config_security/external_account.py`: Dataclass frozen `ExternalAccount` với 13 trường (status kiểu `ExternalAccountStatus` import từ status_graph J-04), hàm `to_view` trả đúng 9 khóa không lộ secret hay handle, hàm `account_allows_role` kiểm tra quyền phân vai chính xác theo QR-SEC-009 không hỗ trợ wildcard, `rotate_credential` xoay credential với version tăng dần, `reactivate_with_new_credential` kích hoạt lại tài khoản từ REVOKED thành ENABLED với version mới.
- `tests/unit/config/test_j_external_account.py`: Bộ kiểm thử 40 test cases bao phủ dataclass frozen, to_view 9 khóa và lowercase status, sắp xếp capabilities, credential metadata, kiểm tra role-based routing chính xác, tính bất biến khi xoay và kích hoạt credential; docstring chứa dòng `coveredIds: CT-ACC-001, QR-SEC-009, CT-STATE-013`.
- `docs/delivery-evidence/j-06/report.md`: Báo cáo bằng chứng thực thi RED/GREEN và các quyết định kỹ thuật của task J-06.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/config/test_j_external_account.py -q -p no:cacheprovider` | 0 | `40 passed in 0.06s` |
| 2 | `git diff --check` | 0 | PASS (không output) |

## Quyết định mặc định (D8)

1. credential_metadata.present = credential_version > 0.
2. rotate và reactivate chỉ đổi credential_version, credential_updated_at, revision (+1) và với reactivate là status=ENABLED; giữ nguyên credential_expires_at, health, quota_observation_ref vì chữ ký hàm không nhận giá trị mới.
3. new_version phải là int thật (bool bị từ chối), now_iso phải là chuỗi không rỗng, vi phạm raise ValueError.
4. reactivate từ trạng thái khác REVOKED raise ValueError; REVOKED→ENABLED không là cạnh của ACCOUNT_EDGES (J-04, D8-J-09), chỉ đi qua reactivate_with_new_credential.
5. account_allows_role so khớp chính xác bằng `in capabilities`, status phải đúng ExternalAccountStatus.ENABLED (fail-closed), ai_role không phải str cho False.
6. module không import gì ngoài status_graph.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt
- PUC-J-03 (cạnh phục hồi cho DEGRADED/INVALID)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, lockfile, fixture, binding.
- Không gọi dịch vụ thật.
- Chưa nối vào application/infrastructure (ngoài owned paths).
