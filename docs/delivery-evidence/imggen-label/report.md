# Báo cáo IMGGEN-LABEL

## Nhóm lỗi

- Mã gói: `IMGGEN-LABEL`.
- Nhóm lỗi: `OI-CP7-11-Q2` — video có ảnh minh hoạ AI chưa có nhãn trên hình và caption chưa có câu thông báo.
- `GIẢ ĐỊNH`: định nghĩa gốc của Q2 không nằm trong repo; nội dung trên lấy theo spec của task.

## Tệp đã sửa

| Tệp | Mô tả |
| --- | --- |
| `src/render/adapters/ass_manifest.py` | Thêm `ILLUSTRATION_WINDOW_INVALID`, 10 hằng `ILLUSTRATION_*`, `_illustration_style_row`, `_label_windows`; `build_ass_text` và `build_ass_material` nhận `illustration_windows=()`. |
| `src/controlplane/api/wiring/render.py` | Thêm `illustration_windows` công khai (cùng helper); `_build_ass_material` nhận `timeline`, `hook_placement`, `allowed_fallbacks`; `resolve_inputs`, `render_plan`, `ass_material` truyền cùng dữ liệu. |
| `src/creative/application/pipeline.py` | Thêm `ORIGIN_AI_GENERATED`, `AI_ILLUSTRATION_NOTE`, `_uses_ai_illustration`, `_with_illustration_note`; `generate_output_metadata` thêm câu trước sanitizer khi kế hoạch dùng ảnh AI. |
| `tests/integration/render/test_imggen_label.py` | 11 test mới: hàng ASS, cửa sổ thời gian, render FFmpeg ghim thật, QC. |
| `tests/unit/creative/test_imggen_metadata_note.py` | 5 test mới: câu caption, chạy chuỗi D-14 trong bộ nhớ. |
| `docs/delivery-evidence/imggen-label/report.md` | Báo cáo này. |

## Lệnh đã chạy

Bước 9 là RED (chạy trước khi sửa nguồn), bước 21 là GREEN.

| Bước | Lệnh | Exit code | Dòng tổng kết nguyên văn của pytest |
| --- | --- | --- | --- |
| 9 (RED) | `python -m pytest tests/integration/render/test_imggen_label.py tests/unit/creative/test_imggen_metadata_note.py -q -p no:cacheprovider` | 1 | `14 failed, 2 errors in 2.89s` |
| 12 | probe cấu trúc `ass_manifest.py` | 0 | không áp dụng |
| 17 | probe wiring `render.py` | 0 | không áp dụng |
| 20 | probe `pipeline.py` | 0 | không áp dụng |
| 21 (GREEN) | `python -m pytest tests/integration/render/test_imggen_label.py tests/unit/creative/test_imggen_metadata_note.py -q -p no:cacheprovider` | 0 | `16 passed in 7.38s` |
| 22 | probe tên test và tính ngoại tuyến | 0 | không áp dụng |
| 23 | `python -m pytest tests/integration/render/test_f09_fix1_ass_wrap.py tests/integration/render/test_f10_fix6_frame_placement.py tests/integration/prod_wiring/test_pw_f1_inspector_visual.py tests/integration/prod_wiring/test_pw_d3_fix3_illustration.py -q -p no:cacheprovider` | 0 | `99 passed, 4 warnings in 32.00s` |
| 24 | nhóm creative (D-14, D-15, D-16, PW-D1, PW-D2, D-15-FIX1, D-15-FIX2) | 0 | `184 passed in 24.75s` |
| 25 | nhóm render inputs (PW-F3, PW-W2-FIX8, F-10-FIX3, F-10-FIX5) | 0 | `86 passed, 1 warning in 119.58s (0:01:59)` |
| 26 | nhóm render worker và wire (có Postgres) | 0 | `175 passed in 63.41s (0:01:03)` |
| 27 | `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider` | 0 | `11 passed, 1 warning in 153.82s (0:02:33)` |
| 28 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7789 passed, 1 warning, 2561 subtests passed in 25.77s` |
| 29–33 | probe PW-F3, cổng minh hoạ, D-15-FIX1, D-15-FIX2, bố cục gói | 0 | không áp dụng |
| 34 | `git diff --check` (lần 1) | 0 | không áp dụng |
| 36 | probe báo cáo (`report.md` nêu `IMGGEN-LABEL` và `OI-CP7-11-Q2`) | 0 | không áp dụng |
| 37 | `git diff --check` (lần cuối, sau báo cáo) | 0 | không áp dụng |

Các probe còn lại trong nhóm lệnh kiểm do Control chạy (tôi đã chạy thử toàn bộ probe cấu trúc của nhóm lệnh kiểm, đều exit 0).

## Kết quả từng tiêu chí

1. `ass_manifest.py`: có `ILLUSTRATION_WINDOW_INVALID` và 10 hằng `ILLUSTRATION_*` đúng giá trị; `_illustration_style_row` dựng theo `plan.style`; `_label_windows` từ chối cửa sổ sai bằng `AssManifestRejected(ILLUSTRATION_WINDOW_INVALID)`, sắp xếp và gộp cặp chồng hoặc chạm nhau; hàng Style chèn sau hàng Style cuối, mỗi cửa sổ một hàng Dialogue ở cuối tệp. Không có cửa sổ thì văn bản ASS và sha256 giữ nguyên từng byte.
2. `wiring/render.py`: `illustration_windows` công khai theo `artifact_version_ref` chữ thường, loại media có luật image-safety `seed_fallback` hoặc `image_fallback`, theo `visual_asset_refs[0]`, kéo cảnh cuối tới `end_ms`, gộp, cắt hook và thumbnail. `_build_ass_material` được gọi ở ba nơi (`resolve_inputs`, `render_plan`, `ass_material`) với cùng dữ liệu; `resolve_inputs` dùng một `render_timeline`. Không import `creative` hay `voice`; `require_illustration` giữ nguyên vị trí.
3. `pipeline.py`: `illustrated = _uses_ai_illustration(plans)` sau khi nạp plans; `_with_illustration_note` chạy trước sanitizer nên `filename_safe.caption` cũng có câu; kế hoạch không có ảnh AI giữ nguyên caption. Không đổi payload, request_hash, prompt, `activity_inputs.py`.
4. Test: 16 ca mới (11 + 5), docstring có `coveredIds: OI-CP7-11-Q2`, không DB, không mạng, không monkeypatch hay mock. RED bước 9: cả 16 ca không đạt (14 failed, 2 errors; lý do thiếu `illustration_windows`, `_uses_ai_illustration`, `_with_illustration_note`). Không đổi `render_command.py`, `real_output_inspector.py`, `profile.json` hay test cũ.

## Số đo render

Render FFmpeg ghim thật 1080x1920, libx264, so bản không nhãn với bản có nhãn:

- Khung 37 và khung 105 (trong cửa sổ nhãn): đo ở các hàng phía trên dải Disclosure (hàng nhỏ hơn 200), hàng khác biệt 98–159 (khung 37) và 96–154 (khung 105); cột khác biệt 46–431 và 49–422.
- Khung 5, 25, 55, 75 (ngoài cửa sổ nhãn): chênh trung bình 0.0, 0.0004, 0.0358, 0.0 (ngưỡng 0.05).
- Điều chỉnh so với bước 8: test đo toàn khung cho hàng khác biệt tới 1569 (khung 37) và từ hàng 238 (khung 105). Các hàng đó là nhiễu mã hoá của libx264 ở vùng chữ Karaoke và Disclosure (độ lệch tối đa 28 và 41 trên thang 255), không phải nhãn. Test giới hạn phép đo vào 200 hàng đầu; nhãn vẫn nằm trong 90..170 và ngoài dải Disclosure nên các ngưỡng 95..160, 40..700 và 0.05 giữ nguyên.
- Test 11 (`label == plain` và `measured_value` bằng nhau) đạt, không dùng fallback so từng trường.

## Giới hạn đã biết

- Câu caption dựa vào origin của visual trong kế hoạch, không dựa vào ref `ai_illustration` chuyển tiếp, vì video thứ hai của cùng bài dùng lại ảnh AI đã đăng ký mà GenerateIllustrations không trả ref nào.
- Nhãn theo ms của timeline; render làm tròn mỗi cảnh về khung nguyên nên ranh giới có thể lệch một khung.
- Trường hợp hiếm: ảnh bài bị loại rồi thay bằng bản che của một ảnh AI mà kế hoạch không dùng ở đâu khác thì không có nhãn.
- Nếu sau này render vẽ nhiều visual mỗi cảnh, quy tắc `visual_asset_refs[0]` phải đổi theo.
