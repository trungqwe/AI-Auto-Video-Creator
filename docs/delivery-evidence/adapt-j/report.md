# ADAPT-J: Luồng OAuth một lần qua loopback và token qua broker DPAPI

## 1. Phạm vi và tệp đã sửa
- `src/controlplane/infrastructure/security/oauth_google_loopback.py` (luồng OAuth loopback 127.0.0.1 một lần, PKCE S256, state, scope duy nhất `https://www.googleapis.com/auth/drive.file`, timeout từ cấu hình, đóng cổng ngay khi xong hoặc quá hạn, ghi refresh token vào `SecretStorePort` với `secret_ref` `drive-primary-oauth`)
- `src/controlplane/infrastructure/security/oauth_drive_token.py` (broker access token ngắn hạn `max_ttl_seconds`, đọc refresh token qua DPAPI giải mã, làm mới khi hết hạn, từ chối khi tài khoản hoặc phiên bản secret bị thu hồi/vô hiệu)
- `tests/integration/adapt/j/test_adapt_j_oauth.py` (20 hàm kiểm thử với máy chủ OAuth giả cục bộ, không gọi Google thật, không lộ secret)
- `docs/delivery-evidence/adapt-j/report.md`

## 2. Thiết kế và giả định
- Loopback `127.0.0.1` cổng ngẫu nhiên (`port=0`), PKCE S256 và `state` được kiểm cứng trong `_CapturingFlow`.
- Scope duy nhất `https://www.googleapis.com/auth/drive.file` được kiểm cả ở URL cấp quyền lẫn scope được cấp từ phản hồi token; scope khác bị từ chối fail-closed.
- Cổng loopback đóng ngay khi hoàn tất hoặc quá hạn nhờ `run_local_server` đóng server trong `finally`.
- Tệp cấu hình client JSON bắt buộc phải nằm ngoài cây Git và thông điệp lỗi cố định không lặp lại nội dung tệp hay đường dẫn.
- Refresh token chỉ được ghi qua `SecretStorePort` (`DpapiSecretStore`) với `secret_ref` `drive-primary-oauth`.
- PostgreSQL không bị chạm trong toàn bộ slice (không có mã database; chỉ trả metadata handle gồm `secret_ref`, `version`, `scope`, `fingerprint`).
- Chặn log DEBUG của `oauthlib`, `requests_oauthlib`, `google_auth_oauthlib`, `google.auth`, `urllib3` bằng contextmanager `quiet_oauth_loggers` để ngăn rò rỉ token vào log.
- Gói này không phát bản ghi audit riêng (audit `secret_update` thuộc `UpdateSecretService` của J-10).
- GIẢ ĐỊNH: Các khóa cấu hình `oauth_client_secrets_path` và `oauth_consent_timeout_seconds` chưa có trong `tools/launcher/prod/profile.json` (ngoài owned paths) nên ADAPT-CONFIG hoặc ADAPT-PROD phải bổ sung, không dùng default ẩn.
- GIẢ ĐỊNH: `SecretStorePort` không có API đọc nên `DpapiRefreshTokenReader` dùng `export_vault` kết hợp `dpapi_decrypt` bên trong broker.
- Trạng thái handle (`AccountStatusPort`) do caller cấp, ADAPT-WIRE nối.
- Biến môi trường `OAUTHLIB_INSECURE_TRANSPORT` chỉ được đặt trong test cho máy chủ HTTP giả cục bộ.

## 3. Lệnh đã chạy
Kết quả chạy thực tế trên worktree với interpreter khóa `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe`:

| Bước | Lệnh | Exit code | Kết quả thực tế |
| --- | --- | --- | --- |
| Bước 9 (RED) | python -m pytest tests/integration/adapt/j/test_adapt_j_oauth.py -q -p no:cacheprovider | 1 | 19 failed, 3 passed in 9.40s (19 test hành vi thất bại do NotImplementedError từ stub) |
| Bước 13 (GREEN) | python -m pytest tests/integration/adapt/j/test_adapt_j_oauth.py -q -p no:cacheprovider | 0 | 22 passed in 13.16s (20 hàm test, test 14 sinh 3 ca phân tích trạng thái) |
| Bước 14 | git diff --check | 0 | Sạch, không có lỗi khoảng trắng |
| Bước 15 | probe adapter J (assert 'drive.file' và 'SecretStorePort', không có 'from src.') | 0 | Đạt |
| Bước 17 | git diff --check | 0 | Sạch |

## 4. RED/GREEN
- Chứng kiến RED hợp lệ tại bước 9: Pytest chạy ra 19 failed, 3 passed. Tất cả 19 ca thất bại đều do `NotImplementedError` từ stub của hai mô-đun nguồn (đúng oracle), không có lỗi import hay collection error.
- Chứng kiến GREEN tại bước 13: Toàn bộ 22/22 ca kiểm thử passed, không có skip hay xfail.

## 5. Việc còn lại (backlog, không làm trong slice này)
- `GATE-PERSIST-J` do Control quản lý (PENDING).
- Consent thật với tài khoản thật chỉ kiểm ở CP7-J-01.
- Bổ sung khóa cấu hình `oauth_client_secrets_path` và `oauth_consent_timeout_seconds` vào launcher profile.
- Nối broker vào ADAPT-I (Drive) và ADAPT-WIRE.
