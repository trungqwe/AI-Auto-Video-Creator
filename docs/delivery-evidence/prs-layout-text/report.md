# PRS-LAYOUT-TEXT — Báo cáo

## Nhóm lỗi và phạm vi
Gói PRS-LAYOUT-TEXT, nhóm lỗi OI-CP7-11-Q5 (mã nhóm do Control nêu trong yêu cầu nghiệm thu; repo không có định nghĩa riêng, báo cáo không suy diễn thêm).
Lỗi đo được: PRS-LAYOUT-RENDER dựng băng, thẻ, viên nhưng không có chữ, và IMGGEN-LABEL dán nhãn toàn khung 'AI-generated illustration'.

## Các tệp đã sửa
4 tệp chép nguyên văn từ D:/AIAVC_IMGPROTO/ref/prs-layout-text/ kèm sha256 đầy đủ 64 ký tự hex:
- src/render/domain/layout_text.py (sha256: 34a8ae650a9bcb1964a1dff32517ba603df06e9ad0bad09e38cbc8b739bb3fe8)
- src/render/adapters/ass_manifest.py (sha256: 62ab6603ec07bc6e7f7c3aa42f84014e05a3b9264982024e2dcbd23628fcc864)
- src/controlplane/api/wiring/render.py (sha256: 77d8c30543ed880282f1d2ae786c4971b3f30077503a300fc3d03af7eeeb8b33)
- tests/integration/render/test_prs_layout_text.py (sha256: 248eed26153fd0a68f415a588fbc4b0dfb9d356fcf9855e3afeb5c319719efd0)
Báo cáo này do Worker viết.

## Lệnh kiểm đã chạy
| Bước | Lệnh | Mã thoát | Kết quả |
| --- | --- | --- | --- |
| 1 | Probe kiểm tra trạng thái trước khi sửa (thư mục tham chiếu có SHA256SUMS với đủ 4 tệp; lane chưa có layout_text.py và test_prs_layout_text.py; ass_manifest.py và render.py của lane chưa chứa 'layout_rows' và render.py chưa có '_SCRIPT_PAYLOAD_SQL'; hình dạng khớp trạng thái trước nguyên mẫu; bản tham chiếu có 'layout_rows' và 'def layout_rows_for(') | Mã thoát 0 | Khớp pre-state yêu cầu |
| 4 | python -m pytest tests/integration/render/test_prs_layout_text.py -q -p no:cacheprovider | Mã thoát 1 | 4 failed, 1 passed in 2.05s (RED đúng oracle) |
| 7 | Probe kiểm tra sha256 cả 4 tệp so với bản tham chiếu SHA256SUMS | Mã thoát 0 | Cả 4 tệp khớp sha256 bản tham chiếu |
| 8 | python -m pytest tests/integration/render/test_prs_layout_text.py -q -p no:cacheprovider | Mã thoát 0 | 5 passed in 1.70s |
| 9 | git diff --check | Mã thoát 0 | Không có khoảng trắng thừa hay lỗi CRLF |
| 10 | python -m pytest tests/integration/render tests/integration/prod_wiring/test_prs_layout_render_preset.py tests/integration/prod_wiring/test_hook_qc_placeholder.py tests/integration/prod_wiring/test_pw_f1_fix4_still_canvas.py tests/integration/prod_wiring/test_pw_f1_inspector_visual.py -q -p no:cacheprovider | Mã thoát 0 | 312 passed, 4 warnings in 62.03s (0:01:02) |
| 11 | python -m pytest tests/unit/render -q -p no:cacheprovider | Mã thoát 0 | 1381 passed, 487 subtests passed in 10.21s |
| 12 | python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py tests/integration/prod_wiring/test_pw_w2_fix5_bootstrap.py tests/integration/prod_wiring/test_pw_d3_fix3_illustration.py -q -p no:cacheprovider | Mã thoát 0 | 65 passed in 23.19s |
| 13 | Probe sha256 bắt buộc của task cho layout_text.py và test_prs_layout_text.py | Mã thoát 0 | Trùng khớp sha256 bản tham chiếu |
| 14 | Probe cấu trúc layout_text.py (thuần, layout_text_rows, AI illustration, TITLE_MAX_CHARS = 48, first_number, slot_sources, q2) | Mã thoát 0 | Cấu trúc thuần đạt |
| 15 | Probe cấu trúc ass_manifest.py, render.py và test mới | Mã thoát 0 | Khớp cấu trúc |
| 16 | Probe giữ nguyên mọi hằng ILLUSTRATION_* và chữ ký illustration_windows | Mã thoát 0 | Đúng chữ ký và hằng |
| 17 | Probe PW-F3 (không fake, memory, import src.) | Mã thoát 0 | Hợp lệ |
| 18 | Probe waiting_port và assembly | Mã thoát 0 | Hợp lệ |
| 19 | Probe build_qc_probe trong render.py | Mã thoát 0 | Hợp lệ |
| 20 | Probe voice_duration trong render.py | Mã thoát 0 | Hợp lệ |
| 21 | Probe AudioMixGate và warning_gates trong render.py | Mã thoát 0 | Hợp lệ |
| 22 | Probe settings overlay và subtitle samples | Mã thoát 0 | Hợp lệ |
| 23 | Probe render_image_sources và ranh giới import | Mã thoát 0 | Hợp lệ |
| 24 | Probe audio_bed và measure_loudness | Mã thoát 0 | Hợp lệ |
| 25 | Probe cổng require_illustration và thứ tự | Mã thoát 0 | Hợp lệ |
| 26 | Probe illustration_windows trong render.py (đúng 3 lời gọi _build_ass_material) | Mã thoát 0 | Hợp lệ |
| 27 | Probe HOOK-QC (content_gates.py và render.py) | Mã thoát 0 | Hợp lệ |
| 28 | Probe không có CRLF trong 4 tệp của HOOK-QC | Mã thoát 0 | Không có CRLF |
| 29 | Probe PRS-LAYOUT-RENDER còn nguyên (preset, _plan_payload, test cũ) | Mã thoát 0 | Hợp lệ |
| 30 | Probe pyproject package-dir, pythonpath và cấm import tiền tố src | Mã thoát 0 | Hợp lệ |

## Ca hỏng trước, đạt sau
Số ca hỏng ở bước 4 (mã cũ): 4 failed, 1 passed in 2.05s
Số ca đạt ở bước 8 (mã mới): 5 passed in 1.70s
Số ca đạt ở bước 10 (nhóm 1): 312 passed, 4 warnings in 62.03s (0:01:02)

Bước 4 (RED, chạy test_prs_layout_text.py trên mã cũ trước khi chép mã adapters và wiring):
pytest thoát mã 1 với 4 ca hỏng đúng oracle (AttributeError thiếu layout_rows_for trong controlplane.api.wiring.render):
4 failed, 1 passed in 2.05s

Bước 8 (GREEN, test_prs_layout_text.py sau khi chép mã):
pytest thoát mã 0 với toàn bộ 5 ca đạt:
5 passed in 1.70s

Bước 10 (GREEN nhóm 1, tests/integration/render và 4 tệp prod_wiring):
pytest thoát mã 0 với toàn bộ 312 ca đạt:
312 passed, 4 warnings in 62.03s (0:01:02)

Bước 11 (GREEN nhóm 2, tests/unit/render):
pytest thoát mã 0:
1381 passed, 487 subtests passed in 10.21s

Bước 12 (GREEN nhóm 3, prod_wiring cần seed và bootstrap CSDL test):
pytest thoát mã 0:
65 passed in 23.19s

## Chữ của bố cục
Tiêu đề trên băng (tiêu đề ngắn của kế hoạch, ≤ 48 ký tự, thiếu thì câu đầu của lời đọc cắt ở ranh giới từ), chuyên mục (hook_intent của script), số nguyên văn của lời đọc, trích dẫn, nhãn hai vế, bộ đếm DATA_CARD, nhãn 'AI illustration' ở góc từng ô hiện ảnh AI, và không dán nhãn toàn khung lần hai (có layout_rows thì labels = ()); mọi dòng chữ bị cắt bỏ trong hook_time_range và thumbnail_time_range.

## Giới hạn
Tiêu đề dự phòng là câu đầu của lời đọc (render không đọc tiêu đề bài gốc), chuyên mục là hook_intent của script, bố cục bị render bỏ vì graph_too_long vẫn có chữ, không có số thì thẻ số của HERO_STRIP và MOSAIC_GRID để trống, chấm vị trí của HERO_STRIP chưa vẽ, nhắc lại mã OI-CP7-11-Q5.
