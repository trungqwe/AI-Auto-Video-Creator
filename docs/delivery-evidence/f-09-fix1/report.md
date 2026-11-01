# Báo cáo bằng chứng F-09-FIX1

## 1. Nhóm lỗi

- Mã gói: F-09-FIX1. Nhóm lỗi: R37.
- R37: dòng ASS rộng hơn safe area bị libass cắt ở mép khung vì `render_ass` ghi `WrapStyle: 2` (libass không tự xuống dòng, `MarginL`/`MarginR` chỉ dùng để canh giữa).
- Disclosure RG-09 dài 95/131/90 ký tự, rộng tự nhiên 1658/2251/1503 px nên bị cắt hai mép khung 1080 px; dòng karaoke viết hoa hết rộng 1115 px.
- Cách sửa: `render_ass` ghi `WrapStyle: 0` để libass ngắt dòng thông minh trong `MarginL`/`MarginR`. Không đổi cỡ chữ, margin, số từ, số ký tự, chữ Disclosure.

## 2. Tệp đã sửa

- `src/render/domain/karaoke_plan.py`: đổi duy nhất `WrapStyle: 2` thành `WrapStyle: 0` trong `render_ass`.
- `tests/unit/render/test_f09_karaoke_plan.py`: chỉ đổi `EXPECTED_ASS`.
- `tests/integration/render/test_f09_fix1_ass_wrap.py`: mới, 7 ca, FFmpeg ghim thật (sha256 f845a09b...), không DB, không mock.
- `docs/delivery-evidence/f-09-fix1/report.md`: báo cáo này.

## 3. Số đo trong test FFmpeg thật

Số hàng là ước lượng `round(cao / (1.12 * cỡ chữ))`.

| Dòng | Hộp bao x (x_min-x_max) | y (y_min-y_max) | Số hàng |
| --- | --- | --- | --- |
| Disclosure seg-1 | 110-968 | 242-323 | 2 |
| Disclosure seg-3 | 160-918 | 242-363 | 3 |
| Disclosure seg-5 | 149-930 | 242-323 | 2 |
| Karaoke rộng 'MOSCOW WARNS NATO MEMBERS' | 257-823 | 1423-1550 | 2 |
| Karaoke vừa 'James Webb Space Telescope,' | 61-1015 | 1495-1562 | 1 |

Tất cả nằm trong x [55, 1024].

## 4. Lệnh kiểm

| Lệnh | Exit code | Dòng tổng kết |
| --- | --- | --- |
| `python -m pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovider` (bước 3) | 0 | `118 passed in 0.16s` |
| `python -m pytest tests/integration/render/test_f09_fix1_ass_wrap.py -q -rP -p no:cacheprovider` (bước 7) | 0 | `7 passed in 2.71s` |
| `python -m pytest tests/unit/render/test_f09_karaoke_plan.py tests/integration/render/test_f09_fix1_ass_wrap.py -q -p no:cacheprovider` (bước 8) | 0 | `125 passed in 2.56s` |
| `python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py -q -p no:cacheprovider` (bước 9) | 0 | `46 passed in 23.48s` |
| `python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py tests/integration/prod_wiring/test_pw_f1_inspector_visual.py -q -p no:cacheprovider` (bước 10) | 0 | `60 passed in 53.83s` |
| `python -m pytest tests/unit -q -p no:cacheprovider` (bước 11) | 0 | `7545 passed, 2561 subtests passed in 23.35s` |
| probe `python -c` karaoke_plan/test F-09 (bước 13) | 0 | không AssertionError, không output |
| probe `python -c` test tích hợp mới (bước 14) | 0 | không AssertionError, không output |
| probe `python -c` bố cục controlplane/pythonpath/`src.` (bước 15) | 0 | không AssertionError, không output |
| probe `python -c` báo cáo (bước 16) | 0 | không AssertionError, không output |
| `git diff --check` (bước 17) | 0 | không output |

## 5. Giới hạn

- Băm ASS (ass_ref) của mọi render đổi nên chỉ triển khai khi không có job nằm giữa resolve và QC (cấp lại CP7-10 sau khi gộp).
- libass không ngắt được từ đơn rộng hơn 960 px.
- Cổng INFERENCE_DISCLOSURE_PRESENT giữ nguyên.
- Không chạy full suite, tests/m1, tests/m2.
