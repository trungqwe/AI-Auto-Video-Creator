# PRS-LAYOUT-DOMAIN — Báo cáo

## Nhóm lỗi và phạm vi
Gói PRS-LAYOUT-DOMAIN, nhóm lỗi OI-CP7-11-Q5 (mã nhóm do Control nêu trong yêu cầu nghiệm thu; repo không có định nghĩa riêng, báo cáo không suy diễn thêm). Gói thêm mô-đun miền thuần cho 5 bố cục 9:16 (FR-PRS-001, FR-PRS-002, FR-PRS-006), chưa nối vào render.

## Các tệp đã tạo
- src/render/domain/layout.py (sha256: 90cb42c3f5ed700d92644f6ef878d3e6fea14807241a8bd6bfe55760ba13f2a4)
- tests/unit/render/test_prs_layout_geometry.py (sha256: 72443e5a3398cc174df384ced2522674ba0b38680e7b3c463b132c28d72c712d)
- tests/integration/render/test_prs_layout_graph.py (sha256: b5be5bc70ad16f4876e8937ff067de110f9fbec3fae6e05669528d39d9f06187)

Cả 3 tệp được chép nguyên văn từ D:/AIAVC_IMGPROTO/ref/prs-layout-domain/ và bước 8 xác nhận khớp hoàn toàn giá trị băm chuẩn; báo cáo này do Worker viết.

## Lệnh kiểm đã chạy
| Bước | Lệnh | Mã thoát | Kết quả |
| --- | --- | --- | --- |
| 3 | python -m pytest tests/unit/render/test_prs_layout_geometry.py tests/integration/render/test_prs_layout_graph.py -q -p no:cacheprovider | 2 | 2 errors during collection (chưa có mô-đun layout.py) |
| 4 | Chép src/render/domain/layout.py từ bản tham chiếu | 0 | Tạo tệp thành công, sha256 khớp bản tham chiếu |
| 5 | python -m pytest tests/unit/render/test_prs_layout_geometry.py tests/integration/render/test_prs_layout_graph.py -q -p no:cacheprovider | 0 | 11 passed in 1.58s |
| 6 | python -m pytest tests/unit/render -q -p no:cacheprovider | 0 | 1381 passed, 487 subtests passed in 12.29s |
| 7 | git diff --check | 0 | Không có lỗi khoảng trắng thừa |
| 8 | Probe so khớp sha256 của 3 tệp với bản tham chiếu | 0 | Cả 3 sha256 khớp bản tham chiếu |
| 9 | Probe kiểm tra cấu trúc layout.py (5 hàm, các hằng, thuần túy) | 0 | Đạt toàn bộ hàm và hằng số yêu cầu, không có thư viện cấm |
| 10 | Probe kiểm tra test (coveredIds, 3 tên test, không mock) | 0 | Đạt coveredIds FR-PRS-001, FR-PRS-002, FR-PRS-006 |
| 11 | Probe package-dir/pythonpath/không import tiền tố src. | 0 | Cấu trúc gói và import hợp lệ |

## Ca hỏng trước, đạt sau
Bước 3 (RED, trước khi có layout.py):
pytest thoát mã 2 với 2 lỗi thu thập do thiếu render.domain.layout:
`	ext
2 errors in 0.21s
`

Bước 5 (GREEN, sau khi có layout.py):
pytest thoát mã 0:
`	ext
11 passed in 1.58s
`

Bước 6 (tests/unit/render):
pytest thoát mã 0:
`	ext
1381 passed, 487 subtests passed in 12.29s
`

## Toạ độ 5 bố cục
- HERO_STRIP (nền mờ 0.45): title_band 0,310,1080,170 màu nhấn; main 34,504,1012,632 viền 6 trắng; number_card 70,966,330,132 đen 0.82 bo 16 (nhấn mạnh); strip0..2 x=40+340k,y=1160,320x190 (strip0 viền 6 màu nhấn, còn lại viền 3 trắng); subtitle_shade gradient 0,1340,1080,580 từ 0 đến 0.8. Ô chữ: title 60,322,960,140; number 92,972,290,90; number_caption 92,1064,290,30; position_dots 60,1352,900,24.
- MOSAIC_GRID (0.18): title_band 0,300,1080,160 đen 0.92; category_bar 0,300,16,160 đỏ; grid0..3 x=544*(k%2),y=476+444*(k//2),536x436; badge_ring 422,780,236,236 bo 118; badge 430,788,220,220 màu nhấn bo 110; subtitle_backing 0,1360,1080,560 đen 0.92. Chữ: category 60,316,960,40; title 60,360,960,56; badge_number 450,820,180,110; badge_caption 450,940,180,36.
- FULL_BLEED_INSET (nền đen): background 0,0,1080,1920; top_shade 0,0,1080,560 từ 0.75 đến 0; bottom_shade 0,1240,1080,680 từ 0 đến 0.85; inset 70,570,908,588 viền 14 trắng; quote_card 90,1210,900,150 đen 0.8 bo 14; quote_bar 90,1210,10,150 nhấn. Chữ: category 60,318,960,40; title 60,362,960,140; ai_label 780,510,230,40; quote 130,1226,820,110.
- SPLIT_STACK (0.3): top 0,290,1080,600; bottom 0,1040,1080,880; middle_band 0,890,1080,150 đen; middle_rule_top 0,890,1080,6 và middle_rule_bottom 0,1034,1080,6 màu nhấn; subtitle_shade 0,1300,1080,620 từ 0 đến 0.85; top_label 40,320,470,64 nhấn bo 10; bottom_label 40,1072,450,64 trắng bo 10. Chữ: title 60,900,900,130; arrow 976,945,40,40; top_label 60,328,440,48; bottom_label 60,1080,420,48.
- DATA_CARD (0.22): category_pill 60,330,300,54 đỏ bo 27; main 60,580,960,540; aux0 90,1050,208,138 và aux1 310,1050,208,138 viền 4 trắng; counter_pill 890,600,110,48 đen 0.7 bo 24; number_rule 60,1210,960,4 nhấn. Chữ: category 84,334,260,44; title 60,404,960,132; counter 900,606,90,36; number 60,1216,400,156; explain 480,1236,480,44 (rộng 480 để không vào cột phải); sub_line 480,1286,480,44.

## Kiểm vùng an toàn
Bằng chứng là test test_every_layout_keeps_text_and_emphasis_out_of_the_reserved_zones (bước 5): safe_zone_violations trả () cho cả 5 bố cục (không ô chữ hay lớp nhấn mạnh trong hàng 0-220, 1380-1580, 1600-1920; chữ trong x 60-1020 và trái x 960 ở hàng 1000-1600).

## Độ dài đồ thị lọc
Con số do Control đo bằng nguyên mẫu: chuỗi lọc mỗi cảnh khi dùng chrome chung dài 990-1544 ký tự. Worker không tự đo (probe python -c không được import mô-đun dự án) nên ghi rõ đây là số của Control, không phải số Worker đo.

## Giới hạn
Chưa có bo góc ảnh, bóng đổ, xoay ảnh lồng, hiệu ứng trượt hay bật lớp; viền là hình chữ nhật; ảnh cắt giữa (chưa đọc crop_intent); chữ thuộc gói PRS-LAYOUT-TEXT; mô-đun chưa được render gọi cho tới PRS-LAYOUT-RENDER.

## Ghi chú
Lệnh kiểm probe report.md và git diff --check cuối chạy sau khi ghi báo cáo; kết quả ở thông báo worker_done.
