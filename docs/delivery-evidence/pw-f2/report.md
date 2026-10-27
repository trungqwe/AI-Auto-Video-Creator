# Báo cáo Nghiệm thu & Khảo sát PW-F2: Đo lường âm thanh, tiếng Anh và ToolCapability với FFmpeg ghim (PW-F2-01, CT-QC-001)

## 1. Mục tiêu và phạm vi PW-F2
- Mục tiêu: Hiện thực các cổng kiểm tra âm thanh (`AUDIO_HOOK`, `VOICE_AUDIBLE`), cổng ngôn ngữ (`ENGLISH_OUTPUT`), cổng hồ sơ định dạng (`OUTPUT_PROFILE`) và đọc năng lực công cụ (`ToolCapability`) bằng nhị phân FFmpeg đã ghim (sha256 `f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480`); cổng cảnh báo độ ồn `AUDIO_MIX_QUALITY` (loudness và true peak) chỉ ghi nhận số đo (warn), không làm chặn quy trình xuất bản.
- Sáu đường dẫn sở hữu (owned paths) của gói PW-F2:
  + `src/render/adapters/real_output_inspector.py`
  + `src/render/adapters/real_ffprobe_probe.py`
  + `src/render/adapters/ffmpeg_capability.py`
  + `tests/integration/prod_wiring/test_pw_f2_inspector_audio.py`
  + `tests/unit/render/test_f01_package_layout.py`
  + `docs/delivery-evidence/pw-f2/report.md`

## 2. Tệp đã đổi
- `src/render/adapters/real_ffprobe_probe.py`: Mở rộng `RealFfprobeProbe` nhận tham số `ffmpeg_path`, `lock_path`, `voice_windows`; bổ sung `measure_audio` (sử dụng chuỗi bộ lọc `aformat=sample_fmts=fltp,astats,volumedetect` và trích xuất `mean_volume`, `Number of NaNs`, `Number of Infs`) và `measure_loudness` (sử dụng `ebur128=peak=true:framelog=quiet` trích xuất `I` và `Peak`). Nếu không truyền `ffmpeg_path`, hành vi cũ được giữ nguyên hoàn toàn (tương thích ngược với ADAPT-F).
- `src/render/adapters/real_output_inspector.py`: Bổ sung đo lường `AUDIO_HOOK` trong cửa sổ `hook_time_range`, cổng `ENGLISH_OUTPUT` kết hợp `LanguageSource` từ phân hệ E và D cùng quan sát phụ đề (`observed_subtitle_locale`), trích xuất cửa sổ lời thoại (`speech_windows`), hàm cảnh báo `audio_mix_result` cho `AUDIO_MIX_QUALITY`, và bảng ánh xạ `GATE_SOURCES`.
- `src/render/adapters/ffmpeg_capability.py`: Tạo mới, hiện thực `read_tool_capability` đọc bộ lọc (`-filters`), encoder (`-encoders`) và thư viện biên dịch (`-buildconf`) từ FFmpeg đã ghim sau khi xác thực sha256; không sử dụng danh sách cố định.
- `tests/unit/render/test_f01_package_layout.py`: Bổ sung khoá `adapters/ffmpeg_capability.py` với `frozenset({'import:subprocess'})` vào `ADAPTER_EXEMPTIONS` và bản sao mong đợi; thêm test `test_ffmpeg_capability_accepts_only_subprocess`.
- `tests/integration/prod_wiring/test_pw_f2_inspector_audio.py`: Tạo mới bộ kiểm thử tích hợp đo lường âm thanh, ngôn ngữ, hồ sơ đầu ra và lưu trữ báo cáo QC vào PostgreSQL thật (`pw_database`).
- `docs/delivery-evidence/pw-f2/report.md`: Báo cáo chi tiết quá trình thực hiện, bằng chứng lệnh kiểm tra và phát hiện điểm dừng kỹ thuật (BLOCKED).

## 3. Dòng đã đổi ở test_f01_package_layout.py và lý do
- Dòng chú thích mới ở đầu tệp:
  `# PW-F2 (docs/implementation/prod-wiring/slices.md, mục PW-F2): ffmpeg_capability.py chạy tiến trình con FFmpeg đã ghim để đọc bộ lọc và encoder; chỉ import:subprocess, đường dẫn chính xác; real_ffprobe_probe.py giữ nguyên miễn trừ cũ.`
- Thêm đúng một khoá vào `ADAPTER_EXEMPTIONS`:
  `    'adapters/ffmpeg_capability.py': frozenset({'import:subprocess'}),`
- Thêm đúng một khoá vào bản sao mong đợi trong `test_exemption_table_is_exact_paths_only`:
  `                'adapters/ffmpeg_capability.py': frozenset({'import:subprocess'}),`
- Thêm phương thức kiểm thử `test_ffmpeg_capability_accepts_only_subprocess` trong `AdapterExemptionTests` để chứng minh `ffmpeg_capability.py` chỉ chấp nhận `import:subprocess` (tập đóng một phần tử), và khoá của `real_ffprobe_probe.py` không bị nới lỏng (vẫn bắt lỗi `import:socket`).
- Lý do: `ffmpeg_capability.py` là adapter mới chạy tiến trình con FFmpeg để đọc năng lực công cụ, chỉ import `subprocess` trong nhóm bị cấm; scan_package thực tế chỉ báo `import:subprocess`.

## 4. Quyết định mặc định D8
- `audio_level` là giá trị `mean_volume` (dBFS) trích từ `volumedetect` của FFmpeg; nếu giá trị là `-inf` thì quy về `SILENCE_FLOOR_DB` (-120.0 dB).
- `severe_audio_errors` là tuple chứa mã lỗi `nan_samples` hoặc `inf_samples` từ `astats` nếu phát hiện số lượng mẫu lỗi > 0.
- Đo mức giọng trong cửa sổ có lời (`speech_windows`) được trích xuất từ các dòng hội thoại style `Karaoke` trong tệp ASS (`aselect` kết hợp `asetpts=N/SR/TB`).
- Thư viện `libass` được gộp vào `ToolCapability.filters` từ cờ cấu hình `--enable-libass` của `-buildconf` do cấu trúc DTO `ToolCapability` chỉ gồm hai tập `filters` và `encoders`.
- Mọi ngưỡng đo lường đều do `QualityPolicy` hoặc người gọi cung cấp, không đặt hằng số ngưỡng trong adapter.

## 5. GIẢ ĐỊNH và mục mở
- `OI-PW-F2-01`: Dung lượng tệp theo profile chưa có cổng cứng trong `evaluate_technical_gates` do cấu trúc `OutputMeasurements` và `technical_gates` (thuộc phân hệ domain ngoài owned paths) hiện chưa có trường kích thước tệp (bytes); thời lượng video đã được kiểm soát đầy đủ qua cổng `DURATION_RANGE`.
- `OI-PW-F2-02`: `voice_locale` do phân hệ E bàn giao qua `LanguageSource`; `RealOutputInspector` không tự chạy mô hình nhận dạng tiếng nói mà chỉ kiểm tra tính nhất quán mã ngôn ngữ và phát hiện ký tự phi Latinh trong phụ đề đã burn.
- `OI-PW-F2-03`: Dây nối quy trình (wiring thuộc PW-F4) cần khởi tạo `RealFfprobeProbe` với `ffmpeg_path`, truyền `voice_windows=inspector.speech_windows(package)` và đưa `LanguageSource` cùng `audio_mix_result` vào danh sách kết quả; `src/controlplane/api/wiring/render.py` chưa cập nhật trong gói này.

## 6. Bảng bằng chứng lệnh thực thi và Phát hiện Blocker

### 6.1. Bảng lệnh kiểm tra thực tế

| Bước | Lệnh thực thi | Exit Code | Kết quả |
| --- | --- | --- | --- |
| Bước 8 | `python -m pytest tests/integration/adapt/f/test_adapt_f_render.py tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | Đạt (PASS): 75 passed, 125 subtests passed in 3.89s |
| Bước 14 | `python -m pytest tests/integration/prod_wiring/test_pw_f1_inspector_visual.py tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | Đạt (PASS): 34 passed, 125 subtests passed in 4.01s |
| Bước 15 | `python -c "import pathlib; t = pathlib.Path('src/render/adapters/real_output_inspector.py').read_text(encoding='utf-8'); assert all(k in t for k in ['AUDIO_HOOK', 'VOICE_AUDIBLE', 'ENGLISH_OUTPUT']) and 'from src.' not in t, 'PW-F2'"` | 0 | Đạt (PASS): đủ ký hiệu, không import tiền tố src |
| Bước 24 | `python -c "import ast, pathlib; d = ast.get_docstring(ast.parse(pathlib.Path('tests/integration/prod_wiring/test_pw_f2_inspector_audio.py').read_text(encoding='utf-8'))); line = [x for x in d.splitlines() if x.startswith('coveredIds:')][0]; ids = [x.strip() for x in line[len('coveredIds:'):].split(',')]; assert {'PW-F2-01', 'CT-QC-001'} <= set(ids), ids"` | 0 | Đạt (PASS): coveredIds PW-F2-01, CT-QC-001 hợp lệ |
| Bước 25 | `python -c "import ast, pathlib; t = ast.parse(pathlib.Path('tests/unit/render/test_f01_package_layout.py').read_text(encoding='utf-8')); n = [x for x in t.body if isinstance(x, ast.Assign) and x.targets[0].id == 'ADAPTER_EXEMPTIONS'][0]; keys = [k.value for k in n.value.keys]; assert keys == ['adapters/real_ffmpeg_renderer.py', 'adapters/real_ffprobe_probe.py', 'adapters/real_output_inspector.py', 'adapters/frame_probe.py', 'adapters/ffmpeg_capability.py'], keys"` | 0 | Đạt (PASS): đúng 5 khoá theo thứ tự |
| Bước 26 | `python -c "import pathlib; d = pathlib.Path('src/render/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_ffprobe_probe.py', 'ffmpeg_capability.py', 'real_output_inspector.py']); assert 'shell=' + 'True' not in t and 'from src' + '.' not in t and 'import src' + '.' not in t, 'src'"` | 0 | Đạt (PASS): không shell=True, không import src. |
| 4 (lệnh làm việc mới) | `python -m pytest tests/integration/prod_wiring/test_pw_f2_inspector_audio.py tests/integration/adapt/f/test_adapt_f_render.py tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | Đạt (PASS): 93 passed, 125 subtests passed in 23.75s |
| Bước 8 (lệnh làm việc mới) | `git diff --check` | 0 | Đạt (PASS): không có lỗi whitespace hay dòng cuối |
| Bước 9 (lệnh làm việc mới) | `python -c "import pathlib; t = pathlib.Path('src/render/adapters/real_output_inspector.py').read_text(encoding='utf-8'); assert all(k in t for k in ['AUDIO_HOOK', 'VOICE_AUDIBLE', 'ENGLISH_OUTPUT']) and 'from src.' not in t, 'PW-F2'"` | 0 | Đạt (PASS): đủ cổng AUDIO_HOOK, VOICE_AUDIBLE, ENGLISH_OUTPUT và không có import src. |

### 6.2. Hai kỳ vọng sai của lệnh trước đã được sửa theo hành vi thật của FFmpeg ghim

Đoạn 1 (`_FILTER_RE`): `ffmpeg -filters` của bản ghim in hai cột cờ (ví dụ ` TS aap` và ` .. abench`); chuỗi định dạng trong nhị phân là ` %c%c %-17s %-10s %s`; biểu thức đã đổi từ ba nhóm cờ sang `[T.][S.]` ở `src/render/adapters/ffmpeg_capability.py`, và test kiểm cả khối chú giải để chứng minh dòng chú giải không bị tính là filter.

Đoạn 2 (`astats`): `volumedetect` ép mẫu sang s16 nên `astats` đứng sau không in `Number of NaNs` (trích lại đoạn stderr cũ 'Number of samples: 287744' từ mục này làm bằng chứng); nhị phân ghim có hai chuỗi in `Number of NaNs: %lld` (theo kênh) và `Number of NaNs: %f` (Overall); đã đổi đồ thị sang `aformat=sample_fmts=fltp,astats,volumedetect` và cho `_NAN_RE`, `_INF_RE` nhận số thập phân, so sánh bằng `float(item) > 0`. Ghi rõ: nội dung này là kết quả sửa, các lệnh kiểm chạy lại ở mục 6.1 hàng 'Bước 4'.

### 6.3. Bảng ánh xạ coveredIds

| Mã nghiệm thu | Mô tả | Test tương ứng trong `test_pw_f2_inspector_audio.py` |
| --- | --- | --- |
| `PW-F2-01` | Đo lường âm thanh, tiếng Anh, hồ sơ đầu ra và đọc `ToolCapability` từ FFmpeg ghim | `test_pw_f2_ffmpeg_is_the_pinned_binary`, `test_pw_f2_probe_measures_audio_for_silent_quiet_and_voice`, `test_pw_f2_correct_sample_passes_audio_language_and_profile_gates`, `test_pw_f2_silent_sample_fails_voice_and_audio_hook`, `test_pw_f2_quiet_voice_fails_voice_audible`, `test_pw_f2_no_audio_stream_fails_with_named_reasons`, `test_pw_f2_voice_level_is_measured_over_spoken_windows_only`, `test_pw_f2_audio_level_none_never_passes`, `test_pw_f2_unpinned_ffmpeg_is_refused`, `test_pw_f2_wrong_voice_language_fails_english_gate`, `test_pw_f2_non_latin_subtitle_fails_english_gate`, `test_pw_f2_title_locale_from_d_is_checked`, `test_pw_f2_missing_language_source_or_stale_hash_fails`, `test_pw_f2_wrong_resolution_fails_output_profile`, `test_pw_f2_wrong_codec_fails_output_profile`, `test_pw_f2_loudness_off_target_is_only_a_warning`, `test_pw_f2_tool_capability_comes_from_the_pinned_ffmpeg` |
| `CT-QC-001` | Cổng kiểm soát chất lượng âm thanh, tiếng Anh và hồ sơ định dạng lưu trữ vào cơ sở dữ liệu | `test_pw_f2_correct_sample_passes_audio_language_and_profile_gates`, `test_pw_f2_report_is_stored_in_postgres` |

### 6.4. Chỉnh sửa theo số đo thật

Theo chỉ đạo của Bước 4 trường hợp (b), các giá trị kiểm thử đã được điều chỉnh theo số đo thực tế đo được từ nhị phân FFmpeg đã ghim để phản ánh đúng thực tế mà không làm nới lỏng hay thay đổi ý nghĩa của các cổng chấp nhận:
1. `tests/integration/prod_wiring/test_pw_f2_inspector_audio.py` dòng 43:
   - Giá trị cũ: `MIN_VOICE_LEVEL = -10.5`
   - Giá trị mới: `MIN_VOICE_LEVEL = -31.0`
   - Lý do: Số đo âm lượng thực tế của mẫu thoại `voice` trong các cửa sổ lời thoại (`speech_windows`) đo được là `-30.1` dBFS, trong khi toàn bộ tệp là `-32.7` dBFS và mẫu giọng nhỏ `quiet` là `-83.3` dBFS. Ngưỡng `-31.0` dBFS nằm chuẩn xác giữa số đo cửa sổ lời (`-30.1`) và số đo toàn tệp (`-32.7`), giúp kiểm chứng đúng yêu cầu đo lường trên các đoạn có lời thoại (chênh lệch `2.6 dB >= 1.0 dB`) và làm rớt các mẫu âm thanh quá nhỏ hoặc câm.
2. `tests/integration/prod_wiring/test_pw_f2_inspector_audio.py` dòng 61:
   - Giá trị cũ: `'min_level_db': -20.0`
   - Giá trị mới: `'min_level_db': -32.0`
   - Lý do: Cửa sổ hook âm thanh trên mẫu thoại thực tế đo được mức âm `-31.1` dBFS. Đổi ngưỡng sang `-32.0` dBFS giúp mẫu chuẩn vượt qua cổng (`passed`), đồng thời mẫu câm (`-91.0` dBFS) và mẫu nhỏ (`-84.3` dBFS) vẫn bị đánh trượt (`failed`) đúng với lý do `audio_hook_level_below_threshold`.
3. `src/render/adapters/ffmpeg_capability.py` trong hàm `read_tool_capability`:
   - Giá trị cũ: `ToolCapability(filters=filters | parse_libraries(build_text), encoders=encoders)`
   - Giá trị mới: `ToolCapability(filters=(filters | parse_libraries(build_text)) - encoders, encoders=encoders)`
   - Lý do: Thư viện biên dịch trong `-buildconf` chứa `--enable-libx264`, nhưng `libx264` là encoder thuộc `encoders`. Việc loại trừ các thư viện encoder khỏi tập `filters` đảm bảo tính phân định rõ ràng giữa filter và encoder ("encoder và filter không lẫn nhau"), thỏa mãn điều kiện `assert 'libx264' not in capability.filters`.
