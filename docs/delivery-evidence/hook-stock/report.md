# Báo cáo nghiệm thu HOOK-STOCK: client tìm và tải Pixabay (video hook) và Freesound (SFX, nhạc nền)

## Kết luận

Gói HOOK-STOCK thêm client tìm kiếm và tải thuần stdlib cho hai kho Pixabay và Freesound, transport HTTPS tiêm vào, không mạng, không log.
Nhóm lỗi OI-CP7-11-Q4 (sản phẩm chưa có client nào cho Pixabay và Freesound) được xử lý bằng gói này, ghi đúng mã OI-CP7-11-Q4.

## Tệp đã sửa

1. `src/controlplane/infrastructure/production_ports/stock_media.py`: chép nguyên văn từ bản tham chiếu Control D:/AIAVC_IMGPROTO/ref/hook-stock/, sha256 f4dcb4eb6a749bf46a5977fc84de0352b114f70ed1790871c5b890491be64dea.
2. `tests/integration/prod_ports/test_hook_stock_search.py`: chép nguyên văn từ bản tham chiếu Control D:/AIAVC_IMGPROTO/ref/hook-stock/, sha256 f5e853cb53e2191c010f55efd4e9b81c7b3a6eff78ff2baa0e41fcefc6b2c498.
3. `docs/delivery-evidence/hook-stock/report.md`: báo cáo nghiệm thu.

## Lệnh đã chạy

1. Bước 2 (RED trước khi có module):
   - Lệnh: `python -m pytest tests/integration/prod_ports/test_hook_stock_search.py -q -p no:cacheprovider`
   - Mã thoát: 2
   - Dòng tổng kết nguyên văn pytest: 1 error in 0.24s
   - Kết quả: số ca hỏng trước là 1 lỗi thu thập (ModuleNotFoundError: No module named `controlplane.infrastructure.production_ports.stock_media`), 0 đạt.

2. Bước 4 (GREEN sau khi có module):
   - Lệnh: `python -m pytest tests/integration/prod_ports/test_hook_stock_search.py -q -p no:cacheprovider`
   - Mã thoát: 0
   - Dòng tổng kết nguyên văn pytest: 10 passed in 0.04s
   - Kết quả: số ca đạt sau là 10 passed (8 hàm test, một hàm tham số hoá).

3. Bước 5 (Kiểm tra sha256 bản tham chiếu):
   - Lệnh: `python -c "import hashlib, pathlib; want = {'src/controlplane/infrastructure/production_ports/stock_media.py': 'f4dcb4eb6a749bf46a5977fc84de0352b114f70ed1790871c5b890491be64dea', 'tests/integration/prod_ports/test_hook_stock_search.py': 'f5e853cb53e2191c010f55efd4e9b81c7b3a6eff78ff2baa0e41fcefc6b2c498'}; norm = lambda p: pathlib.Path(p).read_bytes().replace(bytes([13, 10]), bytes([10])); bad = sorted(p for p, h in want.items() if hashlib.sha256(norm(p)).hexdigest() != h); assert not bad, ('khác bản tham chiếu D:/AIAVC_IMGPROTO/ref/hook-stock (so sau khi đổi CRLF thành LF)', bad)"`
   - Mã thoát: 0

4. Bước 6 (Probe cấu trúc module):
   - Lệnh: `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/stock_media.py').read_text(encoding='utf-8'); assert 'class PixabayVideoSearch' in t and 'class FreesoundSearch' in t and 'def download_stock_file(' in t and 'def license_cleared(' in t and 'https://pixabay.com/api/videos/' in t and 'https://freesound.org/apiv2/search/text/' in t and 'cdn.pixabay.com' in t and 'cdn.freesound.org' in t and 'Pixabay Content License' in t and 'CC-BY-4.0' in t, 'clients'; assert 'import socket' not in t and 'urllib.request' not in t and 'http.client' not in t and 'print(' not in t and 'logging' not in t, 'no network or log'"`
   - Mã thoát: 0

5. Bước 7 (Probe test):
   - Lệnh: `python -c "import pathlib; t = pathlib.Path('tests/integration/prod_ports/test_hook_stock_search.py').read_text(encoding='utf-8'); assert 'coveredIds: FR-HOOK-004, FR-AUD-007' in t and all(('def ' + n + '(') in t for n in ('test_pixabay_search_sends_key_and_safesearch_and_keeps_clips_in_the_window', 'test_freesound_sfx_keeps_only_cc0_and_cc_by_with_author', 'test_errors_carry_a_code_and_never_the_key', 'test_download_takes_only_the_cdn_url_and_pins_sha256')), 'tests'"`
   - Mã thoát: 0

6. Bước 8 (Probe CRLF):
   - Lệnh: `python -c "import pathlib; bad = [p for p in ('src/controlplane/infrastructure/production_ports/stock_media.py', 'tests/integration/prod_ports/test_hook_stock_search.py',) if bytes([13]) in pathlib.Path(p).read_bytes()]; assert not bad, ('CRLF', bad)"`
   - Mã thoát: 0

7. Bước 9 (Probe bố cục CP2A-LAYOUT):
   - Lệnh: `python -c "import pathlib, re, tomllib; root = pathlib.Path('src/controlplane'); keys = set(tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['tool']['setuptools']['package-dir']); pk = set('.'.join(('controlplane',) + q.parent.relative_to(root).parts) for q in root.rglob('*.py') if q.stem.strip('_') == 'init' and 'node_modules' not in q.parts); miss = sorted(pk - keys); assert not miss, miss; ini = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['tool']['pytest']['ini_options']; assert 'src' in ini.get('pythonpath', []), 'pytest pythonpath must include src'; bad = [str(q) for d in ['src', 'tests'] for q in pathlib.Path(d).rglob('*.py') if 'node_modules' not in q.parts and re.search(r'(?m)^\s*(from|import)\s+src\.', q.read_text(encoding='utf-8', errors='replace'))]; assert not bad, bad"`
   - Mã thoát: 0

8. Bước 10 (Kiểm tra khoảng trắng thừa):
   - Lệnh: `git diff --check`
   - Mã thoát: 0

## Luật giấy phép và nguồn tải đã kiểm bằng transport giả

Các kiểm thử dùng transport giả (không gọi mạng thật):
- `test_pixabay_search_sends_key_and_safesearch_and_keeps_clips_in_the_window`: tham số key, safesearch và cửa sổ thời lượng của Pixabay.
- `test_freesound_sfx_keeps_only_cc0_and_cc_by_with_author` và `test_license_rule_needs_attribution_for_cc_by_only`: chỉ CC0 và CC BY có tác giả của Freesound đi qua, NC/ND/Sampling+ bị bỏ.
- `test_freesound_music_uses_the_long_duration_window`: cửa sổ nhạc.
- `test_errors_carry_a_code_and_never_the_key`: lỗi mang mã cố định và không chứa khoá.
- `test_transport_failure_hides_the_request_url`: lỗi transport không lộ URL.
- `test_missing_key_stops_before_any_request`: thiếu khoá không gửi request.
- `test_download_takes_only_the_cdn_url_and_pins_sha256`: tải chỉ nhận URL https đúng host CDN (cdn.pixabay.com, cdn.freesound.org) và ghim sha256.

## Giới hạn

- Chỉ tìm và tải; nhập kho hook, cắt clip, catalog nhạc thuộc HOOK-HARVEST.
- Freesound tải bản xem trước HQ mp3, bản gốc cần OAuth2 chưa làm.
- Pixabay cấm hotlink nên phải tải về rồi dùng.
- Pexels gắn sau khi user yêu cầu.
