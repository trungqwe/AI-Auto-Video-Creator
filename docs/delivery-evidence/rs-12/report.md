# RS-12: Bộ ghép compose_read_screens cho mười service

## Phạm vi
Triển khai đúng 3 tệp thuộc owned paths:
- `src/controlplane/infrastructure/read_screens/compose.py`
- `tests/integration/read_screens/test_rs_12_compose.py`
- `docs/delivery-evidence/rs-12/report.md`

## RED
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_12_compose.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe`)
- Mã thoát: 1 (khác 0)
- Dòng tổng kết nguyên văn: `34 failed in 0.80s`
- Mọi lỗi trong lần chạy trên stub rỗng trả `{}` đều là assertion (`set(env.services) == EXPECTED_KEYS`, `assert 'articles' in env.services`, `assert [] == siblings`), không có lỗi import, lỗi cú pháp hay lỗi thu thập test.

## GREEN
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_12_compose.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 0
- Dòng tổng kết nguyên văn: `34 passed in 0.60s`
- Toàn bộ 34 test passed, 0 failed, 0 skipped, 0 error.

## Lệnh kiểm khác
| Lệnh kiểm | Mục đích | Mã thoát |
| --- | --- | --- |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/compose.py').read_text(encoding='utf-8').lower(); assert 'story-angles' in t and 'wiring.production' not in t and 'controlplane.api' not in t and 'from src.' not in t and 'os.environ' not in t, 'RS-12'"` | Quét mã nguồn compose.py bảo đảm có 'story-angles' và không chứa chuỗi cấm (bước 7) | 0 |
| `git diff --check` | Kiểm tra diff và khoảng trắng thừa cuối dòng (bước 9) | 0 |

## Kết luận theo tiêu chí nghiệm thu
1. `compose_read_screens(manager)` trả về dictionary có đúng mười khóa: `articles`, `events`, `media`, `artifacts`, `snapshots`, `story-angles`, `scripts`, `sessions`, `accounts`, `cost`. Khóa `story-angles` sử dụng dấu gạch ngang chuẩn (không phải `story_angles`). Mỗi service được khởi tạo với tham số `connection_scope=manager.borrow_connection`. Chỉ duy nhất service `media` sở hữu phương thức `apply_update` (ném `CapabilityUnavailableError`), chín service còn lại hoàn toàn không có `apply_update`. Khi gọi `fetch_page` trên cơ sở dữ liệu rỗng (`temp_database`), cả mười service đều trả về `Page` rỗng với `next_cursor` là `None`. Khi gọi `fetch_one` với định danh không tồn tại, kết quả trả về `None`.
2. Tệp `compose.py` chỉ import từ đúng mười mô-đun anh em trong cùng gói `read_screens` cùng với `__future__` và `typing`. Hoàn toàn không import `production` (tránh import vòng), không import bất kỳ thứ gì từ `controlplane.api`, không sử dụng tiền tố `from src.` và không sử dụng `os.environ`. Quá trình khởi tạo và dựng bộ ghép gọi `borrow_connection` đúng 0 lần (chỉ lưu tham chiếu hàm mà không mở kết nối).
3. Báo cáo `docs/delivery-evidence/rs-12/report.md` ghi nhận đầy đủ lần chạy RED đúng oracle trên stub trả `{}`, mã thoát thực tế (1), dòng tổng kết nguyên văn (`34 failed in 0.80s`), số lượng test pass ở GREEN (`34 passed in 0.60s`), cùng kết quả các lệnh kiểm bắt buộc.

## Ghi chú
- Bộ ghép chỉ liên kết các service và chuyển giao tham chiếu `borrow_connection`, không tạo kết nối sớm khi chưa có request.
- Tuyệt đối không ghi DSN, mật khẩu hay bất kỳ thông tin bí mật nào trong báo cáo, test hoặc mã nguồn.
