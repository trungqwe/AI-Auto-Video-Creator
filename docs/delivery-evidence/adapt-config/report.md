# Báo cáo ADAPT-CONFIG

## Tệp đã tạo

- `tools/launcher/prod/profile.json`: Hồ sơ cấu hình production gồm 78 tham số thuộc 19 nhóm, mỗi tham số chứa đầy đủ `value`, `reason` và `basis` (`DECIDED` hoặc `CONSERVATIVE_DEFAULT`), không có giá trị `null` và không chứa khóa nhạy cảm.
- `tools/launcher/prod/sources.json`: Danh mục 7 nguồn tin RSS công khai cơ sở thuộc Tier 1 và Tier 2, toàn bộ URL sử dụng giao thức HTTPS và cờ `enabled` là true.
- `tools/launcher/prod/hooks.json`: Khai báo 5 hook hình (`vh-01` đến `vh-05`), 5 hook âm thanh (`ah-01` đến `ah-05`) và 12 ảnh nền seed (`bg-01` đến `bg-12`) kèm công thức sinh `recipe_templates`, `sha256` là `null` với trạng thái `PENDING_GENERATION`.
- `tools/launcher/prod/model-weights.lock.json`: Khóa trọng số mô hình cho 6 tệp (Kokoro v1.0 và faster-whisper small.en) với URL HTTPS cố định, `sha256` là `null` kèm trạng thái `BLOCKED`.
- `tests/integration/adapt/config/test_adapt_config_profile.py`: Bộ kiểm thử tích hợp sử dụng thư viện chuẩn Python (stdlib) kiểm tra toàn diện cấu trúc, mã hóa UTF-8 không BOM, tính nhạy cảm, số lượng tham số, preset, route AI, nguồn RSS, hook và khóa trọng số.
- `docs/delivery-evidence/adapt-config/report.md`: Báo cáo nghiệm thu chi tiết của task ADAPT-CONFIG.

## Lệnh đã chạy

1. `git diff --check`
   - Exit code: 0
   - Kết quả: Không có lỗi định dạng hay khoảng trắng thừa cuối dòng.

2. `python -m pytest tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider`
   - Exit code: 0
   - Kết quả: 11 passed in 0.04s.

3. `python -c "import json, pathlib; d = pathlib.Path('tools/launcher/prod'); x = [json.loads((d / n).read_text(encoding='utf-8')) for n in ['profile.json', 'sources.json', 'hooks.json', 'model-weights.lock.json']]; assert 'Asia/Ho_Chi_Minh' in (d / 'profile.json').read_text(encoding='utf-8'), 'profile'"`
   - Exit code: 0
   - Kết quả: Đọc thành công 4 tệp cấu hình bằng UTF-8, assertion hợp lệ xác nhận chuỗi 'Asia/Ho_Chi_Minh' trong profile.json.

## Mục mở

- (a) `sha256` của hook và ảnh nền hiện là `null` kèm trạng thái `PENDING_GENERATION`, chờ nhiệm vụ ADAPT-SEED sinh tài sản thật rồi Control ghi lại giá trị hash thực tế, không bịa hash.
- (b) `sha256` của các tệp trọng số hiện là `null` kèm trạng thái `BLOCKED` (theo OI-ADAPT-06), commit Hugging Face của faster-whisper small.en là `null` do Control điền khi ghim và danh sách tệp mô hình whisper cần Control xác minh lại từ kho lưu trữ.
- (c) Bảy nguồn tin RSS công khai cơ sở chưa được kiểm tra độ sống trực tiếp (CP7-ADAPT-07) do kế hoạch không gọi mạng ngoài.
- (d) `route_endpoint` của 9Router đang ở mức `CONSERVATIVE_DEFAULT` chờ Control xác nhận chính thức ở CP7 (theo OI-ADAPT-05).
- (e) Màu sắc của năm preset là các giá trị chọn trước và sẽ được người dùng duyệt tại bước nghiệm thu, phông chữ Arial theo OI-ADAPT-08.
- (f) Không có tham số nào được gán `basis` là `MEASURED` vì hệ thống chưa thực hiện các phép đo thực tế trên máy này.

## Phạm vi

- Xác nhận chỉ chỉnh sửa và tạo mới trong phạm vi các tệp thuộc danh sách owned paths đã được giao (`tools/launcher/prod/profile.json`, `tools/launcher/prod/sources.json`, `tools/launcher/prod/hooks.json`, `tools/launcher/prod/model-weights.lock.json`, `tests/integration/adapt/config/test_adapt_config_profile.py`, `docs/delivery-evidence/adapt-config/report.md`).
- Không tạo bất kỳ tệp media nhị phân (`.mp4`, `.wav`, `.png`, `.jpg`, `.mp3`) hoặc tệp trọng số (`.onnx`, `.bin`, `.safetensors`) nào trong cây Git.
- Không thực hiện gọi mạng ra bên ngoài, không gọi RSS thật, không gọi 9Router thật và không gọi Google Drive thật.
