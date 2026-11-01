# F-10-FIX3 — Render dài đúng giọng đo được

## Nhóm lỗi R36

`-t` đầu ra của `build_render_command` lấy cuối timeline kế hoạch (`timeline.duration_ms`, lập ở BuildProductionPlan trước TTS theo ước lượng số từ chia 136 wpm), nên mp4 ngắn hơn giọng khi giọng dài hơn kế hoạch. Ca production: job `fea412ea:video:2` có mp4 64,412 s so với giọng 66,197 s, mất 3 từ cuối. F-10-FIX2 che lỗi vì test FFmpeg thật dùng timeline bằng độ dài giọng.

## Các tệp đã sửa

- `src/render/domain/render_command.py`: `build_render_command` thêm tham số từ khoá `voice_duration_ms`, kiểm `invalid_voice_duration_ms` (int không bool, 0 < v <= 2**31-1), đặt `-t` ngay sau `-shortest`; `None` giữ cuối timeline (đổi tên `_voice_duration_ms` thành `_timeline_end_ms`).
- `src/controlplane/api/wiring/render.py`: `render_plan` đọc payload timing một lần, `INPUT_NOT_READY` với `word_timing_not_found` / `voice_duration_missing`, dựng ASS từ chính payload đó và truyền `voice_duration_ms=`.
- `tests/unit/render/test_f10_render_command_spec.py`: ca (a)-(d), gồm sửa test FFmpeg thật.
- `tests/integration/prod_wiring/test_f10_fix3_render_length.py`: test wiring mới (coveredIds: CT-RND-004).
- `docs/delivery-evidence/f-10-fix3/report.md`: báo cáo này.

## Lệnh kiểm đã chạy

Các lệnh pytest chạy bằng interpreter khoá của lane, kèm `PYTEST_DEBUG_TEMPROOT` riêng.

| Bước | Lệnh | Mã thoát | Dòng tổng kết pytest |
| --- | --- | --- | --- |
| 4 (RED, mã src cũ) | `pytest tests/integration/prod_wiring/test_f10_fix3_render_length.py` | 1 | `3 failed in 4.21s` (`-t` là `4.000` thay vì `5.250`/`3.950`; ca thiếu giá trị không ném `ActivityInputError`) |
| 8 | unit render spec + test_f10_fix3_render_length + test_pw_f3_render_inputs | 0 | `248 passed in 31.65s` |
| 9 | unit render spec `-rP -k pinned_ffmpeg_renders_mixed_size` | 0 | `2 passed, 197 deselected in 2.24s` |
| 10 | test_pw_f4_render_worker + test_pw_f1_inspector_visual | 0 | `60 passed in 53.34s` |
| 11 | test_f18 + test_f20 + test_adapt_f_render | 0 | `141 passed in 4.20s` |
| 12 | test_pw_w2_launcher_def + test_pw_w2_fix5_bootstrap + test_adapt_wire_services | 0 | `156 passed in 15.58s` |
| 13 | test_pw_e2e_batch_video | 0 | `10 passed, 1 warning in 123.29s (0:02:03)` |
| 14 | `pytest tests/unit` | 0 | `7563 passed, 1 warning, 2561 subtests passed in 22.53s` |
| 15-19 | 5 probe `python -c` chỉ đọc (render_command, wiring/render, hai tệp test, cây wiring, packaging và import `src.`) | 0 | không áp dụng |
| 21 | probe `python -c` báo cáo (`F-10-FIX3`, `R36`) | 0 | không áp dụng |
| 22 | `git diff --check` | 0 | không có cảnh báo |

## Bằng chứng FFmpeg thật

Test `test_pinned_ffmpeg_renders_mixed_size_stills_to_the_voice_length` truyền `voice_duration_ms=3000` với timeline ngắn hơn (2000 ms) và dài hơn (5000 ms) giọng. Hai dòng đầu ra nguyên văn:

```
F10FIX3 timeline_ms=2000 output_t=3.000 mp4_s=3.000000 frames=90
F10FIX3 timeline_ms=5000 output_t=3.000 mp4_s=3.000000 frames=90
```

Khung 2800 ms giống `tall.png` (similarity >= 0,85) và khác `small.png` (< 0,85), tức khung cuối được giữ tới hết giọng.

## Ghi chú lệch so với gói

Bảng `cp_word_timings` có UNIQUE(`timing_artifact_ref`) và trigger append-only nên không chèn được revision 2 cùng ref. Test wiring chèn revision 1 với `voice_duration_ms` 5250 / 3950 trước `build_world` (`insert_timing` của PW-F3 dùng ON CONFLICT DO NOTHING nên bỏ qua).

## Backlog ngoài phạm vi

- Không cổng QC nào so độ dài mp4 với giọng.
- Bed nhạc nền dài theo cue kế hoạch; khi được nối phải theo giọng.
- E2E có timeline bằng giọng nên không bắt được lỗi này.
