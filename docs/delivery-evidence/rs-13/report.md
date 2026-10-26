# RS-13: Kiểm đầu cuối mười tài nguyên đọc trên ứng dụng production

## Phạm vi
- Tệp đã tạo: `tests/integration/read_screens/test_rs_13_prod_e2e.py`, `docs/delivery-evidence/rs-13/report.md`.
- Không sửa `src/**`, `tests/integration/adapt/**`, `tests/integration/convergence/**`, `route_catalog.py`, `production.py`: CP-4-WIRING-FIX3 và ADAPT-PROD-FIX3 đã tích hợp trước HEAD 419e081 và là cổng ngoài gói.

## Cách dựng
- `build_production_app` trên CSDL PostgreSQL tạm từ `rs_support.temp_database()` (hai workspace), mẫu `ProductionRuntime`, capability một lần và phiên sao chép từ `test_adapt_prod_app.py` (không import chéo giữa tệp test).
- Dữ liệu thật tạo bằng repository của phân hệ: articles, events, media, artifacts, snapshots (kèm phân tích), story-angles, scripts, cost; chỉ sessions và accounts dùng INSERT SQL tối thiểu vì `src/` chưa có hàm ghi (BL-RS-04). Mỗi tài nguyên có 3 dòng ở workspace 1 và 1 dòng ở workspace 2.

## Lệnh đã chạy
| Lệnh | Mã thoát | Kết quả |
| --- | --- | --- |
| `python -m pytest tests/integration/read_screens/test_rs_13_prod_e2e.py -q -p no:cacheprovider` | 0 | 88 passed, 1 warning in 3.79s |
| `git diff --check` | 0 | 0 cảnh báo, không có khoảng trắng thừa |
| probe `python -c` kiểm `/v1/logs`, `story-angles`, `build_production_app` | 0 | PASS, assert thành công |

## Đối chiếu tiêu chí nghiệm thu
1. Danh sách `?limit=1` trả 200, `items` đúng dữ liệu, `next_cursor` không rỗng; trang kế qua `cursor` trả phần còn lại; đi hết trang bằng limit=1; đủ mười tài nguyên (test `test_first_page_has_one_row_and_a_cursor`, `test_cursor_returns_the_remaining_rows`, `test_walking_with_limit_one_visits_every_row_once`).
2. Chi tiết 200 cho id có thật; 404 `NOT_FOUND` cho id lạ và id workspace khác (id workspace khác được xác nhận có thật qua `compose_read_screens`); `PATCH /v1/media/{id}` 503 `CAPABILITY_UNAVAILABLE`; `GET /v1/logs` 404; `sources` và `hooks` giữ 200 rỗng, không phiên thì 403.
3. Không phản hồi nào chứa canary, khóa cấm mục 4 `plan.md` hay dữ liệu workspace khác; md5 và số hàng 14 bảng nguồn không đổi sau toàn bộ yêu cầu.

## RED và GREEN
- Gói chỉ thêm test kiểm cổng cho mã đã tích hợp (RS-2..RS-12, CP-4-WIRING-FIX3, ADAPT-PROD-FIX3), không có mã sản phẩm mới nên không có bước RED theo oracle riêng; ghi GREEN thật ở bảng trên.

## Giới hạn
- Cần `M2_TEST_PG_DSN`; thiếu thì test dừng `BLOCKED_EXTERNAL`.
- `logs` chưa có nguồn đọc thật (BL-RS-02); sessions và accounts có thể rỗng ở production (BL-RS-04).
- Không dùng mock để tuyên bố PASS cổng ngoài; không có bí mật trong báo cáo.
