# PW-F1-FIX3 — QC so khung mẫu với chính nó sau khi vẽ lại ASS

## 1. Nhóm lỗi

Nhóm lỗi: `OI-PW-F1-01` (cùng gốc với `OI-PW-F1-02` và `OI-CP7-10-F10`).

- CP7-10, RG-09 ngày 01/11/2026, HEAD 2687822: job `0ccb8a77…:job:1` FAILED_FINAL ở bước qc vì `SUBTITLE_BURNED_IN=failed/subtitle_not_observed`, dù mp4 có đủ chữ karaoke và Disclosure khớp ASS.
- Gốc: `_subtitle` cần một khung mốc ở giữa khoảng trống ≥ `baseline_min_gap_ms` (400 ms) ngoài mọi cửa sổ Dialogue. Giọng liền 147 từ phủ gần hết thời lượng (nghỉ giữa hai dòng lớn nhất 220 ms) nên `baseline_ms` là `None` và cổng trả `subtitle_not_observed`.
- Cùng cơ chế còn cho kết quả đạt giả: khung mốc nằm ở cảnh khác nên khác biệt giữa hai khung đến từ nội dung cảnh chứ không phải từ chữ; video nền kiểu P31c bỏ bộ lọc `subtitles` vẫn PASSED.
- `INFERENCE_DISCLOSURE_PRESENT` được đo giống `SUBTITLE_BURNED_IN` (PW-F1) nên chung gốc.

## 2. Cách sửa

Mỗi khung mẫu được so với chính nó sau khi vẽ lại ASS đã stage (không dùng khoảnh khắc khác):

- `FrameProbe.overlay_difference(media, sample_ms, subtitles_path, top, bottom)` trả `OverlayDifference(residual, ink)`: `residual` = YAVG(|F − subtitles(F)|), `ink` = YAVG(|G − subtitles(G)|) với G là khung xám cùng kích thước và pts. Khung có chữ khi `ink > 0` và `residual ≤ overlay_max_missing_share × ink`.
- `subtitles_filter_path`: thoát `/` và `:` hai lần như renderer; `None` khi đường dẫn có ký tự ngoài chữ, số, `_ - . / :` và gạch ngược.
- `style_band_from_ass(text, style)` (`disclosure_band_from_ass` gọi nó), `karaoke_sample_ms(dialogue)` (giữa từ có thẻ k dài nhất).
- `InspectorSettings`: bỏ `subtitle_min_difference`, `disclosure_min_difference`, `baseline_min_gap_ms`; thêm `overlay_max_missing_share` (bắt buộc, 0 < x < 1, hữu hạn, không bool, không mặc định). Bỏ `baseline_ms`, `band_difference`, `band_pixels`.
- Wiring: `overlay_max_missing_share=0.25`, giữ band, 4 mẫu, 90x160, timeout.

Tệp đã sửa:

- `src/render/adapters/frame_probe.py`
- `src/render/adapters/real_output_inspector.py`
- `src/controlplane/api/wiring/render.py`
- `tests/integration/prod_wiring/test_pw_f1_inspector_visual.py`
- `tests/integration/prod_wiring/test_pw_f2_inspector_audio.py` (chỉ khối SETTINGS)
- `tests/integration/prod_wiring/test_pw_f4_render_worker.py` (chỉ khối SETTINGS)
- `tests/real/test_cp7_render_real.py` (chỉ khối SETTINGS, vẫn 20 mẫu)
- `docs/delivery-evidence/pw-f1-fix3/report.md`

## 3. Lệnh đã chạy

Interpreter khoá của lane, `PYTEST_DEBUG_TEMPROOT` riêng của lượt này.

**RED (bước 5, mới sửa test, mã HEAD chưa sửa)** — `python -m pytest tests/integration/prod_wiring/test_pw_f1_inspector_visual.py -q -p no:cacheprovider`, mã thoát 1:

`8 failed, 42 passed in 15.28s`

Ca hỏng: `test_pw_f1_correct_sample_passes_every_measured_gate`, `test_pw_f1_replaced_hook_fails_visual_hook_gate`, `test_pw_f1_karaoke_offset_beyond_tolerance_fails_karaoke_gate` (ba ca này hỏng vì mã cũ không thấy chữ đốt thật bằng bộ lọc `subtitles`), `test_pw_f1_fix3_scene_sample_without_text_fails_both_gates` (mã cũ PASSED vì khung mốc ở cảnh khác), `test_pw_f1_fix3_scene_sample_with_text_passes_three_of_three`, `test_pw_f1_fix3_no_text_other_text_or_shifted_text_fails_both_gates[other]`, `test_pw_f1_frame_probe_reads_duration_and_band_difference` (diff 0,0014 < 5,0 với chữ thật), `test_pw_f1_fix3_continuous_speech_render_passes_both_gates` (hỏng đúng oracle `subtitle_not_observed`, `evidence.subtitle` là `None`).

**GREEN (sau bản sửa)** — số ca của `test_pw_f1_inspector_visual.py` nay là 71 (trước bản sửa 50: 8 hỏng, 42 đạt; sau bản sửa 71 đạt):

| Bước | Lệnh | Mã thoát | Dòng tổng kết pytest |
| --- | --- | --- | --- |
| 18 | `python -m pytest tests/integration/prod_wiring/test_pw_f1_inspector_visual.py tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | `93 passed, 125 subtests passed in 22.96s` |
| 19 | `python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py tests/integration/prod_wiring/test_pw_f1_inspector_visual.py -q -p no:cacheprovider` | 0 | `87 passed in 72.42s (0:01:12)` |
| 20 | `python -m pytest tests/integration/prod_wiring/test_pw_f2_inspector_audio.py tests/integration/prod_wiring/test_pw_w2_fix6_qc_probe.py tests/integration/prod_wiring/test_pw_w2_fix7_audio_mix.py tests/integration/prod_wiring/test_pw_w2_launcher_def.py -q -p no:cacheprovider` | 0 | `42 passed in 34.25s` |
| 21 | `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider` | 0 | `10 passed, 1 warning in 132.26s (0:02:12)` |
| 22 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7607 passed, 1 warning, 2561 subtests passed in 25.75s` |
| 23 | `python -m pytest tests/real/test_cp7_render_real.py --collect-only -q -p no:cacheprovider` | 0 | `17 tests collected in 0.33s` |

Các lệnh `git diff --check` và năm probe `python -c` chỉ đọc (bước 25-32) được chạy ở bước kiểm cuối và đều mã thoát 0 (xem báo cáo `worker_done`).

## 4. Số đo từng mẫu

Đo bằng probe chỉ đọc gọi `FrameProbe.overlay_difference` đúng tại `karaoke_sample_ms` của từng dòng Karaoke được chọn (tối đa 4 dòng chia đều) và giữa cửa sổ Disclosure. Ngưỡng `overlay_max_missing_share` = 0,25.

**Ca giọng liền** (`test_pw_f1_fix3_continuous_speech_render_passes_both_gates`, render production qua `build_render_command` + `build_final_argv`, 3 dòng Karaoke sát nhau, dải Karaoke 0,7292-0,8125) — PASSED 3/3:

| Mẫu | Mốc (ms) | residual | ink | residual/ink |
| --- | --- | --- | --- | --- |
| Karaoke dòng 0 | 250 | 0,4398 | 11,7978 | 0,0373 |
| Karaoke dòng 1 | 1750 | 0,5632 | 15,1022 | 0,0373 |
| Karaoke dòng 2 | 3250 | 0,4023 | 10,2750 | 0,0392 |
| Disclosure seg-2 | 3000 | 0,4948 | 11,0686 | 0,0447 |

**Ca ba cảnh lavfi không chữ** (`build_scene_sample(burn=False)`, dải 0,7250-0,8750) — FAILED cả hai cổng (`frames_with_text == 0`; mã cũ PASSED cả hai):

| Mẫu | Mốc (ms) | residual | ink | residual/ink |
| --- | --- | --- | --- | --- |
| Karaoke dòng 0 | 500 | 11,6199 | 12,0723 | 0,9625 |
| Karaoke dòng 1 | 2500 | 11,9164 | 15,1252 | 0,7879 |
| Karaoke dòng 2 | 4500 | 7,8972 | 15,4581 | 0,5109 |
| Disclosure seg-2 | 3000 | 9,7333 | 10,5054 | 0,9265 |

**Ca ba cảnh lavfi có chữ** (`build_scene_sample(burn=True)`) — PASSED 3/3 và Disclosure PASSED:

| Mẫu | Mốc (ms) | residual | ink | residual/ink |
| --- | --- | --- | --- | --- |
| Karaoke dòng 0 | 500 | 0,7126 | 12,0723 | 0,0590 |
| Karaoke dòng 1 | 2500 | 0,4426 | 15,1252 | 0,0293 |
| Karaoke dòng 2 | 4500 | 0,1193 | 15,4581 | 0,0077 |
| Disclosure seg-2 | 3000 | 0,4585 | 10,5054 | 0,0436 |

## 5. Phản ví dụ đã loại trừ

- Không hạ `min_frames_with_text` (POLICY vẫn 2) và không hạ số mẫu (production 4, CP7-render 20).
- Không lấy khung mốc ở khoảnh khắc khác: mỗi mẫu so với chính nó sau khi vẽ lại ASS.
- Không tính khung có chữ chỉ vì ASS có dòng: phải `ink > 0` và `residual ≤ overlay_max_missing_share × ink`; thiếu ASS thì `subtitle` là `None` và Disclosure không visible.
- Không dùng hộp màu: test đốt chữ thật bằng bộ lọc `subtitles`; không có `drawbox` giả phụ đề trong test (chỉ `frame_probe.py` dùng `drawbox` để dựng khung xám tham chiếu `ink`).
- Không monkeypatch; FFmpeg ghim; test fix3 hỏng với mã cũ (RED ở mục 3).
- Ngưỡng nằm ở settings (`overlay_max_missing_share`), không có hằng trong inspector và không có mặc định.
- Không sửa `profile.json`, `karaoke_plan.py`, `ass_manifest.py`, `render_command.py`, `real_ffmpeg_renderer.py`, `content_gates.py`, `inspect_output.py`; không thêm thư viện.

## 6. Đính chính D8 của PW-F1

Câu đo ở `docs/delivery-evidence/pw-f1/report.md` mục 4 (D8) và ở `slices.md` mục PW-F1 ("so với khung không phụ đề", khung mốc ở giữa khoảng trống dài nhất ngoài cửa sổ phụ đề) được đính chính thành: so cùng một khung mẫu với chính nó sau khi vẽ lại ASS đã stage (`FrameProbe.overlay_difference`). Ý định giữ nguyên: đo khung hình, không coi là có chữ chỉ vì ASS có dòng. Disclosure đo giống `SUBTITLE_BURNED_IN` nên đổi cùng. `KARAOKE_TIMING` giữ nguyên.

Căn cứ `a15a18f2` (22/10/2026): việc kế hoạch đã duyệt có mà chưa nối do Control lập gói sửa; `OI-PW-F1-01` giao PW-F3/F4 cách đo khi phụ đề liền nhưng chưa gói nào làm, nên gói này làm.

## 7. Mục mở đã đóng và giới hạn

- `OI-PW-F1-01` đã đóng: giọng liền không còn `subtitle_not_observed` (không cần khung mốc).
- `OI-PW-F1-02` đã đóng: so cùng khung nên nền động hay nền tĩnh không làm tăng chênh lệch giả; dải Disclosure lấy từ hàng style của ASS, thiếu thì dùng band của settings.
- `OI-CP7-10-F10` đã đóng: lỗi `subtitle_not_observed` của job RG-09 có nguyên nhân gốc và bản sửa ở trên; bằng chứng thật là lượt CP7-10 kế tiếp.

Giới hạn:

- QC dựng lại ASS qua `ass_ref_for`: ASS đổi giữa render và QC thì FAIL (an toàn).
- QC cần cùng phông với máy render.
- Đường dẫn staging có ký tự ngoài chữ, số, `_ - . / :` và gạch ngược thì FAIL.
- Mỗi khung mẫu chạy hai lần FFmpeg (residual và ink), thêm vài giây mỗi video.
- RG-07 (CP7-8) chỉ thu thập (17 test), không chạy thật; bằng chứng thật là lượt CP7-10 kế tiếp.
