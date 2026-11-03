# PRS-LAYOUT-CONFIG — Báo cáo

## Nhóm lỗi và phạm vi
Gói PRS-LAYOUT-CONFIG, nhóm lỗi OI-CP7-11-Q5 (mã nhóm do Control nêu trong yêu cầu nghiệm thu; repo không có định nghĩa riêng, báo cáo không suy diễn thêm).
Lỗi đo được: seed_render_config chỉ ghi khi scope chưa có revision nên preset đổi trong hồ sơ không tới production.

## Các tệp đã sửa
3 tệp chép nguyên văn từ D:/AIAVC_IMGPROTO/ref/prs-layout-config/ kèm sha256 thật đã đo:
- tools/launcher/prod/profile.json (sha256: 2bfbc7c40c9f8e42916ce8fa2de7a3b8ba9085693ab72738730b9d7ef16b83cf)
- src/render/adapters/config_render_sources.py (sha256: 14d00ea7ed715f23037081c17fba0e63815c4aeb97b673155c31d89649baa391)
- tests/integration/render/test_prs_layout_config.py (sha256: 78ff3ca672a07c8aee81ccc3516db793c8ea675b9653c334a71e62fff5813047)
Báo cáo này do Worker viết.

## Lệnh kiểm đã chạy
| Bước | Lệnh | Mã thoát | Kết quả |
| --- | --- | --- | --- |
| 1 | Probe kiểm tra trạng thái trước khi sửa (revision 7, margin_right 60, chưa có layout, chưa có LAYOUT_KEYS) | Mã thoát 0 | Khớp pre-state yêu cầu |
| 2 | Chép tests/integration/render/test_prs_layout_config.py từ bản tham chiếu | Mã thoát 0 | Tạo tệp test thành công, sha256 khớp bản tham chiếu |
| 3 | python -m pytest tests/integration/render/test_prs_layout_config.py -q -p no:cacheprovider | Mã thoát 1 | 8 failed in 2.39s (RED đúng oracle) |
| 4 | Chép tools/launcher/prod/profile.json từ bản tham chiếu | Mã thoát 0 | Cập nhật hồ sơ thành công, sha256 khớp bản tham chiếu |
| 5 | Chép src/render/adapters/config_render_sources.py từ bản tham chiếu | Mã thoát 0 | Cập nhật bộ điều hợp thành công, sha256 khớp bản tham chiếu |
| 6 | Probe so khớp sha256 của profile.json và config_render_sources.py với bản tham chiếu | Mã thoát 0 | Cả hai tệp khớp sha256 chuẩn |
| 7 | python -m pytest tests/integration/render/test_prs_layout_config.py tests/integration/adapt/config tests/integration/render/test_f10_fix4_render_loudness.py -q -p no:cacheprovider | Mã thoát 0 | 41 passed in 16.20s |
| 8 | python -m pytest tests/unit/render -q -p no:cacheprovider | Mã thoát 0 | 1381 passed, 487 subtests passed in 13.81s |
| 9 | python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py tests/integration/prod_wiring/test_pw_w2_fix5_bootstrap.py -q -p no:cacheprovider | Mã thoát 0 | 50 passed in 27.32s |
| 10 | git diff --check | Mã thoát 0 | Không có khoảng trắng thừa |
| 11 | Probe sha256 tệp test so với bản tham chiếu | Mã thoát 0 | Khớp sha256 78ff3ca672a07c8aee81ccc3516db793c8ea675b9653c334a71e62fff5813047 |
| 12 | Probe ghép preset, lề và revision trong profile.json | Mã thoát 0 | 5 cặp layout đúng, margin_right 140, revision 8 |
| 13 | Probe cấu trúc mã và test | Mã thoát 0 | Khớp import LAYOUT_KEYS, presentation, accent_colour, scope, expected_revision, coveredIds |
| 14 | Probe PW-F3 | Mã thoát 0 | Không chứa fake, memory hay import tiền tố src. |
| 15 | Probe ADAPT-CONFIG-FIX2 | Mã thoát 0 | Dung sai word timing và karaoke 200ms, revision >= 2 |
| 16 | Probe PW-W2-FIX5 | Mã thoát 0 | Đủ trường render và qc, revision >= 2 |
| 17 | Probe voice.speed_fit | Mã thoát 0 | Khớp tham số speed_fit |
| 18 | Probe speech_rate_wpm | Mã thoát 0 | Tốc độ giọng đọc 136 wpm, revision >= 3 |
| 19 | Probe batch và gpu slots | Mã thoát 0 | max_concurrent_videos 6/10, 2 GPU slots, revision >= 5 |
| 20 | Probe image_safety | Mã thoát 0 | Đủ 6 danh mục an toàn ảnh, ngưỡng và boxblur, revision >= 6 |
| 21 | Probe ai.route_model_refs và revision | Mã thoát 0 | 7 tuyến AI đều dùng ag/gemini-3.8-flash-high, revision >= 7 |
| 22 | Probe package-dir, pythonpath và cấm import tiền tố src. | Mã thoát 0 | Cấu trúc gói hợp lệ, pytest pythonpath chứa src |

## Ca hỏng trước, đạt sau
Số ca hỏng ở bước 3 (mã cũ): 8 failed in 2.39s
Số ca đạt ở bước 7 (mã mới): 41 passed in 16.20s

Bước 3 (RED, chạy test mới trên mã cũ trước khi chép profile.json và config_render_sources.py):
pytest thoát mã 1 với 8 ca hỏng đúng oracle (KeyError 'layout', KeyError 'presentation', không raise ValueError khi layout lạ/trùng, TypeError tham số scope, AssertionError margin_right 60 != 140):
8 failed in 2.39s

Bước 7 (GREEN nhóm 1, sau khi chép đủ 3 tệp mã/test):
pytest thoát mã 0 với toàn bộ 41 ca đạt:
41 passed in 16.20s

Bước 8 (GREEN nhóm 2, tests/unit/render):
pytest thoát mã 0:
1381 passed, 487 subtests passed in 13.81s

Bước 9 (GREEN nhóm 3, prod_wiring):
pytest thoát mã 0:
50 passed in 27.32s

## Hồ sơ và seed
Hồ sơ tools/launcher/prod/profile.json được nâng lên revision 8 (meta.revision 7 thành 8), ghép đúng 5 cặp preset/bố cục:
- bold-yellow HERO_STRIP
- news-red MOSAIC_GRID
- soft-shadow FULL_BLEED_INSET
- clean-white SPLIT_STACK
- neon-cyan DATA_CARD

Lề phải phụ đề render.layout.value.margin_right đổi từ 60 thành 140 (lề trái giữ 60).

Bằng chứng seed ghi revision mới:
Test test_seed_with_scope_publishes_a_new_revision_only_when_the_payload_changed đạt ở bước 7 (ghi revision mới đúng một lần khi payload đổi, không ghi khi giữ nguyên) cùng test seed không scope vẫn chỉ điền scope trống.

## Giới hạn
Bốn phần UNSPECIFIED_V1 (visual_rhythm, thumbnail_overlay_style, hook_treatment, color_effect_rules) giữ nguyên vì render v1 không đọc; preset mới chỉ tới CSDL production khi PRS-LAYOUT-RENDER truyền scope vào seed_production_render_config; nhắc lại mã OI-CP7-11-Q5.
