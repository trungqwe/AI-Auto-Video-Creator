# Báo cáo Nghiệm thu PW-F1: RealOutputInspector đo cổng hình ảnh và disclosure suy luận với FFmpeg ghim (CT-QC-001, PW-F1-01)

## 1. Mục tiêu và phạm vi PW-F1
- Mục tiêu: Hiện thực `RealOutputInspector` và `FrameProbe` tuân thủ cổng `OutputInspectorPort` bằng nhị phân FFmpeg đã ghim (sha256 `f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480`); đo lường thật các cổng `VISUAL_HOOK`, `THUMBNAIL`, `SUBTITLE_BURNED_IN`, `KARAOKE_TIMING` và cổng cứng có điều kiện `INFERENCE_DISCLOSURE_PRESENT` (CT-QC-001). Mọi ngưỡng đo nằm trong `InspectorSettings`, không có hằng số ngưỡng trong mã; thiếu đầu vào thì trả trường evidence là `None`, không cổng nào mặc định PASS khi thiếu phép đo.
- Phạm vi sở hữu (owned paths) của gói PW-F1:
  + `src/render/adapters/real_output_inspector.py`
  + `src/render/adapters/frame_probe.py`
  + `tests/integration/prod_wiring/test_pw_f1_inspector_visual.py`
  + `tests/unit/render/test_f01_package_layout.py`
  + `docs/delivery-evidence/pw-f1/report.md`

## 2. Tệp đã đổi
- `src/render/adapters/frame_probe.py`: Tạo mới, lớp `FrameProbe` cung cấp `duration_ms` (trích thời lượng video) và `band_difference` (đo chênh lệch pixel dải giữa khung hình mẫu và khung mốc bằng bộ lọc `blend=all_mode=difference`, `signalstats`, `metadata=mode=print:key=lavfi.signalstats.YAVG` kết hợp `setpts=PTS-STARTPTS` chuẩn hóa mốc thời gian); lớp chỉ đọc, không ghi tệp.
- `src/render/adapters/real_output_inspector.py`: Tạo mới, lớp `RealOutputInspector` cài `OutputInspectorPort` cùng cấu hình `InspectorSettings` không có giá trị mặc định; kiểm tra pin sha256 FFmpeg trước mọi lần chạy và từ chối nhị phân không ghim bằng `FfmpegPinRejected`; đo `VISUAL_HOOK` và `THUMBNAIL` bằng bộ lọc `ssim`; thumbnail hỏng trả `None`, lệch ngưỡng trả `unmatched:`; đo `SUBTITLE_BURNED_IN` và disclosure suy luận (`INFERENCE_DISCLOSURE_PRESENT`) bằng chênh lệch dải điểm ảnh so với khung mốc ngoài cửa sổ phụ đề/disclosure; trích xuất `KARAOKE_TIMING` từ các thẻ `\k` trong tệp ASS.
- `tests/unit/render/test_f01_package_layout.py`: Mở rộng bảng miễn trừ `ADAPTER_EXEMPTIONS` và bản chép trong `test_exemption_table_is_exact_paths_only` thêm đúng hai khoá đường dẫn chính xác cho hai adapter mới; thêm test `test_inspector_adapters_accept_only_subprocess`.
- `tests/integration/prod_wiring/test_pw_f1_inspector_visual.py`: Tạo mới bộ kiểm thử tích hợp 12 test đo thật trên video lavfi sinh bằng FFmpeg đã ghim trong `tmp_path`, không mock, không phụ thuộc database; kiểm chứng mẫu chuẩn PASS toàn bộ cổng, và các mẫu lỗi FAIL đúng cổng với đúng lý do.
- `docs/delivery-evidence/pw-f1/report.md`: Tạo mới, báo cáo nghiệm thu chi tiết kèm bảng bằng chứng lệnh thực thi.

## 3. Dòng đã đổi ở test_f01_package_layout.py và lý do
- Thêm chú thích phía trên `ADAPTER_EXEMPTIONS`:
  `# PW-F1 (docs/implementation/prod-wiring/slices.md, mục PW-F1): hai tệp đo khung hình chạy tiến trình con FFmpeg đã ghim; chỉ import:subprocess, đường dẫn chính xác.`
- Trong `ADAPTER_EXEMPTIONS = {`: thêm 2 dòng cho 2 tệp mới:
  + `    'adapters/real_output_inspector.py': frozenset({'import:subprocess'}),`
  + `    'adapters/frame_probe.py': frozenset({'import:subprocess'}),`
- Trong `test_exemption_table_is_exact_paths_only`: thêm 2 dòng tương tự vào bản sao dict mong đợi:
  + `                'adapters/real_output_inspector.py': frozenset({'import:subprocess'}),`
  + `                'adapters/frame_probe.py': frozenset({'import:subprocess'}),`
- Trong lớp `AdapterExemptionTests`: thêm phương thức kiểm thử `test_inspector_adapters_accept_only_subprocess` xác nhận hai tệp mới chỉ được miễn `import:subprocess`, các hành vi cấm khác (`import:os`, `call:unlink`) vẫn bị bắt lỗi nghiêm ngặt.
- Lý do: Hai tệp mới là adapter thực thi đo đạc khung hình video thông qua tiến trình con FFmpeg đã ghim, chỉ import `subprocess` trong nhóm bị cấm và không gọi `unlink`/`remove`/`rename`/`truncate`. Bảng miễn trừ giữ nguyên tính chính xác tuyệt đối theo đường dẫn, không miễn cả thư mục, không thay đổi `FORBIDDEN_IMPORT_PREFIXES`, `FORBIDDEN_CALL_ATTRS` hay hai khoá cũ.

## 4. Quyết định mặc định D8
- Khung mốc (baseline frame) lấy ở điểm giữa khoảng trống dài nhất ngoài mọi cửa sổ phụ đề (hoặc ngoài cửa sổ Disclosure đối với cổng disclosure suy luận); nếu khoảng trống dài nhất có độ dài nhỏ hơn `baseline_min_gap_ms` thì trả `None` và cổng tương ứng thất bại (FAIL) do thiếu điều kiện đo an toàn.
- Mọi ngưỡng đo (kích thước khung so sánh, ngưỡng tương đồng SSIM, vị trí dải, chênh lệch tối thiểu, khoảng cách mốc, giới hạn mẫu) nằm hoàn toàn trong dataclass `InspectorSettings` được truyền vào, tuyệt đối không chứa hằng số ngưỡng trong mã sản xuất; các ngưỡng quyết định cổng đạt/không đạt thuộc về `QualityPolicy`.

## 5. GIẢ ĐỊNH và mục mở
- `OI-PW-F1-01`: Video có phụ đề liên tục không có khoảng trống đạt `baseline_min_gap_ms` để lấy khung mốc thì `SUBTITLE_BURNED_IN` trả `None` và cổng đánh giá `FAILED` với lý do `subtitle_not_observed` (đây là hạn chế kỹ thuật đã biết, PW-F3/PW-F4 sẽ quyết định mốc chèn phụ đề khi ghép nối timeline).
- `OI-PW-F1-02`: Nền video động (motion background) có thể làm tăng chênh lệch dải điểm ảnh tự nhiên; vị trí dải disclosure thật do PW-F3 sinh và wiring phải cung cấp `disclosure_band` khớp với cấu hình style `Disclosure`.
- `OI-PW-F1-03`: Bộ kiểm thử tích hợp của PW-F1 không sử dụng PostgreSQL vì toàn bộ tiêu chí nghiệm thu của tác vụ tập trung vào đo kiểm hình ảnh và phân tích tệp ASS cục bộ; không có yêu cầu lưu trữ cơ sở dữ liệu ở tầng này.

## 6. Bảng bằng chứng
### 6.1. Bảng lệnh kiểm tra bắt buộc và kết quả thực tế

| Bước | Lệnh kiểm tra | Exit Code | Kết quả thực tế |
| --- | --- | --- | --- |
| Bước 10 | `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | Đạt (PASS): 21 passed, 124 subtests passed in 0.42s |
| Bước 17 | `python -m pytest tests/integration/prod_wiring/test_pw_f1_inspector_visual.py tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | Đạt (PASS): 33 passed, 124 subtests passed in 3.71s |
| Bước 18 | `python -c "import pathlib; t = pathlib.Path('src/render/adapters/real_output_inspector.py').read_text(encoding='utf-8'); assert 'VISUAL_HOOK' in t and 'KARAOKE_TIMING' in t and 'DisclosureEvidence' in t and 'from src.' not in t, 'PW-F1'"` | 0 | Đạt (PASS): chứa đầy đủ ký hiệu bắt buộc, không vi phạm import |
| Bước 19 | `python -c "import ast, pathlib; d = ast.get_docstring(ast.parse(pathlib.Path('tests/integration/prod_wiring/test_pw_f1_inspector_visual.py').read_text(encoding='utf-8'))); line = [x for x in d.splitlines() if x.startswith('coveredIds:')][0]; ids = [x.strip() for x in line[len('coveredIds:'):].split(',')]; assert {'PW-F1-01', 'CT-QC-001'} <= set(ids), ids"` | 0 | Đạt (PASS): coveredIds khai báo đủ PW-F1-01 và CT-QC-001 |
| Bước 20 | `python -c "import ast, pathlib; t = ast.parse(pathlib.Path('tests/unit/render/test_f01_package_layout.py').read_text(encoding='utf-8')); n = [x for x in t.body if isinstance(x, ast.Assign) and x.targets[0].id == 'ADAPTER_EXEMPTIONS'][0]; keys = [k.value for k in n.value.keys]; assert keys == ['adapters/real_ffmpeg_renderer.py', 'adapters/real_ffprobe_probe.py', 'adapters/real_output_inspector.py', 'adapters/frame_probe.py'], keys"` | 0 | Đạt (PASS): ADAPTER_EXEMPTIONS chứa đúng 4 khoá theo thứ tự |
| Bước 22 | `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-f1/report.md').read_text(encoding='utf-8'); assert chr(65533) not in t and chr(273) in t and 'ADAPTER_EXEMPTIONS' in t and 'frame_probe.py' in t, 'report'"` | 0 | Đạt (PASS): tệp UTF-8 không lỗi font, nguyên vẹn dấu tiếng Việt |
| Bước 23 | `git diff --check` | 0 | Đạt (PASS): không có lỗi khoảng trắng thừa |

### 6.2. Chỉnh sửa phát sinh ở bước 17
- Khi đo `band_difference` giữa hai mốc thời gian bằng bộ lọc `blend=all_mode=difference`, do việc seek (`-ss`) đến mốc thời gian mili-giây lẻ (như 2250 ms) không rơi vào biên khung hình số nguyên (ở 30 fps, 2.25s rơi vào khung 67.5), luồng video thứ hai có PTS ban đầu bị lệch (pts = 256). Bộ lọc `blend` của FFmpeg căn chỉnh khung theo PTS nên đã không tìm thấy khung tương ứng ở pts = 0 của luồng thứ nhất và dẫn đến việc trừ với khung rỗng (sinh `YAVG` giả ~125 dù ảnh giống hệt nhau).
- Khắc phục đúng chỉ dẫn bước 17: thêm `setpts=PTS-STARTPTS` vào chuỗi tiền xử lý `prep` của từng đầu vào trong `FrameProbe.band_difference` để chuẩn hóa mốc thời gian frame 0 của cả hai luồng về 0. Sau khi chuẩn hóa, độ chênh lệch khi không có dải chữ đo chính xác về 0 (< 5.0), giúp test `test_pw_f1_missing_disclosure_band_fails_with_segment_id` PASS hoàn hảo mà không phải hạ ngưỡng hay sửa assert.

### 6.3. Ánh xạ coveredIds sang các test trong `test_pw_f1_inspector_visual.py`

| Covered ID | Mô tả nghiệm thu | Các test tương ứng trong test_pw_f1_inspector_visual.py |
| --- | --- | --- |
| `PW-F1-01` | `RealOutputInspector` cài `OutputInspectorPort` bằng FFmpeg ghim; đo lường thật các cổng `VISUAL_HOOK`, `THUMBNAIL`, `SUBTITLE_BURNED_IN`, `KARAOKE_TIMING`; ngưỡng đến từ settings; thiếu đầu vào FAIL có lý do | `test_pw_f1_ffmpeg_is_the_pinned_binary`, `test_pw_f1_correct_sample_passes_every_measured_gate`, `test_pw_f1_replaced_hook_fails_visual_hook_gate`, `test_pw_f1_missing_burned_in_subtitles_fails_subtitle_gate`, `test_pw_f1_corrupt_thumbnail_fails_thumbnail_gate`, `test_pw_f1_karaoke_offset_beyond_tolerance_fails_karaoke_gate`, `test_pw_f1_missing_ass_measures_nothing_and_never_passes`, `test_pw_f1_thresholds_come_from_settings_not_code`, `test_pw_f1_unpinned_ffmpeg_is_refused_before_any_run`, `test_pw_f1_frame_probe_reads_duration_and_band_difference` |
| `CT-QC-001` | Cổng cứng có điều kiện `INFERENCE_DISCLOSURE_PRESENT`: segment inference kèm dải disclosure PASS; thiếu dải trong khung hình FAIL dù ASS có dòng; không có segment inference cho NOT_APPLICABLE | `test_pw_f1_correct_sample_passes_every_measured_gate`, `test_pw_f1_missing_disclosure_band_fails_with_segment_id`, `test_pw_f1_without_inference_segments_disclosure_is_not_applicable`, `test_pw_f1_missing_ass_measures_nothing_and_never_passes` |
