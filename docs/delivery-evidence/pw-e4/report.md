# Báo cáo Nghiệm thu PW-E4: Nhạc nền tự tìm và thu thập từ nguồn ngoài (FR-AUD-007, FR-AUD-004)

## 1. Mục tiêu và phạm vi PW-E4
- Mục tiêu: Hiện thực AudioBedPort sản xuất (`audio_bed_source.py`) tìm nhạc nền theo cảm xúc (mood) và thời lượng trong kho nhạc đã thu thập, thu thập mới qua HTTPS với chính sách SSRF khớp đúng URL đã ghim trong `music_sources.json`, kiểm tra mã băm SHA-256, ghi nhận đầy đủ nguồn gốc (provenance), không sử dụng nhạc do AI sáng tác; khi không tìm thấy nhạc phù hợp hoặc nguồn gặp sự cố thì trả kết quả `none` kèm cảnh báo `AUDIO_MIX_QUALITY` để chuỗi xử lý video vẫn tiếp tục hoàn thành.
- Phạm vi: Các tệp thuộc owned paths của gói PW-E4:
  + `tools/launcher/prod/music_sources.json`
  + `src/voice/adapters/audio_bed_source.py`
  + `tests/integration/prod_wiring/test_pw_e4_audio_bed.py`
  + `tests/unit/voice/test_e01_package_layout.py`
  + `docs/delivery-evidence/pw-e4/report.md`
- Ghi chú phạm vi: Tệp `docs/implementation/prod-wiring/music-source.md` KHÔNG thuộc sở hữu (owned paths) của gói này; Worker không sửa, không tạo, không dời tệp và hoàn toàn không chạm vào tệp đó.

## 2. Tệp đã đổi
- `tools/launcher/prod/music_sources.json`: Tạo mới, chứa đúng 2 nguồn nhạc mẫu (primary: openverse, fallback: incompetech) với đầy đủ siêu dữ liệu bản quyền, tác giả, URL HTTPS, mã băm SHA-256 đã đo thật và mảng moods.
- `src/voice/adapters/audio_bed_source.py`: Tạo mới, hiện thực `AudioBedSource` tuân thủ cổng `AudioBedPort`, `load_music_sources`, `check_music_url` (chính sách SSRF), cấu trúc bản ghi xuất xứ `CollectedTrack` và `HttpsTransport` được tiêm từ wiring.
- `tests/integration/prod_wiring/test_pw_e4_audio_bed.py`: Tạo mới, bộ kiểm thử tích hợp trên PostgreSQL 18.6 thật kết hợp với transport giả lập phục vụ tệp WAV mẫu, kiểm thử toàn bộ các nhánh thu thập, tái sử dụng, từ chối SHA-256 sai, xử lý lỗi kết nối và trả kết quả `none` an toàn.
- `docs/delivery-evidence/pw-e4/report.md`: Tạo mới, báo cáo nghiệm thu chi tiết kèm bảng bằng chứng thực tế.
- `tests/unit/voice/test_e01_package_layout.py`: KHÔNG đổi dòng nào. Lý do: Chọn phương án thay thế được phép là tiêm transport HTTP từ wiring (`HttpsTransport`), nhờ đó tệp adapter production không import bất kỳ mô-đun cấm nào (`socket`, `subprocess`, `urllib.request`, `http.client`, v.v.), kết quả lệnh quét AST ở bước 8 đạt tuyệt đối và toàn bộ test của `test_e01_package_layout.py` giữ nguyên màu xanh mà không cần nới lỏng bảng miễn trừ.

## 3. Quyết định mặc định đơn giản theo D8
- Chính sách SSRF: Chặn theo cơ chế khớp đúng URL đã ghim trong danh sách cấu hình (https, không thông tin đăng nhập, cổng 443, không IP literal), transport trả final_url khác URL yêu cầu bị từ chối (không theo redirect).
- Cơ chế tìm và nạp nhạc: Tìm trong thư viện trước (mood và thời lượng >= độ dài cue, chọn track ngắn nhất đủ dài), rồi tới nguồn primary, rồi fallback.
- Ràng buộc hoàn thành: Mọi cue phải có nhạc, thiếu một cue thì cả yêu cầu trả bed `none`; cue kind sfx luôn dẫn tới `none` vì hai nguồn chỉ có nhạc.
- Biểu diễn bed loại `none`: Bed `none` là WAV im lặng đúng độ dài cue (domain E không biểu diễn được bed rỗng), loudness của nó là điểm giữa ràng buộc, ghi rõ `constraint_midpoint_not_measured`.
- Xử lý mã băm sai lệch: SHA-256 sai bị từ chối, ghi log `music_sha256_mismatch`, không ghi tệp.

## 4. GIẢ ĐỊNH
- GIẢ ĐỊNH về trường moods: Trường moods trong `tools/launcher/prod/music_sources.json` (openverse: calm, ambient; incompetech: carefree, upbeat) suy từ tiêu đề bài, chưa có metadata xác nhận.
- GIẢ ĐỊNH về URL và SHA-256: SHA-256 và URL chép nguyên văn từ `docs/implementation/prod-wiring/music-source.md` (do Control đo), Worker không đo lại vì không dùng mạng.

## 5. Mục mở
- `OI-PW-E4-01`: Đề xuất gói riêng cho phép domain `AudioBedResult` biểu diễn bed rỗng (hiện phải dùng WAV im lặng).
- `OI-PW-E4-02`: Gói wiring (PW-W) phải cấp `HttpsTransport` thật (phân giải DNS, từ chối địa chỉ private/loopback/link-local, không theo redirect), duration_probe và loudness_meter bằng FFmpeg/ffprobe cho tệp MP3 thật vì test chỉ dùng WAV.
- `OI-PW-E4-03`: Hai nguồn mẫu chỉ có hai bài nên mood không khớp sẽ ra `none` thường xuyên, mở rộng kho thuộc `OI-PW-06` chờ user.

## 6. Bảng bằng chứng
### 6.1. Bảng lệnh kiểm tra bắt buộc và kết quả thực tế

| Bước | Lệnh kiểm tra | Exit Code | Kết quả thực tế |
| --- | --- | --- | --- |
| Bước 8 | `python -c "import ast, pathlib; text = pathlib.Path('src/voice/adapters/audio_bed_source.py').read_text(encoding='utf-8'); t = ast.parse(text); names = [a.name for n in ast.walk(t) if isinstance(n, ast.Import) for a in n.names] + [n.module for n in ast.walk(t) if isinstance(n, ast.ImportFrom) and n.module]; bad = [x for x in names if x.split('.')[0] in ('socket', 'subprocess', 'src', 'psycopg', 'creative', 'render') or x in ('urllib.request', 'http.client')]; assert not bad, bad; assert 'fake' not in text.lower(), 'fake in production'"` | 0 | Đạt (PASS), không import mô-đun cấm, không chứa từ 'fake' |
| Bước 13 | `python -m pytest tests/integration/prod_wiring/test_pw_e4_audio_bed.py tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` | 0 | 39 passed, 89 subtests passed in 3.11s |
| Bước 14 | `python -c "import json, pathlib, re; j = json.loads(pathlib.Path('tools/launcher/prod/music_sources.json').read_text(encoding='utf-8')); s = j['sources']; assert len(s) == 2 and sorted(x['role'] for x in s) == ['fallback', 'primary'], 'music_sources: need exactly two sources'; assert all(re.fullmatch('https://[^ ]+', x['url']) and x['license'] and 'nc' not in x['license'].lower().replace('-', ' ').split() and x['attribution'] and x['author'] and re.fullmatch('[0-9a-f]{64}', x['sha256']) for x in s), 'music_sources: missing fields'"` | 0 | Đạt (PASS), đúng hai nguồn primary và fallback, license không NC, sha256 64 ký tự hex |
| Bước 16 | `python -c "import ast, pathlib; d = ast.get_docstring(ast.parse(pathlib.Path('tests/integration/prod_wiring/test_pw_e4_audio_bed.py').read_text(encoding='utf-8'))); line = [x for x in d.splitlines() if x.startswith('coveredIds:')][0]; ids = [x.strip() for x in line[len('coveredIds:'):].split(',')]; assert {'PW-E4-01', 'FR-AUD-007', 'FR-AUD-004'} <= set(ids), ids"` | 0 | Đạt (PASS), coveredIds khai báo đủ PW-E4-01, FR-AUD-007, FR-AUD-004 |
| Bước 17 | `python -m pytest tests/integration/prod_wiring/test_pw_e4_audio_bed.py tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` | 0 | 39 passed, 89 subtests passed in 3.11s |
| Bước 18 | `git diff --check` | 0 | Đạt (PASS), không có lỗi khoảng trắng thừa hay định dạng dòng |

### 6.2. Ánh xạ coveredIds sang các test trong `test_pw_e4_audio_bed.py`

| Covered ID | Mô tả nghiệm thu | Các test tương ứng trong test_pw_e4_audio_bed.py |
| --- | --- | --- |
| `PW-E4-01` | Cấu hình nguồn nhạc, nạp kiểm tra danh sách nguồn, tải nhạc có xác thực xuất xứ, từ chối sai lệch SHA-256, xử lý bed none an toàn khi hết nguồn và phòng chống SSRF URL | `test_pw_e4_music_sources_json_has_exactly_two_complete_sources`, `test_pw_e4_loader_rejects_incomplete_or_noncommercial_lists`, `test_pw_e4_collects_new_music_and_records_every_provenance_field`, `test_pw_e4_wrong_sha256_is_rejected_stored_nowhere_and_fallback_is_used`, `test_pw_e4_without_usable_music_the_bed_is_none_with_warning_and_the_chain_goes_on`, `test_pw_e4_url_outside_the_pinned_list_is_blocked` |
| `FR-AUD-007` | Hệ thống tự tìm và thu thập nhạc nền ngoài qua HTTPS, ghi nhận xuất xứ đầy đủ, không AI sáng tác, dự phòng an toàn | `test_pw_e4_music_sources_json_has_exactly_two_complete_sources`, `test_pw_e4_loader_rejects_incomplete_or_noncommercial_lists`, `test_pw_e4_collects_new_music_and_records_every_provenance_field`, `test_pw_e4_wrong_sha256_is_rejected_stored_nowhere_and_fallback_is_used`, `test_pw_e4_without_usable_music_the_bed_is_none_with_warning_and_the_chain_goes_on`, `test_pw_e4_url_outside_the_pinned_list_is_blocked` |
| `FR-AUD-004` | Chọn nhạc nền theo cảm xúc (mood) và thời lượng, ưu tiên tái sử dụng từ thư viện đã thu thập | `test_pw_e4_search_reuses_collected_music_by_mood_and_duration` |
