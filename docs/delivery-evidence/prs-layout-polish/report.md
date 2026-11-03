# PRS-LAYOUT-POLISH — Báo cáo

## Nhóm lỗi và phạm vi
Gói PRS-LAYOUT-POLISH, nhóm lỗi OI-CP7-11-Q5 (mã nhóm do Control nêu trong yêu cầu nghiệm thu; repo không có định nghĩa riêng, không suy diễn thêm).
Lỗi đo được: ô vuông góc, viền là khung chrome đứng yên, không bóng, ảnh lồng không xoay, chỉ ô chính chuyển động, đồ thị trên 24.000 ký tự (HERO_STRIP, MOSAIC_GRID trên 14 cảnh) làm video mất bố cục (graph_too_long).

## Các tệp đã sửa
7 tệp chép nguyên văn từ D:/AIAVC_IMGPROTO/ref/prs-layout-polish/ kèm sha256 đầy đủ 64 ký tự hex của từng tệp:
- src/render/domain/layout.py (sha256: b6f91f1d6fd46456ca2fca74dc1426c9802ca1cc09338cbcf15176c489f04b6c)
- src/render/domain/render_command.py (sha256: 6177aa7785974e8538907b630d0a06ea3872e144f1572d1ae292fe2a14a2ac0e)
- src/render/adapters/real_ffmpeg_renderer.py (sha256: 380ebf3408dfbeb18bbc59f9630213f89b5e92aa8d5c00a000fa373abd664b9e)
- tests/unit/render/test_prs_layout_geometry.py (sha256: 87006ae096363b7eaff85cee88651f055e13a93632881c71b100f9058b7a562b)
- tests/integration/render/test_prs_layout_graph.py (sha256: de9dbf8ad59edbc943a23cf9aa19827212bb7182ca436e69b11efd771bd7b923)
- tests/integration/render/test_prs_layout_render.py (sha256: 6af7cc89e0654acd96e674c9cee0b0199a43561fd7a73210882afefa70e76f76)
- tests/integration/render/test_prs_layout_polish.py (sha256: 2da6bd90c46f53ee5a8fe5d992fe39fc1d86898c662df4d22848d25c4d99b87e)
Báo cáo này do Worker viết.

## Lệnh kiểm đã chạy
| Bước | Lệnh | Mã thoát | Kết quả |
| --- | --- | --- | --- |
| 1 | `python -c "import hashlib, pathlib; ref = pathlib.Path('D:/AIAVC_IMGPROTO/ref/prs-layout-polish'); lines = [l.split() for l in (ref / 'SHA256SUMS').read_text(encoding='utf-8-sig').splitlines() if l.strip()]; assert len(lines) == 7, lines; norm = lambda p: p.read_bytes().replace(bytes([13, 10]), bytes([10])); bad = sorted(n for h, n in lines if hashlib.sha256(norm(ref / n)).hexdigest() != h); assert not bad, ('reference differs from SHA256SUMS', bad); lay = pathlib.Path('src/render/domain/layout.py').read_text(encoding='utf-8'); fr = pathlib.Path('src/render/adapters/real_ffmpeg_renderer.py').read_text(encoding='utf-8'); assert 'def compose_masks(' not in lay and 'GRAPH_FILE_OPTION' not in fr, 'pre-state'; assert not pathlib.Path('tests/integration/render/test_prs_layout_polish.py').exists(), 'polish test exists'; assert not pathlib.Path('docs/delivery-evidence/prs-layout-polish/report.md').exists(), 'report exists'"` | Mã thoát 0 | Khớp trạng thái trước khi sửa (reference khớp SHA256SUMS, layout.py chưa có compose_masks, real_ffmpeg_renderer.py chưa có GRAPH_FILE_OPTION, 2 tệp chưa tồn tại) |
| 3 | `python -m pytest tests/integration/render/test_prs_layout_polish.py -q -p no:cacheprovider` | Mã thoát 1 | 7 failed in 0.94s (RED đúng oracle, 7 ca hỏng ở thân test) |
| 10 | `python -c "import hashlib, pathlib; want = {'src/render/domain/layout.py': 'b6f91f1d6fd46456ca2fca74dc1426c9802ca1cc09338cbcf15176c489f04b6c', 'src/render/domain/render_command.py': '6177aa7785974e8538907b630d0a06ea3872e144f1572d1ae292fe2a14a2ac0e', 'src/render/adapters/real_ffmpeg_renderer.py': '380ebf3408dfbeb18bbc59f9630213f89b5e92aa8d5c00a000fa373abd664b9e', 'tests/unit/render/test_prs_layout_geometry.py': '87006ae096363b7eaff85cee88651f055e13a93632881c71b100f9058b7a562b', 'tests/integration/render/test_prs_layout_graph.py': 'de9dbf8ad59edbc943a23cf9aa19827212bb7182ca436e69b11efd771bd7b923', 'tests/integration/render/test_prs_layout_render.py': '6af7cc89e0654acd96e674c9cee0b0199a43561fd7a73210882afefa70e76f76', 'tests/integration/render/test_prs_layout_polish.py': '2da6bd90c46f53ee5a8fe5d992fe39fc1d86898c662df4d22848d25c4d99b87e'}; norm = lambda p: pathlib.Path(p).read_bytes().replace(bytes([13, 10]), bytes([10])); bad = sorted(p for p, h in want.items() if hashlib.sha256(norm(p)).hexdigest() != h); assert not bad, ('differs from reference', bad)"` | Mã thoát 0 | Cả 7 tệp khớp sha256 của bản tham chiếu |
| 11 | `python -m pytest tests/integration/render/test_prs_layout_polish.py -q -p no:cacheprovider` | Mã thoát 0 | 7 passed in 5.94s |
| 12 | `python -m pytest tests/integration/render tests/integration/prod_wiring/test_prs_layout_render_preset.py tests/integration/prod_wiring/test_hook_qc_placeholder.py tests/integration/prod_wiring/test_pw_f1_fix4_still_canvas.py tests/integration/prod_wiring/test_pw_f1_inspector_visual.py tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider` | Mã thoát 0 | 373 passed, 4 warnings in 73.11s (0:01:13) |
| 13 | `python -m pytest tests/unit/render -q -p no:cacheprovider` | Mã thoát 0 | 1381 passed, 487 subtests passed in 10.44s |
| 14 | `python -m pytest tests/integration/prod_wiring/test_f10_fix5_bed_mix.py tests/integration/prod_wiring/test_pw_f2_inspector_audio.py tests/integration/prod_wiring/test_pw_f4_render_worker.py -q -p no:cacheprovider` | Mã thoát 0 | 61 passed, 1 warning in 197.12s (0:03:17) |
| 15 | `git diff --check` | Mã thoát 0 | Không có output, không có khoảng trắng thừa hay lỗi xuống dòng |

## Ca hỏng trước, đạt sau
Số ca hỏng ở bước 3 (mã cũ, kỳ vọng 7 failed): 7 failed in 0.94s
Số ca đạt ở bước 11 (mã mới): 7 passed in 5.94s
Số ca đạt ở bước 12 (nhóm 1, render tích hợp và prod_wiring liên quan): 373 passed, 4 warnings in 73.11s (0:01:13)
Số ca đạt ở bước 13 (nhóm 2, unit render): 1381 passed, 487 subtests passed in 10.44s
Số ca đạt ở bước 14 (nhóm 3, bed mix, inspector audio, render worker): 61 passed, 1 warning in 197.12s (0:03:17)

Bước 3 (RED, chạy test_prs_layout_polish.py trên mã cũ trước khi chép mã nguồn mới):
pytest thoát mã 1 với 7 ca hỏng ở thân test (AssertionError góc bo viền, AssertionError bóng đổ ô chính, AssertionError góc xoay 2 độ ảnh lồng, AssertionError trượt vào ô phụ, AttributeError compose_masks, AttributeError graph_through_file, AssertionError độ dài đồ thị vượt trần):
7 failed in 0.94s

Bước 11 (GREEN, chạy test_prs_layout_polish.py trên mã mới sau khi chép):
pytest thoát mã 0 với toàn bộ 7 ca đạt:
7 passed in 5.94s

Bước 12 (GREEN nhóm 1, tests/integration/render và các tệp prod_wiring/adapt liên quan):
pytest thoát mã 0 với toàn bộ 373 ca đạt:
373 passed, 4 warnings in 73.11s (0:01:13)

Bước 13 (GREEN nhóm 2, tests/unit/render):
pytest thoát mã 0 với toàn bộ 1381 ca đạt:
1381 passed, 487 subtests passed in 10.44s

Bước 14 (GREEN nhóm 3, tests/integration/prod_wiring bed mix, inspector audio, render worker):
pytest thoát mã 0 với toàn bộ 61 ca đạt:
61 passed, 1 warning in 197.12s (0:03:17)

## Hình thức dựng mới
Bo góc bằng mặt nạ alphamerge, bóng đổ (SHADOW_OPACITY 0.55, SHADOW_OFFSET 10), ảnh lồng FULL_BLEED_INSET xoay -2 độ bằng rotate c=none, ô chính Ken Burns, ô phụ trượt vào (ENTER_SECONDS 0.3, ENTER_STAGGER 0.06, ENTER_SHIFT 120), mặt nạ dựng một lần (compose_masks), khung cuối cảnh trùng khung QC, đồ thị dài hơn LAYOUT_GRAPH_MAX_CHARS (24000) được truyền qua tệp -/filter_complex và tệp bị xoá sau lượt, trần mới LAYOUT_SCRIPT_MAX_CHARS = 400000 thay trần 14 cảnh; preset không có presentation không đổi argv.

## Giới hạn
Bóng đổ của ảnh lồng đứng yên khi ảnh rơi vào (0,3 giây); thẻ số không bật theo hình; probe sha256 của PRS-LAYOUT-DOMAIN và PRS-LAYOUT-RENDER ghim bản cũ của layout.py và ba test nên cần check-corrections do Control xử lý; nhắc lại mã OI-CP7-11-Q5.
