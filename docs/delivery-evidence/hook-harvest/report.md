# Báo cáo nghiệm thu HOOK-HARVEST: lệnh thu video hook, âm hook và catalog nhạc nền

## Kết luận

Gói HOOK-HARVEST thêm module và lệnh thu video hook (Pixabay) và âm hook (Freesound SFX) vào kho hook của C, cùng catalog nhạc nền (Freesound) cho AudioBedSource, có trần request, lượt tải, byte, đảm bảo tính idempotent, ghi nhận đầy đủ giấy phép và tác giả.
Nhóm lỗi OI-CP7-11-Q4 (lô CP7-11 thiếu hook thật và nhạc sau khi PW-D3-FIX4 bỏ hook giữ chỗ)
OI-CP7-11-Q4: gói này thêm lệnh thu để Control chạy một lần; chỉ đóng sau khi Control chạy --probe, hooks, music thật.

## Tệp đã sửa

1. `src/controlplane/infrastructure/production_ports/stock_harvest.py`: chép nguyên văn từ bản tham chiếu Control D:/AIAVC_IMGPROTO/ref/hook-harvest/, sha256 6385192457666be4e7d50504416e4b9d2b8ce17f3abb5f6d8cd1f2066b67c928.
2. `tools/launcher/prod/harvest_media.py`: chép nguyên văn từ bản tham chiếu Control D:/AIAVC_IMGPROTO/ref/hook-harvest/, sha256 afdfc1112c2677d375e8f5790ae21f0605e4dd424360d7e0020756cceaf46239.
3. `tests/integration/prod_ports/test_hook_harvest.py`: chép nguyên văn từ bản tham chiếu Control D:/AIAVC_IMGPROTO/ref/hook-harvest/, sha256 a1366915bace1fccee5ead7e1023dece889623e004060049cb420d1f56dcd8bf.
4. `tests/integration/prod_wiring/test_hook_harvest_import.py`: chép nguyên văn từ bản tham chiếu Control D:/AIAVC_IMGPROTO/ref/hook-harvest/, sha256 4555ec43ccc57eb4f33babcddaeeecdfe55e2e7a24eb4cb056100eb4d65c577b.
5. `docs/delivery-evidence/hook-harvest/report.md`: báo cáo nghiệm thu.

## Lệnh đã chạy

1. Bước 3 (RED trước khi có module):
   - Lệnh: `python -m pytest tests/integration/prod_ports/test_hook_harvest.py -q -p no:cacheprovider`
   - Mã thoát: 2
   - Dòng tổng kết nguyên văn pytest: `1 error in 0.23s`
   - Kết quả: 1 lỗi thu thập (ModuleNotFoundError: No module named 'controlplane.infrastructure.production_ports.stock_harvest'), 0 đạt.

2. Bước 6 (GREEN nhóm không cần Postgres):
   - Lệnh: `python -m pytest tests/integration/prod_ports/test_hook_harvest.py tests/m2/test_p0_architecture_rules.py -q -p no:cacheprovider`
   - Mã thoát: 0
   - Dòng tổng kết nguyên văn pytest: `16 passed in 1.50s`
   - Kết quả: 16 passed (10 passed từ test_hook_harvest.py, 6 passed từ tests/m2/test_p0_architecture_rules.py).

3. Bước 7 (Test PostgreSQL của gói):
   - Lệnh: `python -m pytest tests/integration/prod_wiring/test_hook_harvest_import.py -q -p no:cacheprovider`
   - Mã thoát: 0
   - Dòng tổng kết nguyên văn pytest: `1 passed in 0.80s`
   - Kết quả: 1 passed (test_harvested_hooks_become_production_candidates_with_verified_versions).

4. Bước 8 (Kiểm tra sha256 bản tham chiếu):
   - Lệnh: `python -c "import hashlib, pathlib; want = {'src/controlplane/infrastructure/production_ports/stock_harvest.py': '6385192457666be4e7d50504416e4b9d2b8ce17f3abb5f6d8cd1f2066b67c928', 'tools/launcher/prod/harvest_media.py': 'afdfc1112c2677d375e8f5790ae21f0605e4dd424360d7e0020756cceaf46239', 'tests/integration/prod_ports/test_hook_harvest.py': 'a1366915bace1fccee5ead7e1023dece889623e004060049cb420d1f56dcd8bf', 'tests/integration/prod_wiring/test_hook_harvest_import.py': '4555ec43ccc57eb4f33babcddaeeecdfe55e2e7a24eb4cb056100eb4d65c577b'}; norm = lambda p: pathlib.Path(p).read_bytes().replace(bytes([13, 10]), bytes([10])); bad = sorted(p for p, h in want.items() if hashlib.sha256(norm(p)).hexdigest() != h); assert not bad, ('khác bản tham chiếu D:/AIAVC_IMGPROTO/ref/hook-harvest (so sau khi đổi CRLF thành LF)', bad)"`
   - Mã thoát: 0

5. Bước 9 (Probe cấu trúc module stock_harvest.py):
   - Lệnh: `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/stock_harvest.py').read_text(encoding='utf-8'); assert all(w in t for w in ('def harvest_hooks(', 'def harvest_music(', 'def probe_providers(', 'def build_hook(', 'class MeteredTransport', 'class HarvestBudget', 'class PostgresHookLibrary', 'class FfmpegHookMedia', 'MAX_REQUESTS_PER_RUN = 200', 'MAX_DOWNLOADS_PER_RUN = 120', 'MAX_BYTES_PER_RUN = 2 * 1024 * 1024 * 1024', 'REQUEST_INTERVAL_SECONDS = 1.2', 'VISUAL_HOOK_MS = 4000', 'download_stock_file', 'license_cleared', 'save_music_catalog', 'register_staged_artifact', 'import_hook(', 'hook_license', 'hook_attribution', 'hook_source_sha256')), 'harvest'; assert 'recipe_template' not in t and 'siren' not in t.lower() and 'print(' not in t.replace('Fingerprint(', ''), 'no placeholder, no siren, no output'"`
   - Mã thoát: 0

6. Bước 10 (Probe lệnh harvest_media.py):
   - Lệnh: `python -c "import pathlib; s = pathlib.Path('tools/launcher/prod/harvest_media.py').read_text(encoding='utf-8'); assert all(w in s for w in ('--probe', '--status', '--dry-run', '--per-query', '--per-mood', 'StockKeyCredentials', 'ProductionHttpsTransport', 'MeteredTransport', 'EXIT_USAGE = 2', 'resolve_layout', 'def main(')), 'cli'; assert 'argparse' not in s, 'no argparse'"`
   - Mã thoát: 0

7. Bước 11 (Probe hai tệp test):
   - Lệnh: `python -c "import pathlib; t = pathlib.Path('tests/integration/prod_ports/test_hook_harvest.py').read_text(encoding='utf-8'); assert 'coveredIds: FR-HOOK-004, FR-HOOK-005, FR-AUD-007' in t and all(('def ' + n + '(') in t for n in ('test_visual_and_audio_items_are_cut_and_imported_with_license_and_index', 'test_running_again_imports_nothing_twice_and_downloads_nothing', 'test_refused_license_and_foreign_host_are_skipped_before_download', 'test_budget_caps_requests_downloads_and_bytes_and_spaces_requests', 'test_rate_limit_stops_only_that_library', 'test_music_catalog_gets_new_tracks_with_measured_sha_and_moods', 'test_cli_probe_and_dry_run_never_print_the_key_and_refuse_odd_arguments', 'test_pinned_ffmpeg_cuts_a_four_second_clip_and_a_short_loud_wav')), 'tests'; p = pathlib.Path('tests/integration/prod_wiring/test_hook_harvest_import.py').read_text(encoding='utf-8'); assert 'def test_harvested_hooks_become_production_candidates_with_verified_versions(' in p and 'exclude_placeholders=True' in p, 'pg'"`
   - Mã thoát: 0

8. Bước 12 (Probe CRLF):
   - Lệnh: `python -c "import pathlib; bad = [p for p in ('src/controlplane/infrastructure/production_ports/stock_harvest.py', 'tools/launcher/prod/harvest_media.py', 'tests/integration/prod_ports/test_hook_harvest.py', 'tests/integration/prod_wiring/test_hook_harvest_import.py',) if bytes([13]) in pathlib.Path(p).read_bytes()]; assert not bad, ('CRLF', bad)"`
   - Mã thoát: 0

9. Bước 13 (Probe bố cục CP2A-LAYOUT):
   - Lệnh: `python -c "import pathlib, re, tomllib; root = pathlib.Path('src/controlplane'); keys = set(tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['tool']['setuptools']['package-dir']); pk = set('.'.join(('controlplane',) + q.parent.relative_to(root).parts) for q in root.rglob('*.py') if q.stem.strip('_') == 'init' and 'node_modules' not in q.parts); miss = sorted(pk - keys); assert not miss, miss; ini = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['tool']['pytest']['ini_options']; assert 'src' in ini.get('pythonpath', []), 'pytest pythonpath must include src'; bad = [str(q) for d in ['src', 'tests'] for q in pathlib.Path(d).rglob('*.py') if 'node_modules' not in q.parts and re.search(r'(?m)^\s*(from|import)\s+src\.', q.read_text(encoding='utf-8', errors='replace'))]; assert not bad, bad"`
   - Mã thoát: 0

10. Bước 16 (Kiểm tra khoảng trắng thừa):
    - Lệnh: `git diff --check`
    - Mã thoát: 0

## Trần lượt gọi, lượt tải và dung lượng

Hệ thống thiết lập các hằng số kiểm soát tài nguyên chặt chẽ:
- MAX_REQUESTS_PER_RUN = 200: Giới hạn tối đa 200 lượt gọi API trong một lần chạy.
- MAX_DOWNLOADS_PER_RUN = 120: Giới hạn tối đa 120 tệp được tải trong một lần chạy.
- MAX_BYTES_PER_RUN = 2 GiB: Giới hạn tối đa 2 GiB (2 * 1024 * 1024 * 1024 bytes) dung lượng tải về trong một lần chạy.
- REQUEST_INTERVAL_SECONDS = 1.2: Giãn cách tối thiểu 1.2 giây giữa hai yêu cầu liên tiếp.

Các giới hạn trên đã được kiểm thử bằng transport giả qua các bài kiểm thử:
- `test_budget_caps_requests_downloads_and_bytes_and_spaces_requests`: Kiểm tra cơ chế đếm và từ chối request/download/byte khi vượt trần, đảm bảo giãn cách thời gian giữa các request.
- `test_rate_limit_stops_only_that_library`: Kiểm tra khi một thư viện gặp lỗi 401, 403, 429 hoặc thiếu khoá, chỉ thư viện đó bị dừng mà không ảnh hưởng tới các thư viện khác.
- `test_refused_license_and_foreign_host_are_skipped_before_download`: Kiểm tra việc loại bỏ các mục có giấy phép không hợp lệ hoặc URL không thuộc host CDN trước khi tải về.
Toàn bộ quá trình kiểm thử không gọi mạng thật.

## Lệnh --probe

Lệnh probe kiểm tra kết nối tới các nhà cung cấp:
`python tools/launcher/prod/harvest_media.py --probe`
Lệnh này thực hiện đúng một request per_page 3 tới mỗi kho mà không tải tệp nào, do Control chạy sau khi user nhập khoá bằng set_stock_key.py.
Worker KHÔNG chạy lệnh này (không có khoá, không gọi mạng thật). Thứ tự thực thi chuẩn của Control:
1. `--probe`
2. `hooks`
3. `music`

## Ghi công tác giả CC-BY

Quy tắc xử lý giấy phép Creative Commons và ghi công tác giả:
- Giấy phép Freesound CC BY chỉ nhận khi có tác giả (license_cleared).
- Hook ghi nhận đầy đủ: `hook_license`, `hook_author` (bỏ khi rỗng), `hook_attribution`, `hook_page_url`.
- Catalog nhạc bỏ mục thiếu tác giả khi thu thập.

## Giới hạn

- Clip của bài (FR-COL-005) là HOOK-ARTICLE-CLIP; che mờ clip là gói sau.
- Freesound chỉ cho tải bản xem trước HQ mp3 (bản gốc cần OAuth2).
- Lệnh không tự chạy trong start: Control chạy --probe rồi hooks rồi music sau khi user nhập khoá.
- Lệnh kiểm không gọi lại test của bốn gói phụ thuộc vì các tệp đó chưa có ở HEAD lúc thêm gói; test của gói import thẳng mã của chúng.
