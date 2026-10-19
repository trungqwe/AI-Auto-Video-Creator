# Báo cáo bằng chứng J-11

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `c5e236f22f8879070c66bdf088230f05d95ef78a`
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-11 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/security/test_j_credential_issuance.py -q -p no:cacheprovider` (chạy khi credential_issuance.py là stub)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `49 failed, 2 passed in 0.47s`
- Các test FAILED kèm thông điệp nguyên văn (NotImplementedError: J-11 issue):
  - `tests/unit/security/test_j_credential_issuance.py::test_grant_is_frozen FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_canary_token_is_absent_from_every_rendering FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_issue_sets_expiry_and_bindings FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_issue_without_bindings_leaves_refs_none FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_grant_ids_are_unique FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_ttl_at_ceiling_is_allowed FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_ttl_outside_ceiling_is_denied_without_minting[0] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_ttl_outside_ceiling_is_denied_without_minting[-1] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_ttl_outside_ceiling_is_denied_without_minting[601] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_ttl_outside_ceiling_is_denied_without_minting[1000000000] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_ttl_outside_ceiling_is_denied_without_minting[True] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_ttl_outside_ceiling_is_denied_without_minting[1.5] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_ttl_outside_ceiling_is_denied_without_minting[60] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_ttl_outside_ceiling_is_denied_without_minting[None] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_now_without_timezone_is_denied[now0] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_now_without_timezone_is_denied[2026-10-20T12:00:00Z] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_now_without_timezone_is_denied[None] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_desktop_with_oauth_refresh_is_denied FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_desktop_without_refresh_is_issued FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_permissions_given_as_plain_string_are_denied FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_account_not_enabled_is_denied[DISABLED] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_account_not_enabled_is_denied[DEGRADED] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_account_not_enabled_is_denied[INVALID] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_account_not_enabled_is_denied[REVOKED] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_account_of_another_workspace_is_denied FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_capability_outside_account_is_denied[ai.generate] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_capability_outside_account_is_denied[*] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_capability_outside_account_is_denied[drive] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_capability_outside_account_is_denied[] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_minter_must_return_secret_value FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_issuer_requires_positive_int_ceiling[0] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_issuer_requires_positive_int_ceiling[-5] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_issuer_requires_positive_int_ceiling[True] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_issuer_requires_positive_int_ceiling[1.5] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_issuer_requires_positive_int_ceiling[None] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_valid_grant_passes_and_reads_live_revocation FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_expired_grant_raises[300] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_expired_grant_raises[301] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_expired_grant_raises[86400] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_revoke_after_issue_wins_over_stale_snapshot_before_expiry FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_account_in_dead_status_raises_revoked[REVOKED] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_account_in_dead_status_raises_revoked[INVALID] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_account_in_dead_status_raises_revoked[DISABLED] FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_degraded_account_still_validates FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_operation_mismatch_raises_binding_error FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_unbound_grant_accepts_any_operation FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_grant_for_other_account_or_workspace_raises_binding_error FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_naive_now_in_validate_raises_validation_error FAILED (NotImplementedError: J-11 issue)`
  - `tests/unit/security/test_j_credential_issuance.py::test_errors_carry_no_credential_material FAILED (NotImplementedError: J-11 issue)`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED chạy khi credential_issuance.py là stub và fail hợp lệ do NotImplementedError đúng oracle.

## Thay đổi

- `src/controlplane/application/config_security/credential_issuance.py`: CredentialGrant frozen 12 trường không chứa token/secret; IssuedCredential(grant, token: SecretValue) với repr=False; port TokenMinterPort và RevocationPort; CredentialIssuer với trần TTL bắt buộc (D8-J-08), từ chối account không ENABLED, workspace lệch, capability ngoài account, desktop nhận refresh token; validate_grant kiểm tra múi giờ, account_ref/workspace_id binding, trạng thái dead (REVOKED/INVALID/DISABLED), revocation_version từ port thắng snapshot cũ (CT-SEC-003 điều 7), hết hạn now >= expires_at, operation_ref binding; mọi exception kế thừa CredentialError và không chứa secret material.
- `tests/unit/security/test_j_credential_issuance.py`: 51 test bao phủ toàn bộ yêu cầu: CredentialGrant frozen và không có trường token/secret; IssuedCredential giấu canary token khỏi repr/str; issue gán đúng expiry, binding, unique ID; trần TTL (từ chối số <= 0, > trần, bool, float, chuỗi, None); kiểm tra timezone-aware cho now; từ chối desktop kèm oauth.refresh; từ chối account không ENABLED, sai workspace, capability ngoài danh mục; từ chối minter không trả SecretValue; validate_grant chấp nhận grant hợp lệ và đọc live revocation_version; hết hạn sinh GrantExpiredError; revoke sau issue thắng snapshot cũ sinh GrantRevokedError; account chết sinh GrantRevokedError; DEGRADED vẫn validate được; binding operation_ref lệch sinh GrantBindingError; thông điệp ngoại lệ không rò rỉ token canary; docstring có dòng coveredIds: CT-SEC-002, CT-SEC-003, TST-SEC-INV-012, QR-SEC-009.
- `docs/delivery-evidence/j-11/report.md`: Báo cáo bằng chứng thực thi RED/GREEN và các quyết định kỹ thuật của slice J-11.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/security/test_j_credential_issuance.py -q -p no:cacheprovider` | 0 | `51 passed in 0.12s` |
| 2 | `git diff --check` | 0 | PASS (không output) |

## Quyết định mặc định (D8)

1. `issue` thêm tham số keyword-only tùy chọn `workspace_id` vì chữ ký không có workspace nào khác để đối chiếu `workspace khác`, workspace của grant luôn lấy từ account.
2. `account_ref` của grant là `external_account_id`.
3. DEGRADED vẫn validate được, chỉ REVOKED/INVALID/DISABLED là chết, nhưng issue chỉ cho ENABLED.
4. grant có operation_ref mà caller không truyền hoặc truyền khác thì GrantBindingError, grant không ràng buộc operation chấp nhận mọi operation.
5. thứ tự kiểm validate: múi giờ, binding account/workspace, trạng thái account, revocation_version, hết hạn (now >= expires_at), operation.
6. minter phải trả SecretValue, trả kiểu khác bị từ chối.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- CP7-J-01
- CP7-J-02
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, lockfile, fixture, binding.
- Không gọi dịch vụ thật; minter và revocation chỉ là fake trong test.
