# Báo cáo bằng chứng J-17

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `379c232fd55c67c60dfd23333cdd0e2589cc5d96`
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-17 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/integration/config/test_j_dpapi_secret_store.py -q -p no:cacheprovider` (chạy khi dpapi_secret_store.py là stub raise NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `32 failed, 3 passed in 0.56s`
- Danh sách test PASSED kèm lý do (3 passed do stub đã định nghĩa chữ ký, phương thức callable, không có API đọc plaintext, module không import mạng/logging/src, và docstring khai báo coveredIds/skip guard):
  - `tests/integration/config/test_j_dpapi_secret_store.py::test_store_has_no_read_api_and_matches_constructor_signature` (chữ ký constructor và kiểm tra không có API đọc)
  - `tests/integration/config/test_j_dpapi_secret_store.py::test_module_has_no_network_or_logging_imports` (AST kiểm tra module không import mạng/logging/src)
  - `tests/integration/config/test_j_dpapi_secret_store.py::test_module_declares_covered_ids_and_skip_guard` (docstring khai báo coveredIds và skip guard non-win32)
- Danh sách nhóm test FAILED kèm thông điệp nguyên văn (32 failed):
  - 31 test failed do `NotImplementedError` từ các phương thức stub `put`, `revoke`, `current_version`, hoặc `export_vault`:
    - `test_put_writes_v1_and_v2_in_sha256_directory` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_no_tmp_file_remains_after_put` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_no_canary_bytes_or_names_under_root` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_traversal_refs_stay_under_root[../../escape/ref]` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_traversal_refs_stay_under_root[..\\..\\escape\\ref]` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_traversal_refs_stay_under_root[a/../../b]` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_traversal_refs_stay_under_root[C:/Windows/System32/x]` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_root_is_created_on_first_put` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_distinct_refs_have_independent_versions` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_put_rejects_non_secret_value_and_creates_no_file` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_blank_or_non_str_ref_is_rejected` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_current_version_is_none_for_unknown_ref` (NotImplementedError: J-17 DpapiSecretStore.current_version)
    - `test_current_version_tracks_latest_put` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_revoke_removes_ciphertext_and_writes_marker` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_revoke_is_idempotent` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_revoke_unknown_version_raises_value_error` (NotImplementedError: J-17 DpapiSecretStore.revoke)
    - `test_revoke_rejects_bad_version_types` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_version_is_never_reused_after_revoke` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_failed_encrypt_leaves_no_file` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_failed_replace_leaves_no_tmp_and_no_version` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_export_vault_returns_ciphertext_not_plaintext` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_export_vault_then_broker_returns_value_in_scope_and_expires` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_export_vault_uses_current_version_after_rotation` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_export_after_revoking_latest_falls_back_to_previous_version` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_revoked_secret_is_not_exported_and_broker_denies` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_export_vault_omits_unknown_refs_and_keeps_requested_keys` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_export_vault_rejects_bare_string` (NotImplementedError: J-17 DpapiSecretStore.export_vault)
    - `test_export_vault_accepts_generator` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_traversal_ref_round_trips_through_export_and_broker` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_entropy_binds_ciphertext` (NotImplementedError: J-17 DpapiSecretStore.put)
    - `test_operations_emit_no_log_records` (NotImplementedError: J-17 DpapiSecretStore.put)
  - 1 test failed do `SecretUpdateError: secret_store_failed: NotImplementedError: J-17 DpapiSecretStore.current_version`:
    - `test_update_secret_service_uses_the_store`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED chạy khi dpapi_secret_store.py là stub và fail hợp lệ do NotImplementedError đúng oracle.

## Thay đổi

- `src/controlplane/infrastructure/security/dpapi_secret_store.py`: Hiện thực DpapiSecretStore với các phương thức put, revoke, current_version, export_vault; mã hóa DPAPI bằng dpapi_encrypt của controlplane.security.dpapi; ghi nguyên tử .tmp rồi os.replace; đường dẫn tệp <root>/<sha256 của secret_ref>/v<N>.bin; marker xóa v<N>.revoked; version tăng đơn điệu và không tái sử dụng sau revoke; ref traversal được băm sha256 không bao giờ thoát khỏi root; không có API đọc plaintext.
- `tests/integration/config/test_j_dpapi_secret_store.py`: 35 test chia thành 4 nhóm A, B, C, D kiểm tra toàn diện put, revoke, current_version, export_vault nạp vào CredentialBroker, tích hợp UpdateSecretService, entropy, không log, không network/logging import; skip module-level khi không phải win32; docstring coveredIds: TST-SEC-INV-012, QR-SEC-008.
- `docs/delivery-evidence/j-17/report.md`: Báo cáo bằng chứng chuyển giao này.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/integration/config/test_j_dpapi_secret_store.py -q -p no:cacheprovider` | 0 | `35 passed in 0.47s` |
| 2 | `git diff --check` | 0 | PASS (không output) |
| 3 | `python -c "import pathlib; t = pathlib.Path('tests/integration/config/test_j_dpapi_secret_store.py').read_text(encoding='utf-8'); assert 'coveredIds: TST-SEC-INV-012, QR-SEC-008' in t and 'pytest.skip(' in t and 'win32' in t"` | 0 | PASS (assert qua) |
| 4 | `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/j-17/report.md').read_text(encoding='utf-8'); assert 'RED' in t and 'GREEN' in t and 'Exit code' in t and 'NotImplementedError' in t"` | 0 | PASS (assert qua) |

## Quyết định mặc định (D8)

- Version không tái dùng sau revoke (phiên bản tiếp theo luôn là max(phiên bản đã có) + 1 tính cả .bin và .revoked).
- Revoke version không tồn tại raise ValueError; revoke lặp lại cùng một version là idempotent (không raise, giữ nguyên marker, ciphertext vẫn vắng).
- Marker v<N>.revoked được ghi nguyên tử trước khi xóa ciphertext v<N>.bin để đảm bảo fail-closed nếu tiến trình bị ngắt giữa chừng.
- Export_vault bỏ qua ref chưa có hoặc đã bị revoke hoàn toàn và chỉ trả dict ciphertext bytes; không bao giờ giải mã hoặc trả plaintext.
- Vault chỉ giải mã được bằng CredentialBroker khi entropy=None vì CredentialBroker gọi dpapi_decrypt mặc định không entropy.
- Không khóa liên tiến trình; mô hình một tiến trình ghi một ref.
- Secret_ref được băm sha256 thành tên thư mục con nên đường dẫn đĩa không bao giờ lộ secret_ref và loại bỏ hoàn toàn nguy cơ path traversal.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, lockfile, dpapi.py, broker.py.
- Không gọi dịch vụ thật hay mạng.
- DPAPI chỉ chạy trên Windows; trên nền tảng khác test tự động skip có lý do.
- Không có composition root hay migration thuộc gói hội tụ.
