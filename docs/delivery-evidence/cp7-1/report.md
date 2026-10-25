# CP7-1 — Tiền kiểm runtime thật (RG-01)

Ngày đo: 25/10/2026, khoảng 11:40Z, trên máy sản xuất (Windows 10, RTX 4070 SUPER). Chạy trực tiếp trong giai đoạn ổn định hoá (nhánh `stabilize/e2e-20261025`, không qua AI_SETUP; quyết định của user 25/10/2026).

Lệnh: `python -m pytest tests/real/test_cp7_preflight.py -q -p no:cacheprovider` bằng interpreter khoá `.local-tools/runtime/33f06a7a/venv`. Kết quả: 58 passed (51 test đơn vị của `tools/real/cp7_common.py` và `tests/real/conftest.py`, 7 mục đo thật). Trần chi phí: 0 USD, không gọi AI.

## Kết quả

RG-01.ffmpeg_pin: PASS
RG-01.image_digests: PASS
RG-01.loopback_ports: PASS
RG-01.gpu: PASS
RG-01.disk: PASS
RG-01.router_port: PASS
RG-01.secret_scan: PASS

## Chi tiết đo

- ffmpeg_pin: `C:\ffmpeg\bin\ffmpeg.exe` sha256 `f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480`, khớp `tools/runtime/runtime.lock.json` (`pins.ffmpeg`).
- image_digests: container `aiavc-postgres` chạy image sha256 `4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280` (`pins.postgresql_image`); `aiavc-temporal` chạy sha256 `b5ecdb8282bededae2a10c36e8d862e27d0bc2d247fc73c5416025997ab4a1da` (`pins.temporal_server_binary`).
- loopback_ports: 57028 (PostgreSQL), 7233 (Temporal), 8443 (ứng dụng) chỉ lắng nghe trên `127.0.0.1` (netstat TCP và TCPv6).
- gpu: `NVIDIA GeForce RTX 4070 SUPER`, `memory.total` 12282 MiB (ngưỡng 12000 MiB vì thẻ 12 GB danh định báo dưới 12288 MiB).
- disk: ổ chứa thư mục dữ liệu (`C:\`, `%LOCALAPPDATA%\AIAutoVideoCreator`) còn 54,5 GiB, ngưỡng 50 GiB. Ghi chú vận hành: sát ngưỡng; trước đêm chạy 100 video (CP7-11) phải đo dung lượng mỗi video và chuyển thư mục dữ liệu sang ổ khác (D: còn 363 GiB, E: còn 481 GiB) bằng `AIAVC_DATA_DIR` nếu không đủ.
- router_port: TCP `127.0.0.1:20128` (9Router) mở.
- secret_scan: kho DPAPI có alias `drive-primary-oauth` và `router-primary-api-key` (chỉ kiểm tồn tại, không đọc giá trị); tệp báo cáo này không khớp mẫu bí mật nào.

## Ghi chú

- Mã `tools/real/cp7_common.py`, `tests/real/conftest.py`, `tests/real/test_cp7_preflight.py` lấy từ commit của lane CP7-1 trước khi đóng băng (`f416bb7`); bổ sung kiểm alias 9Router vì PP-2 thêm alias này sau khi đặc tả CP7-1 được viết.
- Bộ test `tests/real` chỉ được thu thập khi dòng lệnh nêu đường dẫn đó (`tests/real/conftest.py`), nên lệnh kiểm toàn bộ không chạm tài nguyên thật.
