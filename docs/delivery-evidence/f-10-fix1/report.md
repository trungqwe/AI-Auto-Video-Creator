# Báo cáo bằng chứng F-10-FIX1

## Nhóm lỗi R9

Gói F-10-FIX1 sửa nhóm lỗi R9 (lệnh render của phân hệ Render):
- Trước khi sửa, `build_render_command` đưa mỗi visual vào FFmpeg chỉ bằng `-i <tệp>` rồi `concat=n=N`, không có `-loop 1` hay `-t`, nên ảnh tĩnh chỉ có 1 khung (khoảng 0,033 giây); phụ đề và disclosure không có khung nào để vẽ.
- Bộ lọc `scale` đứng sau `concat` nên ảnh khác kích thước làm FFmpeg lỗi ("Input link ... do not match", mã thoát khác 0).
- Độ dài đầu ra không bám độ dài voice khi timeline ngắn hoặc dài hơn voice.

Cách sửa:
- Thời lượng segment i = `end_ms - start_ms`; thiếu hoặc không phải số nguyên thì `INPUT_NOT_READY`, `end_ms <= start_ms` thì `INVALID_INPUT`.
- `media_type` lấy từ `record.input_artifacts` theo ref. Ảnh `image/*` vào bằng `-loop 1 -framerate <fps> -t <giây> -i`, loại khác vào bằng `-t <giây> -i`.
- Mỗi đầu vào chuẩn hoá trước `concat`: `scale=W:H:force_original_aspect_ratio=increase,crop=W:H,setsar=1,fps=F,format=<pix>`.
- Sau `concat` thêm `tpad=stop_mode=clone:stop=-1` rồi mới `ass=filename=...`, và thêm `-shortest` để output dài đúng bằng voice.
- `redacted_argv` và `spec_fingerprint` đổi theo; `build_thumbnail_command` và `real_ffmpeg_renderer.py` không đổi.

## Các tệp đã sửa

- `src/render/domain/render_command.py`: thêm `IMAGE_MEDIA_PREFIX`, `_duration_ms`, `_seconds`, `_is_still_image`, `_normalise`; cập nhật `_filter_graph`, `_make_spec`, `build_render_command`.
- `tests/unit/render/test_f10_render_command_spec.py`: cập nhật test graph; thêm test `-loop`, `-t`, `-shortest`, chuẩn hoá trước concat, từ chối đầu vào không hợp lệ và 2 test chạy FFmpeg đã ghim thật với ảnh khác kích thước.
- `docs/delivery-evidence/f-10-fix1/report.md`: báo cáo này, ghi lại bằng UTF-8 đủ dấu để sửa lỗi mất dấu.

## RED (ghi nhận từ lần chạy trước khi sửa mã)

- Lệnh: `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider`; mã thoát `1`.
```text
17 failed, 153 passed in 0.84s
```

## GREEN

- Lệnh: như trên, chạy lại ở bước 1 của lệnh làm việc; mã thoát `0`.
```text
170 passed in 1.77s
```

## Lệnh kiểm

| Lệnh | Mã thoát | Kết quả |
| --- | --- | --- |
| pytest đích như trên | 0 | 170 passed in 1.77s |
| Probe `python -c` đọc `report.md`, kiểm có `F-10-FIX1` và `R9` | 0 | Đạt |
| `git diff --check` | 0 | Đạt |
| `python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider` (ghi nhận từ lần chạy trước) | 1 | 1 failed, 53 passed in 3.91s |

## Ảnh hưởng ngoài owned paths

- `tests/integration/adapt/f/test_adapt_f_render.py::test_command_is_an_argument_list_with_production_parameters` (dòng 182) fail vì còn assert chuỗi con cũ `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30`, trong khi R9 bắt buộc có `setsar=1` giữa `crop` và `fps`. Tệp này ngoài owned paths nên Worker không sửa; cần Control hoặc gói chủ cập nhật.

## Quyết định và giới hạn

- Ref không có trong `input_artifacts` được coi là loại media khác và vào bằng `-t <giây> -i`.
- Nhóm lỗi R10 (phân giải hook, thumbnail) không thuộc phạm vi gói F-10-FIX1.
- Chỉ chạy test đích, không chạy full suite.
