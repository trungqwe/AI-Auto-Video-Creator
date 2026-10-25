# Báo cáo bằng chứng chuyển giao: PP-3

## 1. Phạm vi thực hiện
Các tệp đã được tạo mới và triển khai trong phạm vi quyền sở hữu (`owned paths`):
- `src/controlplane/infrastructure/production_ports/drive_token.py`: Triển khai cổng trạng thái `VaultAccountStatusPort(store)` cài đặt `AccountStatusPort` và hàm khởi tạo `build_drive_token_broker(client_secrets_path, max_ttl_seconds, store, clock)`. Mô-đun chỉ ráp lại `DriveAccessTokenBroker`, `DpapiRefreshTokenReader(store)` và `VaultAccountStatusPort(store)` có sẵn; tuyệt đối không viết lại luồng đổi token, không chạm CSDL, không đọc biến môi trường, không ghi token ra đĩa hay log, và không sửa đổi `oauth_drive_token.py`.
- `tests/integration/prod_ports/test_pp_3_drive_token.py`: Bộ kiểm thử tích hợp toàn diện gồm 25 ca kiểm thử bao quát toàn bộ hành vi của `VaultAccountStatusPort` và `build_drive_token_broker`. Sử dụng máy chủ HTTP loopback (`127.0.0.1`) trong tiến trình làm `token_uri` của tệp `oauth-client.json` tạm (trong `tmp_path`, ngoài cây Git), dùng canary tổng hợp, xác minh caching trong TTL, xử lý lỗi từ chối/thu hồi alias, lỗi máy chủ 400, kiểm tra tham số phương thức/tài khoản, kiểm chứng không rò rỉ canary trong `repr`, `stdout`, `stderr`, `log`, tệp trên đĩa và quét tĩnh mã nguồn không chứa chuỗi cấm.
- `docs/delivery-evidence/pp-3/report.md`: Báo cáo bằng chứng chuyển giao này.

## 2. Bằng chứng RED hợp lệ (Bước 6)
Tại Bước 6, sau khi tạo khung tạm (stub) ném `NotImplementedError` tại `drive_token.py` và hoàn thành bộ kiểm thử `test_pp_3_drive_token.py`, lệnh pytest được thực thi với Python interpreter đã khóa để chứng kiến oracle RED hợp lệ:
```text
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_status_is_enabled_when_account_matches_and_alias_exists
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_status_is_revoked_when_alias_is_missing
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_status_is_revoked_after_alias_revoke
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_status_is_revoked_for_other_account_even_with_alias[other-account]
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_status_is_revoked_for_other_account_even_with_alias[]
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_status_is_revoked_for_other_account_even_with_alias[router-primary]
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_status_is_revoked_for_other_account_even_with_alias[DRIVE-PRIMARY]
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_status_reads_only_current_version_from_the_store
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_builder_returns_drive_access_token_broker
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_second_acquire_within_ttl_reuses_token_then_refreshes_after_ttl
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_missing_alias_is_denied_without_server_call
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_revoked_alias_is_denied_without_server_call
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_server_400_raises_refresh_error_without_secrets
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_unknown_method_or_account_raises_value_error[oauth-drive-primary]
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_unknown_method_or_account_raises_value_error[-drive-primary]
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_unknown_method_or_account_raises_value_error[env_var-drive-primary]
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_unknown_method_or_account_raises_value_error[secret_broker_handle-router-primary]
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_unknown_method_or_account_raises_value_error[secret_broker_handle-]
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_unknown_method_or_account_raises_value_error[secret_broker_handle-None]
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_builder_rejects_bad_ttl[0]
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_builder_rejects_bad_ttl[-5]
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_builder_rejects_bad_ttl[True]
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_builder_rejects_bad_ttl[60]
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_no_canary_in_repr_stdout_stderr_log_or_disk
FAILED tests/integration/prod_ports/test_pp_3_drive_token.py::test_source_has_no_forbidden_text
25 failed in 9.57s
```
- **Exit Code:** `1`
- **Xác thực Oracle RED:**
  * 24 ca kiểm thử thất bại do `NotImplementedError` từ khung tạm `VaultAccountStatusPort.account_status` và `build_drive_token_broker`.
  * 1 ca kiểm thử `test_source_has_no_forbidden_text` thất bại do `AssertionError` vì khung tạm chưa ráp nối các lớp production.
  * Hoàn toàn không có lỗi collection, `ImportError` hay `ModuleNotFoundError`.

## 3. Bằng chứng GREEN và kết quả các lệnh kiểm tra
Bảng tổng hợp kết quả thực thi các lệnh kiểm tra bắt buộc:

| Bước / Lệnh | Lệnh thực thi | Exit Code | Dòng tóm tắt nguyên văn |
| :--- | :--- | :--- | :--- |
| Lệnh kiểm 1 (Bước 11) | `git diff --check` | 0 | Thoát 0, không có lỗi khoảng trắng thừa hay định dạng |
| Lệnh kiểm 2 (Bước 8) | `python -m pytest tests/integration/prod_ports/test_pp_3_drive_token.py -q -p no:cacheprovider` | 0 | `25 passed in 8.74s` |
| Lệnh kiểm 3 (Bước 9) | `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/drive_token.py').read_text(encoding='utf-8').lower(); assert 'driveaccesstokenbroker' in t and 'from src.' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-3'"` | 0 | Thoát 0, probe tĩnh đạt chuẩn, không có AssertionError |

## 4. Ánh xạ các yêu cầu nghiệm thu (Acceptance Criteria)

### Yêu cầu 1: Cổng trạng thái VaultAccountStatusPort trên kho DPAPI
- **Yêu cầu:** `VaultAccountStatusPort(store)` cài `AccountStatusPort`: `account_status(account_ref)` trả `ExternalAccountStatus.ENABLED` khi `account_ref == ACCOUNT_REF` và `store.current_version(SECRET_REF)` khác `None`, ngược lại `REVOKED`; không đọc CSDL.
- **Các test chứng minh:**
  * `test_status_is_enabled_when_account_matches_and_alias_exists`: Xác nhận trả về `ExternalAccountStatus.ENABLED` khi `account_ref == ACCOUNT_REF` (`drive-primary`) và alias `drive-primary-oauth` tồn tại trong kho.
  * `test_status_is_revoked_when_alias_is_missing`: Xác nhận trả về `ExternalAccountStatus.REVOKED` khi alias chưa từng được thêm vào kho.
  * `test_status_is_revoked_after_alias_revoke`: Xác nhận trả về `ExternalAccountStatus.REVOKED` sau khi alias bị thu hồi trong kho.
  * `test_status_is_revoked_for_other_account_even_with_alias` (4 ca tham số hóa: `'other-account'`, `''`, `'router-primary'`, `'DRIVE-PRIMARY'`): Xác nhận bất kỳ `account_ref` nào khác `drive-primary` đều trả về `REVOKED`, ngay cả khi alias đang tồn tại.
  * `test_status_reads_only_current_version_from_the_store`: Xác nhận `VaultAccountStatusPort` chỉ gọi duy nhất `store.current_version(SECRET_REF)`, không gọi bất kỳ phương thức CSDL hay nguồn ngoại lai nào khác.
- **Phản ví dụ đã loại trừ:** Đọc trạng thái từ CSDL; bỏ kiểm `account_ref`.

### Yêu cầu 2: Hàm khởi tạo build_drive_token_broker và vận hành an toàn
- **Yêu cầu:** `build_drive_token_broker(client_secrets_path, max_ttl_seconds, store, clock)` trả `DriveAccessTokenBroker` ráp từ `DpapiRefreshTokenReader(store)`, cổng trạng thái trên và `clock`; tái dùng lớp có sẵn, không viết lại luồng đổi token, không sửa `oauth_drive_token.py`. Chỉ nhận `secret_broker_handle` và `drive-primary`; lỗi không chứa token.
- **Các test chứng minh:**
  * `test_builder_returns_drive_access_token_broker`: Xác nhận kết quả trả về là một thực thể `DriveAccessTokenBroker`.
  * `test_second_acquire_within_ttl_reuses_token_then_refreshes_after_ttl`: Xác minh hai lần gọi `acquire` trong TTL chỉ gọi máy chủ loopback một lần (tái sử dụng token trong bộ nhớ), qua TTL thì gọi lại máy chủ lần thứ hai.
  * `test_missing_alias_is_denied_without_server_call`: Xác minh khi kho thiếu alias thì ném `DriveTokenDeniedError` và máy chủ nhận 0 lượt gọi.
  * `test_revoked_alias_is_denied_without_server_call`: Xác minh khi alias bị thu hồi thì ném `DriveTokenDeniedError` và máy chủ nhận 0 lượt gọi.
  * `test_server_400_raises_refresh_error_without_secrets`: Xác minh khi máy chủ trả về mã 400 thì ném `DriveTokenRefreshError` và thông điệp lỗi hoàn toàn không chứa canary (`REFRESH`, `CLIENT_SECRET`, `ERRBODY`).
  * `test_unknown_method_or_account_raises_value_error` (6 ca tham số hóa): Xác minh phương thức hoặc `account_ref` lạ ném `ValueError`, không gọi máy chủ và không làm rò rỉ canary.
  * `test_builder_rejects_bad_ttl` (4 ca tham số hóa: `0`, `-5`, `True`, `'60'`): Xác minh giá trị TTL không hợp lệ bị từ chối bằng `ValueError`.
  * `test_no_canary_in_repr_stdout_stderr_log_or_disk`: Xác nhận canary xuất hiện 0 lần trong `caplog`, `capsys`, `repr`, `str` và không có bất kỳ tệp nào trên đĩa bị ghi đệm token.
- **Phản ví dụ đã loại trừ:** Đọc token từ biến môi trường; ghi đệm token ra đĩa; sửa `oauth_drive_token.py`.

### Yêu cầu 3: Độ sạch của mã nguồn và không có chuỗi cấm
- **Yêu cầu:** Mã nguồn `drive_token.py` không có `from src.`, `mock`, `fake`, `os.environ`; có `DriveAccessTokenBroker`.
- **Các test chứng minh:**
  * `test_source_has_no_forbidden_text`: Quét toàn văn bản nguồn của `drive_token.py`, xác nhận không chứa bất kỳ chuỗi cấm nào (`from src.`, `mock`, `fake`, `os.environ`, `getenv`, `psycopg`, `sqlalchemy`, `subprocess`, `google.auth`, `requests`, `urllib`, `open(`, `write_`), đồng thời có đủ các biểu tượng bắt buộc `driveaccesstokenbroker`, `dpapirefreshtokenreader`, `vaultaccountstatusport`.
  * Lệnh kiểm probe tĩnh bắt buộc thoát 0 không có `AssertionError`.
- **Phản ví dụ đã loại trừ:** Nhánh giả hoặc biến môi trường trong mã production.

## 5. Giới hạn và an toàn (Limitations)
- Bộ kiểm thử sử dụng máy chủ HTTP loopback (`127.0.0.1`) cục bộ mô phỏng máy chủ cấp token OAuth thay vì gọi trực tiếp Google OAuth; không kết nối mạng internet bên ngoài.
- Canary và refresh token trong kiểm thử hoàn toàn là chuỗi tổng hợp ngẫu nhiên trong thư mục tạm `tmp_path`, không truy cập và không lưu trữ bất kỳ bí mật thật nào.
- Tuyệt đối không chỉnh sửa `src/controlplane/infrastructure/security/oauth_drive_token.py`.
- Không thực hiện chạy full regression suite; tuân thủ nghiêm ngặt nguyên tắc kỷ luật thực thi mục tiêu (`targetedCommand`).
- Không thực hiện `git push` hay `git merge`, không chạm vào nhánh `main` hay `backup`.
- Cổng kích hoạt sản xuất thực tế vẫn giữ nguyên trạng thái khóa an toàn (`PRODUCTION_ACTIVATION_BLOCKED`).
