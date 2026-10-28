# Báo cáo bằng chứng F-10-FIX2

## Nhóm lỗi R9

Gói F-10-FIX2 giải quyết nhóm lỗi R9 (lệnh render) và nhóm lỗi R10 (phân giải hook, thumbnail) của phân hệ Render:
- Trước khi sửa, `build_render_command` chỉ ghép visual của segment, phụ đề ASS và voice nên không có visual hook và audio hook thực sự trong output; tiêu chí VISUAL_HOOK chỉ đạt khi tình cờ ảnh nền giống hook, và AUDIO_HOOK đạt nhờ giọng đọc lấp cửa sổ hook.
- Khi AI chọn thumbnail là ảnh tĩnh khác visual hook (`thumb:<media_asset_id>`), thumbnail không xuất hiện trong output.

Cách sửa:
- Đọc `manifest[visual_hook_ref]`, `manifest[audio_hook_ref]`, `manifest[thumbnail_ref]` qua `_local_path` (thiếu trong manifest thì báo `RenderCommandRejected(ASSET_NOT_MATERIALIZED, field_name)`; thiếu trường trong hook_placement thì báo `RenderCommandRejected(INPUT_NOT_READY, f"missing_{field_name}")`).
- Visual hook đưa vào FFmpeg với cờ `-t <độ dài hook_time_range>`, chuẩn hoá khung hình như F-10-FIX1, dùng `setpts` dời mốc `start_ms`, `overlay` lên luồng nền (`[base]`) với `enable='between(t,start,end)'` và `eof_action=repeat` tường minh, đặt trước bộ lọc `ass`.
- Khi `_local_path(manifest[thumbnail_ref])` khác đường dẫn của `visual_hook_ref`, phủ khung đầu của asset thumbnail (ảnh dùng `-loop 1`, clip dùng `trim=end_frame=1`, chuẩn hoá tỷ lệ) lên trên hook trong `thumbnail_time_range` (`enable='between(...)'`); khi cùng đường dẫn thì không phủ thêm overlay.
- Audio hook đưa qua `adelay=start_ms` rồi ghép với voice qua `amix=inputs=2:duration=first:normalize=0` (đặt voice ở đầu vào đầu tiên để giọng đọc không bị nhỏ đi và ổn định độ dài stream audio).
- Luồng map đầu ra là `-map [vout] -map [aout] -shortest`. Đồng thời bổ sung `-t <độ dài voice>` cho output lấy từ dữ liệu `record/timeline` để luồng FFmpeg filtergraph kết thúc sạch sẽ (theo chỉ đạo bổ sung của Control).

## Các tệp đã sửa

- `src/render/domain/render_command.py`: thêm `_chain`, `_HookPlan`, `_hook_plan`, `_overlay`, `_shifted`, `_voice_duration_ms`, `_timed_input`; cập nhật `_normalise`, `_filter_graph`, `build_render_command`.
- `tests/unit/render/test_f10_render_command_spec.py`: cập nhật cấu trúc argv và filter graph trong các test hiện có; thêm các test unit kiểm tra từ chối hook không hợp lệ, overlay thumbnail riêng biệt; thêm helper `render_hook_scene` và 2 test chạy FFmpeg đã ghim thật kiểm tra SSIM hook/thumbnail và phổ âm thanh; cập nhật tham số `duration_ms` cho voice trong test ghim.
- `docs/delivery-evidence/f-10-fix2/report.md`: báo cáo bằng chứng thực thi gói F-10-FIX2.

## RED

- Lệnh: `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider`
- Mã thoát: `1`
- Dòng tổng kết nguyên văn của pytest:
```text
23 failed, 164 passed in 5.45s
```

## GREEN

- Lệnh: `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider`
- Mã thoát: `0`
- Dòng tổng kết nguyên văn của pytest:
```text
187 passed in 8.04s
```

## Lệnh kiểm

| Lệnh | Mã thoát | Kết quả |
| --- | --- | --- |
| `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider` | 0 | 187 passed in 8.04s |
| `git diff --check` | 0 | Đạt (không có lỗi khoảng trắng thừa) |
| Probe `python -c` đọc `report.md`, kiểm có `F-10-FIX2` và `R9` | 0 | Đạt (khớp F-10-FIX2 và R9) |
| `python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider` | 1 | 1 failed, 53 passed in 3.93s |

## Ảnh hưởng ngoài owned paths

- Kết quả bước 14 khi chạy kiểm thử ngoài owned paths (`tests/integration/adapt/f/test_adapt_f_render.py`):
  - Mã thoát: `1`
  - Dòng tổng kết nguyên văn:
  ```text
  1 failed, 53 passed in 3.93s
  ```
  - Test bị fail: `tests/integration/adapt/f/test_adapt_f_render.py::test_command_is_an_argument_list_with_production_parameters`
  - Nguyên nhân: Test assert chuỗi con `'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30'` trong filter graph thiếu `setsar=1` đã chuẩn hoá từ gói F-10-FIX1. Tệp này nằm ngoài owned paths nên Worker không tự ý chỉnh sửa; cần Control hoặc gói chủ cập nhật.
  - Các tệp kiểm thử `tests/integration/prod_wiring/test_pw_f3_render_inputs.py` và `test_pw_f4_render_worker.py` cũng gọi `build_render_command` nhưng nằm ngoài phạm vi owned paths của gói này.

## Quyết định và giới hạn

- Thứ tự đầu vào FFmpeg: các segment timeline (0..count-1), voice (count), visual hook (count+1), audio hook (count+2), và thumbnail asset (count+3 nếu khác đường dẫn visual hook).
- Audio hook cũng bị `-t` cắt theo độ dài `hook_time_range`.
- Thumbnail có cùng đường dẫn với visual hook sẽ không thêm tầng overlay phụ để tối ưu hiệu năng render.
- Không sửa đổi hàm `build_thumbnail_command` và adapter `src/render/adapters/real_ffmpeg_renderer.py`.
- Tuân thủ quy chuẩn quản trị tác vụ: chỉ chạy targeted tests theo work order, không tự ý chạy full regression suite.
