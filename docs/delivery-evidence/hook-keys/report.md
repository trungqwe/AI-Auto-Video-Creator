# HOOK-KEYS — Báo cáo giao hàng

Mã gói: HOOK-KEYS
Nhóm lỗi: OI-CP7-11-Q4

Sản phẩm chưa có lệnh nhập khoá Pixabay và Freesound vào kho DPAPI của launcher (D1, D2 ngày 02/11/2026) và chưa có bộ đọc khoá cho client kho miễn phí.

## Tệp đã thêm

Ba tệp mã nguồn và kiểm thử đã được chép nguyên văn bằng Copy-Item từ D:/AIAVC_IMGPROTO/ref/hook-keys/, khớp hoàn toàn mã băm SHA-256 tham chiếu (64 ký tự), không sửa ports.json, router_key_entry.py, set_router_key.py, credentials.py, dpapi_secret_store.py và không thêm bất kỳ thư viện nào:
- `src/controlplane/infrastructure/production_ports/stock_key_entry.py`: SHA-256 `82da54fe20d8e5055c023afbde934ab069a2799e528a9763a695b649c2f4be6b`
- `tools/launcher/prod/set_stock_key.py`: SHA-256 `8170f8fba563f8320ed0247ea792556a14c763861e22786b4e86b3c5edb78551`
- `tests/integration/prod_ports/test_hook_keys.py`: SHA-256 `0097e4169afe308cd052023b589b88bafae4cfae6d2f3be64164eb70efd02d40`

## Lệnh kiểm đã chạy

Biến môi trường gốc tạm pytest đã đặt:
`PYTEST_DEBUG_TEMPROOT=C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\HOOK-KEYS-implement-r0-ac1b5c0961`

Bảng kết quả các lệnh kiểm tra:

| Bước | Lệnh kiểm | Mã thoát | Dòng tổng kết nguyên văn / Kết quả |
| :--- | :--- | :--- | :--- |
| Bước 2 | `python -m pytest tests/integration/prod_ports/test_hook_keys.py -q -p no:cacheprovider` | 2 | `1 error in 0.26s` (`ModuleNotFoundError: No module named 'controlplane.infrastructure.production_ports.stock_key_entry'`) |
| Bước 5 | `python -m pytest tests/integration/prod_ports/test_hook_keys.py -q -p no:cacheprovider` | 0 | `21 passed in 1.17s` |
| Bước 6 | `python -m pytest tests/integration/prod_ports/test_pp_2_credentials.py tests/integration/config/test_j_dpapi_secret_store.py -q -p no:cacheprovider` | 0 | `126 passed in 1.80s` |
| Bước 7 | Probe so khớp SHA-256 với bản tham chiếu `D:/AIAVC_IMGPROTO/ref/hook-keys` | 0 | Không có lỗi assertion, khớp SHA-256 |
| Bước 8 | Probe kiểm tra cấu trúc `stock_key_entry.py` và `set_stock_key.py` | 0 | Không có lỗi assertion, đầy đủ hàm và hằng, không print/logging/argparse |
| Bước 9 | Probe kiểm tra test bắt buộc và `coveredIds: CT-SEC-001` | 0 | Không có lỗi assertion, đầy đủ 4 hàm test bắt buộc và docstring coveredIds |
| Bước 10 | Probe kiểm tra ký tự byte CR (CRLF) | 0 | Không có byte CR trong ba tệp |
| Bước 11 | Probe kiểm tra bố cục CP2A-LAYOUT (package-dir, pythonpath, không import tiền tố src.) | 0 | Không có lỗi bố cục |
| Bước 14 | `git diff --check` | 0 | Không có lỗi khoảng trắng thừa |

## Số ca hỏng trước và đạt sau

- Trước (Bước 2): Thất bại ở bước thu thập kiểm thử do chưa có mã nguồn module `stock_key_entry` (`ModuleNotFoundError`), 0 ca đạt. Mã thoát: 2, dòng tổng kết nguyên văn: `1 error in 0.26s`.
- Sau (Bước 5): Toàn bộ 21 ca kiểm thử mới đạt thành công. Mã thoát: 0, dòng tổng kết nguyên văn: `21 passed in 1.17s`.
- Hồi quy (Bước 6): Nhóm kiểm thử hồi quy của PP-2 và kho DPAPI đạt tuyệt đối. Mã thoát: 0, dòng tổng kết nguyên văn: `126 passed in 1.80s`.

## Lệnh nhập khoá đã thử với khoá giả

Quy định kỷ luật của lệnh kiểm không cho phép chạy trực tiếp `python <tệp>.py`, do đó lệnh `set_stock_key.py` đã được kiểm thử toàn diện thông qua hàm `main()` có tiêm `ask/stdin/out/err` trong bộ test `test_hook_keys.py` với khoá giả canary `Zq7canaryKEY0123456789abcdef` (không phải khoá thật), trên kho `DpapiSecretStore` thật được khởi tạo trong `tmp_path` với `AIAVC_DATA_DIR` trỏ tới `tmp_path`:
- Chế độ mặc định `getpass`: kiểm thử qua `test_script_uses_getpass_by_default`, lời nhắc không chứa khoá.
- Chế độ đọc qua `--stdin` và `--from-file <tệp>`: kiểm thử qua `test_script_reads_the_named_file_and_stdin`.
- Chế độ trạng thái `--status`: in `freesound: stock-freesound-api-key v1` và `pixabay: stock-pixabay-api-key v1`, chỉ đọc phiên bản, không đọc hay in giá trị khoá.
- Trường hợp khoá đặt trực tiếp trên argv: lệnh trả về mã thoát `EXIT_USAGE = 2`, không in khoá và không lưu vào kho bí mật (`test_script_never_takes_or_echoes_a_key_from_argv`).
- Trường hợp tệp khoá sai định dạng: trả về mã thoát 1 và thông báo lỗi an toàn không làm lộ nội dung tệp (`test_script_reports_a_bad_file_without_its_content`).
- Tuyệt đối không dán, lưu trữ hoặc in bất kỳ khoá thật nào; không đọc tệp khoá của user.

## Giới hạn

- Gói này chỉ chịu trách nhiệm nhập và đọc khoá từ kho DPAPI của launcher; client tìm kiếm thuộc gói HOOK-STOCK, quy trình thu thập nội dung thuộc gói HOOK-HARVEST.
- Kho tài nguyên Pexels chưa được gắn (theo quyết định D1 sẽ gắn sau khi người dùng yêu cầu); việc thêm kho mới trong tương lai chỉ cần thêm một mục vào từ điển `STOCK_SECRET_REFS`.
- Lệnh nhập khoá được thiết kế để chạy dưới quyền người dùng thông thường, không chạy từ phiên nâng cao (elevated).
- Người dùng tự chạy lệnh để nhập khoá thật của mình; Control không đọc và không lưu tệp khoá của người dùng.

## OI-CP7-11-Q4

Nhóm lỗi OI-CP7-11-Q4 phản ánh việc thiếu cơ chế quản lý và cấu hình khoá API cho các kho tài nguyên đa phương tiện miễn phí (Pixabay và Freesound) phục vụ tạo video hook. Gói HOOK-KEYS xử lý dứt điểm phần gốc của nhóm lỗi này ở tầng hạ tầng bằng cách cung cấp module `stock_key_entry` và công cụ dòng lệnh an toàn `set_stock_key` để nhập và đọc khoá qua kho DPAPI. Phần còn lại của chuỗi tính năng liên quan đến việc tiêu thụ khoá này sẽ được chuyển giao và xử lý tiếp ở các gói chuyên trách tiếp theo:
- Gói HOOK-STOCK: Triển khai client tìm kiếm kho tài nguyên sử dụng khoá đã cấu hình.
- Gói HOOK-HARVEST: Quản lý quy trình tải và thu thập video/âm thanh từ kết quả tìm kiếm.
