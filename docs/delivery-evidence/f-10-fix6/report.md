# F-10-FIX6: ảnh bất kỳ tỉ lệ nào hiện trọn trong khung dọc

Mã gói: `F-10-FIX6`. Nhóm lỗi: `OI-CP7-11-Q1`. Milestone: CP7.

## 1. Lỗi và nhóm lỗi OI-CP7-11-Q1

Trên HEAD `7fa09bf` (CP7-11), ảnh ngang trong khung 1080x1920 chỉ còn dải giữa vì `_chain` và `ssim_between` của QC phủ kín mọi ảnh (scale tăng tỉ lệ + crop). Gói này thêm bộ dựng duy nhất `frame_placement`: ảnh gần tỉ lệ khung thì phủ kín, ảnh khác tỉ lệ được đặt trọn giữa khung trên nền là chính ảnh làm mờ và làm tối. Cảnh ảnh tĩnh có thêm zoom chậm 1,00 đến 1,06. `OI-CP7-11-Q1` đã đóng bằng gói này.

Giới hạn còn lại:

- Ảnh rất rộng (3:1) chỉ zoom, chưa trượt ngang.
- Cảnh clip đặt vị trí mỗi khung, không zoom (thêm khoảng 1-2 ms lọc mỗi khung).
- Ảnh nhỏ được phóng vừa ô fit dù mờ hơn.
- Zoom cập nhật 15 lần mỗi giây.
- Test PostgreSQL và `tests/real/test_cp7_render_real.py` không chạy trong gói này.

## 2. Các tệp đã sửa

- `src/render/domain/render_command.py`: thêm 6 hằng (`COVER_ASPECT_TOLERANCE`, `SCENE_ZOOM`, `ZOOM_FRAME_STEP`, `BACKDROP_SHRINK`, `BACKDROP_BLUR_SIGMA`, `BACKDROP_LEVEL`), `frame_placement`, `_segment_frames`, `_scene_zoom`; `_chain` nhận `prefix`, `head`, `motion`; `_normalise`, `_shifted`, `_filter_graph` (nhận `[(still, duration_ms)]`) và `build_render_command` đi theo.
- `src/render/adapters/real_output_inspector.py`: `ssim_between` có `canvas` dựng bên phải bằng `frame_placement(canvas[0], canvas[1], 'qc') + ',' + prep`.
- `src/render/adapters/real_ffmpeg_renderer.py`: `_rewrite_graph` chỉ còn đổi `ass=` thành `subtitles=`; sửa docstring module.
- `tests/integration/render/test_f10_fix6_frame_placement.py`: tệp mới, 6 test chạy FFmpeg ghim thật, không DB, không monkeypatch hay mock.
- `tests/unit/render/test_f10_render_command_spec.py`: pin dựng từ `frame_placement`; thêm `test_frame_placement_is_pinned`, `test_still_scene_frame_count` (8 ca); ảnh tĩnh so ở `first + 33` ms. Ngoài lệnh làm việc, sửa thêm `test_loudnorm_follows_amix_with_the_preset_values`: tìm vị trí chuỗi amix theo nội dung thay vì chỉ số cố định 3 (đồ thị nay có thêm dấu chấm phẩy của `frame_placement`); nội dung kỳ vọng giữ nguyên.
- `tests/integration/adapt/f/test_adapt_f_render.py`: dòng 182 dùng `frame_placement(1080, 1920, 's0')`.
- `docs/delivery-evidence/f-10-fix6/report.md`: báo cáo này.

## 3. Bộ lọc của cảnh, hook, thumbnail

`frame_placement(1080, 1920, 's0')` (in thật từ `render_command`):

```
split=2[s0in0][s0in1];[s0in0]crop=w='min(iw,ih*1080/1920)':h='min(ih,iw*1920/1080)',scale=135:240,gblur=sigma=6,colorchannelmixer=rr=0.5:gg=0.5:bb=0.5,scale=1080:1920:flags=bilinear[s0back];[s0in1]scale=w='if(lt(abs(a*1920/1080-1),0.06),max(1080,1920*a),min(1018,1811*a))':h='if(lt(abs(a*1920/1080-1),0.06),max(1920,1080/a),min(1811,1018/a))',crop=w='min(iw,1080)':h='min(ih,1920)'[s0pic];[s0back][s0pic]overlay=x='(W-w)/2':y='(H-h)/2'
```

Motion của cảnh ảnh tĩnh 3000 ms, 30 fps (90 khung); cảnh ảnh tĩnh có thêm `trim=end_frame=1,` đứng trước `frame_placement`:

```
,loop=loop=89:size=1,setpts=N/30/TB,select='not(mod(n,2))',perspective=x0='W*0.03*(in-1)*2/90/(1+0.06*(in-1)*2/90)':y0='H*0.03*(in-1)*2/90/(1+0.06*(in-1)*2/90)':x1='W-W*0.03*(in-1)*2/90/(1+0.06*(in-1)*2/90)':y1='H*0.03*(in-1)*2/90/(1+0.06*(in-1)*2/90)':x2='W*0.03*(in-1)*2/90/(1+0.06*(in-1)*2/90)':y2='H-H*0.03*(in-1)*2/90/(1+0.06*(in-1)*2/90)':x3='W-W*0.03*(in-1)*2/90/(1+0.06*(in-1)*2/90)':y3='H-H*0.03*(in-1)*2/90/(1+0.06*(in-1)*2/90)':eval=frame
```

Hook (`vhook`) và thumbnail (`vthumb`) dùng cùng `frame_placement` với tiền tố của mình, không head, không motion; cảnh clip dùng nhãn `s<i>`, cũng không head, không motion. Đuôi chung của mọi chuỗi: `,setsar=1,fps=<fps>,format=<pix>`.

## 4. Bằng chứng RED và GREEN

RED (mã nguồn chưa sửa, bước 11): `21 failed, 303 passed, 1 warning in 44.89s`. Hỏng đúng oracle: 6 test mới của tệp tích hợp (thiếu dấu mép, nền ngang `backdrop_step=140` > 16, không zoom, khung hình sai), 5 pin đồ thị cũ, `test_frame_placement_is_pinned`, 8 ca `test_still_scene_frame_count`, và test của `test_adapt_f_render.py` (`AttributeError`: thiếu `frame_placement`). Không có test mới hay pin đã sửa nào đạt trên mã cũ.

GREEN (sau khi sửa mã): nhóm 1 `324 passed, 4 warnings in 58.28s`; nhóm 2 `90 passed in 82.63s (0:01:22)`; nhóm 3 `167 passed in 1.04s`; nhóm 4 `7648 passed, 1 warning, 2561 subtests passed in 30.24s`.

## 5. Lệnh đã chạy

Mọi lệnh pytest đặt `PYTEST_DEBUG_TEMPROOT=C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\F-10-FIX6-implement-r0-ac1b5c0961` và dùng interpreter khoá của lane.

| Lệnh | Exit | Dòng tổng kết |
| --- | --- | --- |
| `git diff --check` | 0 | (không in lỗi) |
| pytest nhóm 1 (fix6, unit render spec, adapt F render, fix4 loudness, f09 ass wrap) | 0 | `324 passed, 4 warnings in 58.28s` |
| pytest nhóm 2 (prod_wiring PW-F1, D10, QC probe, audio mix) | 0 | `90 passed in 82.63s (0:01:22)` |
| pytest nhóm 3 (F17-F20) | 0 | `167 passed in 1.04s` |
| pytest nhóm 4 (`tests/unit`) | 0 | `7648 passed, 1 warning, 2561 subtests passed in 30.24s` |
| probe CP2A-LAYOUT | 0 | (không in) |
| 16 probe `python -c` còn lại của danh sách lệnh kiểm (bộ dựng, QC, `_rewrite_graph`, tên test, pin, render command, loudness, bed mix, overlay, inspector, PW-F1, PW-F2, hai pass, unit, loudness test, hook_similarity_min = 0.85) | 0 | (không in) |
| probe báo cáo | 0 | (không in) |

## 6. Số đo F10FIX6 (warnings summary của nhóm 1)

- `F10FIX6 backdrop_step=4 backdrop_mean=62.6 picture_mean=123.2`
- `F10FIX6 red_start_31=20 red_start_89=0 shift=20`
- `F10FIX6 hook_gate=PASSED thumbnail_gate=PASSED`
- `F10FIX6 frames=90 edge37=119.50 zoom_shift_10_36=17.78`

## 7. Thời gian render một cảnh ảnh tĩnh 10 s, 30 fps

Đây là số đo của nguyên mẫu Control (kèm hook 1,5 s, ASS, âm thanh; trung vị 7 lần xen kẽ; cũ rồi mới). Worker không đo lại.

| Encoder và khung ảnh | Cũ | Mới | Tỉ lệ |
| --- | --- | --- | --- |
| libx264, 1080x608 | 1,25 s | 1,76 s | 1,41 |
| libx264, 1600x900 | 1,64 s | 1,93 s | 1,17 |
| libx264, 1080x1920 | 1,35 s | 1,85 s | 1,37 |
| h264_nvenc, 1080x608 | 1,45 s | 1,55 s | 1,07 |
| h264_nvenc, 1600x900 | 1,43 s | 1,59 s | 1,11 |
| h264_nvenc, 1080x1920 | 1,43 s | 1,67 s | 1,16 |

## 8. Kết quả QC (nguyên mẫu Control)

SSIM của QC giữa khung thumbnail và ảnh 1200x630 tối dựng qua `frame_placement` là 0,9999; visual hook là 0,99988. Ngưỡng 0,85 không đổi. Trong gói này, cả hai cổng `VISUAL_HOOK_PRESENT` và `THUMBNAIL_PRESENT` đều PASSED trên mp4 render thật (mục 6).

## 9. Quyết định và open item còn lại

- Quyết định: một bộ dựng `frame_placement` duy nhất cho cảnh, hook, thumbnail và SSIM của QC; `_rewrite_graph` không còn viết lại scale hay crop; số khung cảnh ảnh tĩnh tính bằng `_segment_frames` (làm tròn nửa lên) để khớp `-loop 1 -t` cũ.
- Không đổi: ngưỡng QC 0,85, khoá profile, đối số input, overlay hook và thumbnail, âm thanh, `build_thumbnail_command`.
- Open item: trượt ngang ảnh rất rộng và zoom cho clip nằm ngoài phạm vi; test PostgreSQL và `tests/real/test_cp7_render_real.py` chưa chạy trong gói này.
