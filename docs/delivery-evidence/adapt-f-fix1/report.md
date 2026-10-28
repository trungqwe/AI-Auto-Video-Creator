# Báo cáo chuyển giao: ADAPT-F-FIX1

## 1. Tóm tắt
Gói ADAPT-F-FIX1 xử lý nhóm lỗi R12: test `tests/integration/adapt/f/test_adapt_f_render.py:182` khẳng định graph `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30`, trong khi lệnh render gộp (F-10-FIX1, `src/render/domain/render_command.py:253-254`) chuẩn hoá mỗi đầu vào bằng `scale=W:H:force_original_aspect_ratio=increase,crop=W:H,setsar=1,fps=F,format=P` trước khi concat.

## 2. Tệp đã sửa
- `tests/integration/adapt/f/test_adapt_f_render.py` (chỉ sửa dòng 182, thêm `setsar=1,`)
- `docs/delivery-evidence/adapt-f-fix1/report.md` (tệp mới)
Không sửa mã production nào (không sửa `src/**` hay `migrations/**`).

## 3. Lệnh đã chạy
| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `git diff --check` | 0 | Đạt (exit code 0, không có khoảng trắng thừa) |
| `python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider` | 0 | 54 passed in 3.78s |
| `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/adapt-f-fix1/report.md').read_text(encoding='utf-8'); assert 'ADAPT-F-FIX1' in t and 'R12' in t, 'report'"` | 0 | Đạt (exit code 0, chứa ADAPT-F-FIX1 và R12) |

## 4. Quyết định
- Giữ nguyên mọi khẳng định khác của test (encoder `h264_nvenc`, các tham số nvenc, aac, `subtitles=filename=`, không chứa `ass=filename=`, tệp `.part`);
- Không nới lỏng khẳng định filter graph thành kiểm tra `scale=` chung chung;
- Không sửa mã production `src/render/domain/render_command.py`.

## 5. Mục mở
- Lỗi test đã được Reviewer F-10-FIX1 ghi nhận là MINOR;
- Các phần lỗi R9 (lệnh render) và R10 (phân giải hook, thumbnail) còn lại thuộc các gói công việc khác nếu có.
