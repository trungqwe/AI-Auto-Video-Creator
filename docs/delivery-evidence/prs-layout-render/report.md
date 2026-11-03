# PRS-LAYOUT-RENDER — Báo cáo

## Nhóm lỗi và phạm vi
Gói PRS-LAYOUT-RENDER, nhóm lỗi OI-CP7-11-Q5 (mã nhóm do Control nêu trong yêu cầu nghiệm thu; repo không có định nghĩa riêng, báo cáo không suy diễn thêm).
Lỗi đo được: render.py lấy preset cố định 'bold-yellow' ở 4 chỗ, bỏ qua preset_revision_ref của kế hoạch; mỗi cảnh chỉ hiện ảnh đầu.

## Các tệp đã sửa
4 tệp chép nguyên văn từ D:/AIAVC_IMGPROTO/ref/prs-layout-render/ kèm sha256 thật đã đo:
- src/render/domain/render_command.py (sha256: 586bc294a79fbaa22dec6e2ceba897d0779d75dd2d2911c5f8235c0909df1ee0)
- src/controlplane/api/wiring/render.py (sha256: 647842b59bde25096aac3e56e28170f77327d418800bf5d99db9870550876c69)
- tests/integration/render/test_prs_layout_render.py (sha256: 0a8af1185208298c409eaa303b7849ee2ce3c443eaaa67220817e96f52702dea)
- tests/integration/prod_wiring/test_prs_layout_render_preset.py (sha256: b090fab780160eb96e1919873c5e3795f43b7a15dc66cd65a5ed25334e903a13)
Báo cáo này do Worker viết.

## Lệnh kiểm đã chạy
| Bước | Lệnh | Mã thoát | Kết quả |
| --- | --- | --- | --- |
| 1 | Probe kiểm tra trạng thái trước khi sửa (thư mục tham chiếu có SHA256SUMS, 4 lần bold-yellow, chưa có DEFAULT_PRESET_KEY, chưa có LAYOUT_GRAPH_MAX_CHARS, 2 test mới chưa tồn tại) | Mã thoát 0 | Khớp pre-state yêu cầu |
| 4 | python -m pytest tests/integration/render/test_prs_layout_render.py tests/integration/prod_wiring/test_prs_layout_render_preset.py -q -p no:cacheprovider | Mã thoát 1 | 8 failed, 4 passed in 3.25s (RED đúng oracle) |
| 7 | Probe kiểm tra sha256 cả 4 tệp mã và test so với bản tham chiếu | Mã thoát 0 | Cả 4 tệp khớp sha256 bản tham chiếu |
| 8 | python -m pytest tests/integration/render tests/integration/prod_wiring/test_prs_layout_render_preset.py tests/integration/prod_wiring/test_hook_qc_placeholder.py tests/integration/prod_wiring/test_pw_f1_fix4_still_canvas.py -q -p no:cacheprovider | Mã thoát 0 | 236 passed, 4 warnings in 36.51s |
| 9 | python -m pytest tests/unit/render -q -p no:cacheprovider | Mã thoát 0 | 1381 passed, 487 subtests passed in 10.50s |
| 10 | python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py tests/integration/prod_wiring/test_pw_w2_fix5_bootstrap.py -q -p no:cacheprovider | Mã thoát 0 | 50 passed in 22.95s |
| 11 | git diff --check | Mã thoát 0 | Không có khoảng trắng thừa |

## Ca hỏng trước, đạt sau
Số ca hỏng ở bước 4 (mã cũ): 8 failed, 4 passed in 3.25s
Số ca đạt ở bước 8 (mã mới): 236 passed, 4 warnings in 36.51s

Bước 4 (RED, chạy 2 tệp test mới trên mã cũ trước khi chép mã):
pytest thoát mã 1 với 8 ca hỏng đúng oracle (AttributeError LAYOUT_GRAPH_MAX_CHARS, DID NOT RAISE RenderCommandRejected khi presentation sai, AssertionError thiếu {image:0} trong argv, AttributeError _plan_preset, AttributeError DEFAULT_PRESET_KEY, AssertionError còn preset('bold-yellow')):
8 failed, 4 passed in 3.25s

Bước 8 (GREEN nhóm 1, tests/integration/render và 3 tệp prod_wiring):
pytest thoát mã 0 với toàn bộ 236 ca đạt:
236 passed, 4 warnings in 36.51s

Bước 9 (GREEN nhóm 2, tests/unit/render):
pytest thoát mã 0:
1381 passed, 487 subtests passed in 10.50s

Bước 10 (GREEN nhóm 3, prod_wiring cần seed và bootstrap):
pytest thoát mã 0:
50 passed in 22.95s

## Video thử và preset
Test test_hero_strip_video_shows_the_scene_image_in_the_main_cell_and_the_next_ones_in_the_strip dựng video thật 3 cảnh HERO_STRIP qua FFmpeg ghim, khung giữa cảnh có đúng ảnh ở ô chính và dải.
render.py không còn cố định bold-yellow: chỉ còn DEFAULT_PRESET_KEY làm dự phòng; preset đã seed theo preset_revision_ref của kế hoạch được dùng; preset chưa seed thì dùng mặc định.

## Giới hạn
Chưa vẽ chữ bố cục và chưa có cổng QC LAYOUT_RENDERED (hai gói PRS-LAYOUT-TEXT, PRS-LAYOUT-QC); cảnh là clip thì giữ cảnh một ảnh; video trên 14 cảnh (HERO_STRIP, MOSAIC_GRID) giữ cảnh một ảnh và ghi graph_too_long; nhắc lại mã OI-CP7-11-Q5.
