# CP7-2 — Phiên sản xuất thật và bảo mật loopback (RG-01)

Ngày đo: 29/10/2026, trên máy sản xuất (Windows 10). Chạy đo lại trong lane `lane-cp7-2` (worktree của AI_SETUP, hồ sơ `production`, dưới quyền thường).

Lệnh: `node --check tools/real/cp7_browser_probe.js` (mã thoát 0) và `python -m pytest tests/real/test_cp7_session_security.py -q -p no:cacheprovider` bằng interpreter khoá `.local-tools/runtime/1ca840a7/venv`. Kết quả: 10 passed trong 110.33 giây, mã thoát 0. Playwright được nạp từ `src/controlplane/ui/node_modules` nếu có, nếu không thì từ runtime khoá `.local-tools/runtime/1ca840a7/ui/node_modules/playwright` qua biến `CP7_PLAYWRIGHT_DIR`. Test chạy `launcher.py start` thật hai lần (hồ sơ `production`), bắt URL `/launch` qua biến `BROWSER` vào tệp tạm (capability không bao giờ được in), rồi mở phiên bằng Playwright headless. Trần chi phí: 0 USD, không gọi AI.

## Kết quả

RG-01.tls_loopback: PASS
RG-01.launch_one_time: PASS
RG-01.launch_expiry: PASS
RG-01.test_driver_404: PASS
RG-01.host_rejected: PASS
RG-01.origin_rejected: PASS
RG-01.csrf_required: PASS
RG-01.cookie_flags: PASS
RG-01.canary_zero_hits: PASS
RG-01.secret_scan: PASS

## Chi tiết đo

- tls_loopback: bắt tay TLSv1.3 với `127.0.0.1:8443`; chứng chỉ có SAN IP `127.0.0.1` và SAN DNS `localhost`.
- launch_one_time: lần dùng đầu (trình duyệt) chuyển hướng về `/`; dùng lại đúng capability đó trả 403.
- launch_expiry: capability của lần start thứ nhất, không dùng, gọi sau 61 giây trả 403.
- test_driver_404: `GET /test-driver/issue-capability` trả 404 trên hồ sơ production.
- host_rejected: `/launch` với capability thật chưa dùng của lần start thứ hai và Host `evil.example` trả 403; ngay sau đó trình duyệt dùng đúng capability đó với Host đúng vẫn vào được `/`, nên 403 là do Host chứ không do capability. `/v1/jobs` với Host `evil.example` và cookie của phiên vừa mở trả 403.
- origin_rejected: `POST /v1/batches` với Origin `https://evil.example`, cookie và token CSRF hợp lệ, body `{}` trả 403; không lô nào được tạo.
- csrf_required: `POST /v1/batches` có cookie phiên và Origin đúng nhưng thiếu `X-CSRF-Token`, body `{}` trả 403; không lô nào được tạo.
- cookie_flags: `cp_session` HttpOnly, Secure, SameSite=Strict; `csrf_token` Secure, SameSite=Strict.
- canary_zero_hits: chuỗi canary tổng hợp (tiền tố cố định của CP7 cộng một uuid mới mỗi lần chạy) ghi qua `DpapiSecretStore` vào một alias riêng của test, thu hồi trong `finally`; 0 lần khớp trên 10 bề mặt (DOM, HAR, 7 body response của test, log trong thư mục dữ liệu). Ứng dụng không đọc alias của canary, nên canary chỉ chứng minh kho bí mật không bị đổ ra các bề mặt. Vì vậy cùng 10 bề mặt còn được quét bằng hai bí mật thật mà ứng dụng cầm: refresh token Drive (ứng dụng giải mã khi dựng thư mục Drive lúc start) và khoá 9Router. Giá trị lấy qua `CredentialBroker`, chỉ nằm trong bộ nhớ của test; kết quả 0 lần khớp. Giới hạn: HAR chỉ chứa body của response đã kết thúc, không chứa payload của luồng SSE còn mở.
- secret_scan: `scan_secrets` của CP7-1 cho 0 lần khớp trên 11 bề mặt (10 bề mặt trên và tệp báo cáo này).

## Ghi chú

- Test dừng ứng dụng bằng `python tools/launcher/launcher.py stop` trong `finally` của fixture và kiểm cổng `127.0.0.1:8443` đã đóng; không có launcher nào còn chạy sau test.
- Ba lỗi hạ tầng phát hiện khi dựng slice này đã sửa trên nhánh ổn định hoá, kèm test: `launcher stop` treo khi trình duyệt giữ SSE (`b0bf81d` cho máy chủ production, `8bb5768` cho mọi nơi tạo máy chủ uvicorn: hạn tắt êm 10 giây); namespace Temporal `default` chưa đăng ký trên image server 1.31.2 (`2f7e847`); `worker.stop()` chờ đủ 60 giây vì future bị bỏ rơi khi loop của worker đã dừng (`6686c58`).
- Probe trình duyệt không chờ `networkidle`, vì UI giữ một `EventSource` mở suốt phiên. Probe chờ trang nạp, chờ tiêu đề `h1.brand-title`, rồi chờ thêm 3 giây để các lệnh gọi API đầu tiên vào HAR.
- DOM, HAR và cookie chỉ nằm trong thư mục tạm ngoài cây Git, và bị xoá khi test xong.
