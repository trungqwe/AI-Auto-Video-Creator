# Báo cáo chuyển giao: ADAPT-F

## 1. Tóm tắt
ADAPT-F thêm real_ffmpeg_renderer.py và real_ffprobe_probe.py.

## 2. Tệp đã thêm
- `src/render/adapters/real_ffmpeg_renderer.py`
- `src/render/adapters/real_ffprobe_probe.py`
- `tests/integration/adapt/f/test_adapt_f_render.py`
- `docs/delivery-evidence/adapt-f/report.md`

## 3. Lệnh đã chạy
| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider` | 0 | 53 passed in 3.49s |
| `python -c "import pathlib; d = pathlib.Path('src/render/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_ffmpeg_renderer.py', 'real_ffprobe_probe.py']); assert 'h264_nvenc' in t and 'libx264' in t and 'subtitles' in t and 'shell=True' not in t and 'from src.' not in t, 'adapter F'"` | 0 | Đạt (exit code 0) |
| `git diff --check` | 0 | Đạt (exit code 0) |

## 4. Quyết định thiết kế
- output_ref là đường dẫn đầu ra (phần tử cuối argv) của RenderCommandSpec nên output_artifact_ref của G phải trùng đường dẫn này (GIẢ ĐỊNH, chốt ở CONV-F-02);
- adapter chỉ chạy spec kind render, argv[0] phải trùng ffmpeg_path đã kiểm sha256;
- adapter thay filter ass bằng subtitles, thêm crop, tham số p5/vbr/cq23 và libx264 crf 21 theo plan.md 7.4, bỏ -b:v của spec;
- metrics là số nên encoder ghi thành encoder_h264_nvenc trong gpu_metrics hoặc encoder_libx264 trong cpu_metrics và thêm thuộc tính last_encoder;
- dự phòng libx264 chỉ khi stderr có dấu hiệu NVENC không khởi tạo (nvenc, nvcuda, cuda, could not open encoder, error initializing output stream), đúng một lần, dùng chung hạn timeout;
- tệp đầu ra có sẵn không bị ghi đè (FAILED output_already_exists);
- pin sai, BLOCKED hoặc thiếu ném FfmpegPinRejected trước khi lấy lease;
- lease nhận qua constructor (bắt buộc) và owner_ref là spec_fingerprint;
- ffprobe không có pin trong runtime.lock.json nên không kiểm sha256 ffprobe;
- container map thành mp4 cho họ mov/mp4 trừ major_brand qt;
- audio_level và severe_audio_errors không đo nên là None.

## 5. Mục mở
- RenderPipeline của F-18 cũng lấy GpuLeasePort quanh run() nên khi lắp ráp ở CONV-F-02 phải chọn một nơi giữ lease để không giữ hai slot cho một render (slots 2);
- render NVENC thật, đo thời gian và preset thật thuộc CP7-F-01;
- ffmpeg và ffprobe trong test là script Python giả;
- không có RED hợp lệ cho module mới (lỗi import không phải RED) nên phản ví dụ được kiểm trực tiếp bằng test.
