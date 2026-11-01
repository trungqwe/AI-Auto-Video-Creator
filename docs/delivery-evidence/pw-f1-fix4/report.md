# Báo cáo PW-F1-FIX4

## 1. Nhóm lỗi OI-CP7-10-F14

Lô c84aedba-ae26-499d-9914-7798dd4bfb09, lượt RG-09 F10c của CP7-10 ngày 01/11/2026, HEAD b2712db: qc FAILED_FINAL vì `THUMBNAIL_PRESENT=thumbnail_asset_mismatch` tại 2000 ms dù thumbnail hiện đúng trong mp4.

Gốc lỗi: render đặt ảnh lên khung bằng `scale=W:H:force_original_aspect_ratio=increase,crop=W:H`, còn `ssim_between` thu thẳng ảnh về 90x160. Hai đường scale cho mức đen khác nhau ở ảnh gần đen phẳng, nên SSIM là 0,694 < 0,85 (`qc.hook_similarity_min`). Đặt ảnh lên khung 1080x1920 trước rồi mới thu nhỏ cho 0,993 trên tệp thật của lô (số đo của Control). `VISUAL_HOOK_PRESENT` dùng chung `ssim_between` nên chung lỗi khi clip hook khác tỷ lệ khung.

## 2. Cách sửa

- `FrameProbe.frame_size` và `_FRAME_SIZE_RE` đọc rộng x cao của luồng video đầu; `None` khi không đọc được.
- `ssim_between` thêm tham số từ khoá `canvas`; khi có canvas, đầu vào phải đi qua `scale increase + crop` theo canvas trước chuỗi prep cũ; đầu vào trái giữ nguyên; canvas `None` giữ đúng chuỗi lọc cũ.
- `_visual_hook` và `_thumbnail` truyền `canvas=self._probe.frame_size(media)`.
- Không đổi ngưỡng 0,85, `profile.json`, `render_command.py`, renderer, `content_gates.py`; không thêm thư viện.

## 3. Tệp đã sửa

- `src/render/adapters/real_output_inspector.py`
- `src/render/adapters/frame_probe.py`
- `tests/integration/prod_wiring/test_pw_f1_fix4_still_canvas.py` (mới)
- `docs/delivery-evidence/pw-f1-fix4/report.md` (mới)

## 4. Lệnh đã chạy

| Bước | Lệnh | Mã thoát | Kết quả nguyên văn |
| --- | --- | --- | --- |
| RED (mã cũ, đã tạm gỡ sửa ở `src/render/adapters`) | `python -m pytest tests/integration/prod_wiring/test_pw_f1_fix4_still_canvas.py -q -p no:cacheprovider` | 1 | `3 failed in 4.21s` |
| 2 | `python -m pytest tests/integration/prod_wiring/test_pw_f1_fix4_still_canvas.py tests/integration/prod_wiring/test_d10_fix1_hook_lead.py tests/integration/prod_wiring/test_pw_f1_inspector_visual.py tests/integration/prod_wiring/test_pw_f2_inspector_audio.py -q -p no:cacheprovider` | 0 | `97 passed in 61.06s (0:01:01)` |
| 3 | `python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py tests/integration/prod_wiring/test_pw_w2_fix6_qc_probe.py -q -p no:cacheprovider` | 0 | `19 passed in 51.02s` |
| 4 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7638 passed, 2561 subtests passed in 26.09s` |
| 5-11 | các probe `python -c` nguyên văn của brief | 0 | không in lỗi |
| 1 | `git diff --check` | 0 | không in dòng nào |
| 12 | probe báo cáo (`PW-F1-FIX4`, `OI-CP7-10-F14`) | chạy ở bước hoàn tất, kết quả ghi trong worker_done | |

## 5. RED trước và đạt sau

Trên mã cũ cả 3 test mới hỏng (3 failed); ca đầu `test_dark_still_thumbnail_passes_thumbnail_gate` hỏng đúng `thumbnail_asset_mismatch`, hai ca còn lại hỏng vì `FrameProbe` chưa có `frame_size`. Sau bản sửa: 3 passed (`3 passed in 4.37s`).

## 6. SSIM của test_ssim_prepares_the_still_on_the_output_canvas

Dòng in ở test: `without_canvas=0.570692 with_canvas=0.999658`. MIN_SIMILARITY là 0,85: có canvas đạt, không có canvas không đạt.

## 7. Phản ví dụ đã loại trừ

Canvas `None` giữ nguyên chuỗi lọc; không đổi ngưỡng; không sửa render hay `content_gates.py`; test không dùng monkeypatch, DB hay đối tượng giả.

## 8. Mục mở và giới hạn

`OI-CP7-10-F14` đã đóng. Giới hạn: phụ đề vẫn nằm trong khung so; ảnh có phụ đề lớn đè lên chi tiết chính có thể còn gần ngưỡng, theo dõi ở CP7-11. Căn cứ a15a18f2 và quyết định Control 01/11/2026 (`docs/audit/CONTROL_SELF_DECISIONS.md`): sửa cách đo cho đúng cách render dựng, không nới ngưỡng.
