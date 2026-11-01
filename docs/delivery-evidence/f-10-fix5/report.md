# F-10-FIX5: trộn nền nhạc PrepareAudioBed vào mp4 dưới giọng

Mã gói: `F-10-FIX5`. Nhóm lỗi: `OI-F-10-BED-MIX`. Milestone: CP7.

## OI-F-10-BED-MIX

Mục mở D8 mục 5 của F-10 được đóng phần nhạc bằng gói này: nền nhạc do `PrepareAudioBed` chuẩn bị nay vào mp4 ở mức `audio.bed_gain_db` (-20 LU) so với giọng, trước `loudnorm` hai lượt. Phần SFX vẫn mở vì chưa có nguồn SFX. Không ducking vì chưa có mức duyệt. `OI-F-10-BED-MIX` đã đóng.

## 1. Mục tiêu và nguyên mẫu lỗi

Trên HEAD `4dbb431`: `PrepareAudioBed` ghi rendition vào `staging/audio_library` nhưng render bỏ qua (`mix_plan={}`, đồ thị chỉ trộn giọng với hook). Khoảng nghỉ của mp4 ở -78,3 dB; nguyên mẫu Kokoro thật cho bed chỉ thấp hơn giọng 13,5 LU khi áp tĩnh mức. Flow khử trùng ref theo `(ref_type, ref_id)` nên cần ref riêng cho từng cue.

## 2. Thay đổi theo từng tệp

- `src/controlplane/api/wiring/voice.py`: handler `PrepareAudioBed` thêm mỗi cue một ref `audio_bed_cue` (`ref_id` = `<operation_key>#<cue_index>`, `rendition_ref`, `start_ms`, `end_ms` dạng chuỗi, `staged_ref` khi tìm thấy tệp); `voice_activity_handlers` nhận `music_sources`, `music_transport`.
- `src/controlplane/api/wiring/render.py`: `resolve_inputs` đọc ref `audio_bed_cue`, kiểm định dạng (sai: `INVALID_INPUT`), chép phẳng `<rendition_ref>.wav` sau khi kiểm sha256 (sai: `INPUT_NOT_READY audio_bed_not_ready:<ref>`), đo loudness bằng FFmpeg ghim, tính `gain_db = bed_gain_db + L_giọng - L_rendition` (làm tròn 0,1), dựng cửa sổ bed, ghi `mix_plan`, thêm asset và manifest; `validation_context` đo `VerifiedArtifact` từ bản phẳng.
- `src/render/domain/resolve_package.py`: `rendition_ref` của `mix_plan.beds` được vào input; thiếu là `MISSING_REQUIRED` đúng field.
- `src/render/domain/render_command.py`: mỗi bed là một input `-t`/`-i` (token `{bed:i}`), `volume=..dB,adelay=..:all=1`, `amix=inputs=2+n` trước `loudnorm`; fingerprint có beds; không beds thì argv, đồ thị, fingerprint như cũ.
- `tests/integration/prod_wiring/test_f10_fix5_bed_mix.py`: test mới (27 ca).

## 3. Bằng chứng RED (mã nguồn chưa sửa)

`python -m pytest tests/integration/prod_wiring/test_f10_fix5_bed_mix.py -q -p no:cacheprovider`: thoát 1, **10 hỏng, 16 lỗi, 1 đạt** (27 ca).
- 10 hỏng đúng oracle hành vi: `KeyError: 'beds'` (mix_plan rỗng), không có asset bed, `DID NOT RAISE ResolveError`, `DID NOT RAISE RenderCommandRejected` (6 ca bed sai).
- 16 lỗi: `TypeError: voice_activity_handlers() got an unexpected keyword argument 'music_sources'` (hành vi thiếu của mã cũ; chạy được fixture thế giới render đến đúng điểm này).
- 1 đạt: `test_no_cue_refs_and_bed_none_only_keep_the_old_mix_plan` (hành vi cũ được giữ).

## 4. Bằng chứng GREEN và số đo

Sau bản sửa: **27 passed** cho test mới. Số đo thật (cảnh báo `f10-fix5 measurements`):

| Mục | Có bed | Không bed (bản cũ) |
| --- | --- | --- |
| mp4 integrated LUFS | -15,9 | -15,9 |
| mp4 true peak (dBFS) | -12,9 | -13,5 |
| Khoảng nghỉ (cả hai khoảng, atrim) | -35,9 LUFS | -70,0 LUFS (im lặng) |
| Thời lượng | 14000 ms (voice_duration_ms 14000) | - |
| md5 khung video | trùng bản không bed | - |

Theo từng bed: `voice_integrated_lufs` = -32,8; bed 0-8000 ms: `integrated_lufs` -16,0, `gain_db` -36,8; bed 8000-14000 ms: `integrated_lufs` -16,0, `gain_db` -36,8.

Mức bed so với giọng (`bed_gain_db` = -20): trong lời -15,6 LUFS, ngoài lời (nghỉ) -35,9 LUFS ở cả hai cặp cửa sổ, chênh 20,3 LU, lệch 0,3 LU so với -20 (ngưỡng 1 LU).

Ghi chú: bed A và giọng ban đầu cùng 220 Hz nên cộng pha cho lệch 1,3 LU (lỗi của test, không phải mã); đã đổi tần số bed sang 523/659 Hz.

## 5. Lệnh đã chạy

| Lệnh | Exit | Dòng tổng kết pytest |
| --- | --- | --- |
| `git diff --check` | 0 | - |
| pytest test_f10_fix5_bed_mix + test_f10_render_command_spec + test_f05_resolve_package + test_f01_package_layout | 0 | `344 passed, 1 warning, 125 subtests passed in 98.95s (0:01:38)` |
| pytest test_f10_fix4_render_loudness + test_f10_fix3_render_length + test_pw_f3_render_inputs | 0 | `64 passed in 38.62s` |
| pytest test_f17, f18, f19, f20, test_adapt_f_render | 0 | `221 passed in 4.87s` |
| pytest test_pw_f4_render_worker + test_pw_f1_inspector_visual | 0 | `87 passed in 74.16s (0:01:14)` |
| pytest test_pw_w2_fix7_audio_mix + test_pw_f2_inspector_audio + test_pw_w2_fix6_qc_probe | 0 | `29 passed in 31.15s` |
| pytest test_pw_e4_fix1_music_bed, test_pw_e4_audio_bed, test_pw_e3_media_inputs, test_pw_w2_launcher_def, test_pw_w2_fix5_bootstrap | 0 | `70 passed in 31.43s` |
| pytest test_adapt_wire_services + test_pw_e2e_batch_video | 0 | `150 passed, 1 warning in 169.63s (0:02:49)` |
| pytest tests/unit | 0 | `7610 passed, 1 warning, 2561 subtests passed in 24.03s` |
| 8 probe `python -c` (render_command x2, resolve_package, render.py x2, voice.py, test mới, CP2A-LAYOUT) | 0 | - |
| probe report.md | 0 | - |

## 6. Giới hạn

- Không ducking vì chưa có mức duyệt; muốn có cần user quyết (`pendingUserCheckpoint`, không tự coi là đã duyệt).
- SFX vẫn im lặng vì chưa có nguồn SFX.
- `L_rendition` đo trên cả bài nên đoạn đầu nhỏ thì nghe nhỏ hơn mức; bed vào, ra không fade.
- Cue dài hơn WAV thì bed hết trước cuối cửa sổ.
- Job đã qua process trước bản này render không bed.

## 7. Quyết định và open item còn lại

- Đã quyết: gain tính từ loudness đo thật, không viết hằng mức; render chỉ đọc `staged_ref`, không đọc hay ghi thư viện nhạc.
- Open item: ducking (cần user duyệt mức); SFX (cần nguồn SFX).
