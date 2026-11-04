# Báo cáo MCDOC-ROADMAP-M8

## Thông tin gói công việc
- **Mã gói:** MCDOC-ROADMAP-M8
- **Nhóm lỗi / Mục mở:** OI-MC-ROADMAP-M8
- **Mục đích:** Đưa mốc M8 (MC) vào `docs/11-roadmap.md`, kế hoạch MC bản 5 (31 slice) vào `docs/implementation/mc/plan.md` và 8 tệp dữ liệu nghiên cứu vào `docs/implementation/mc/data/`; chỉ tài liệu và dữ liệu, không sửa mã nguồn, kiểm thử hay cấu hình.

## Bảng 10 tệp đã chép nguyên văn từ bản tham chiếu D:/AIAVC_IMGPROTO/ref/mcdoc-roadmap-m8/

| STT | Đường dẫn tệp | Trạng thái | SHA-256 |
| --- | --- | --- | --- |
| 1 | `docs/11-roadmap.md` | thay cả tệp | `a5e9288a1acfbdea2966b2c1a7f76554efe3c48c70a1b4b4df2ee5a591d33a89` |
| 2 | `docs/implementation/mc/plan.md` | tệp mới | `2efde57f0a76e26eab0c8c272230c7eb6753c6e09ef7719f68ada46afd7f63b9` |
| 3 | `docs/implementation/mc/data/sources_seed_mc.json` | tệp mới | `006e34fee45b100be4dfe5d988f274ff5e22be8c9e7078ee0c3966255b617240` |
| 4 | `docs/implementation/mc/data/sources_extra.json` | tệp mới | `86c8fdb84694cea9c547446bae651de3bf432dede16e38519c9674ee1beb6538` |
| 5 | `docs/implementation/mc/data/hook_sources.json` | tệp mới | `a908875af31e708e70cfff96dc1abb7522bcad2080cf188bd1e25488f903f2cc` |
| 6 | `docs/implementation/mc/data/sfx_sources.json` | tệp mới | `8937646117ca58e6ced7092604501a1369ce1b9e93029559109317e8683649dc` |
| 7 | `docs/implementation/mc/data/narrative_formulas.md` | tệp mới | `76dd7e9baebe3ca094fc39a7b18770e02d0db33a0e2ec38e92e6cacaf14cb46d` |
| 8 | `docs/implementation/mc/data/voice_profile.json` | tệp mới | `d84713a0bb32f96456a415fef112234bd0a410ecea0934d076fb5e7d117db1fb` |
| 9 | `docs/implementation/mc/data/labeled_20.json` | tệp mới | `ad7e9280abef7cf54ad98a17c95974332b6dc5bf1b7ea009670bcea936da348a` |
| 10 | `docs/implementation/mc/data/heatcut.py` | tệp mới | `48261d7aad1fd9de8f60dcc86874a2817070dbbfb3e3dee32474a5c255c3e779` |

## Lệnh đã chạy

### Bước 11: Kiểm tra khoảng trắng thừa / CRLF
- **Lệnh:** `git diff --check`
- **Mã thoát:** 0
- **Kết quả:** Mã thoát 0, không có cảnh báo whitespace.

### Bước 12: Pytest kiểm tài liệu catalog coverage
- **Lệnh:** `python -m pytest tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cacheprovider`
- **Mã thoát:** 0
- **Dòng tổng kết nguyên văn:** `25 passed in 2.37s`
- **Kết quả:** Mã thoát 0, dòng tổng kết có 'passed' và không có 'failed' hay 'error'.

### Bước 13: So sánh SHA-256 với bản tham chiếu
- **Lệnh:** `python -c "import hashlib, pathlib; want = {'docs/11-roadmap.md': 'a5e9288a1acfbdea2966b2c1a7f76554efe3c48c70a1b4b4df2ee5a591d33a89', 'docs/implementation/mc/plan.md': '2efde57f0a76e26eab0c8c272230c7eb6753c6e09ef7719f68ada46afd7f63b9', 'docs/implementation/mc/data/sources_seed_mc.json': '006e34fee45b100be4dfe5d988f274ff5e22be8c9e7078ee0c3966255b617240', 'docs/implementation/mc/data/sources_extra.json': '86c8fdb84694cea9c547446bae651de3bf432dede16e38519c9674ee1beb6538', 'docs/implementation/mc/data/hook_sources.json': 'a908875af31e708e70cfff96dc1abb7522bcad2080cf188bd1e25488f903f2cc', 'docs/implementation/mc/data/sfx_sources.json': '8937646117ca58e6ced7092604501a1369ce1b9e93029559109317e8683649dc', 'docs/implementation/mc/data/narrative_formulas.md': '76dd7e9baebe3ca094fc39a7b18770e02d0db33a0e2ec38e92e6cacaf14cb46d', 'docs/implementation/mc/data/voice_profile.json': 'd84713a0bb32f96456a415fef112234bd0a410ecea0934d076fb5e7d117db1fb', 'docs/implementation/mc/data/labeled_20.json': 'ad7e9280abef7cf54ad98a17c95974332b6dc5bf1b7ea009670bcea936da348a', 'docs/implementation/mc/data/heatcut.py': '48261d7aad1fd9de8f60dcc86874a2817070dbbfb3e3dee32474a5c255c3e779'}; norm = lambda p: pathlib.Path(p).read_bytes().replace(bytes([13, 10]), bytes([10])); bad = sorted(p for p, h in want.items() if hashlib.sha256(norm(p)).hexdigest() != h); assert not bad, ('khác bản tham chiếu D:/AIAVC_IMGPROTO/ref/mcdoc-roadmap-m8 (so sau khi đổi CRLF thành LF)', bad)"`
- **Mã thoát:** 0
- **Kết quả:** Mã thoát 0: cả 10 tệp trùng sha256 bản tham chiếu.

### Bước 14: Probe nội dung 1 (roadmap)
- **Lệnh:** `python -c "import pathlib; t = pathlib.Path('docs/11-roadmap.md').read_text(encoding='utf-8'); assert '| M8 | Video phong cách tin nóng Mỹ (MC)' in t and '## 28. M8 — Video phong cách tin nóng Mỹ (MC)' in t and 'Delta đã user duyệt 04/11/2026 (M8 — MC)' in t, 'roadmap thiếu M8'"`
- **Mã thoát:** 0
- **Kết quả:** Mã thoát 0: roadmap có dòng M8, mục 28 và ghi chú mục 21.

### Bước 15: Probe nội dung 2 (plan.md)
- **Lệnh:** `python -c "import pathlib, re; t = pathlib.Path('docs/implementation/mc/plan.md').read_text(encoding='utf-8'); ids = re.findall(r'^### (MC-[A-Z0-9-]+): ', t, re.M); assert len(ids) == 31 and len(set(ids)) == 31, ('slice', len(ids)); assert 'MC-PILOT' in ids and 'MC-E2E' in ids and not any(i in ('MC-ROADMAP', 'MCDOC-POLICY', 'MCDOC-ROADMAP-M8') for i in ids), 'heading sai'"`
- **Mã thoát:** 0
- **Kết quả:** Mã thoát 0: đúng 31 heading MC- không trùng, có MC-PILOT và MC-E2E.

### Bước 16: Probe nội dung 3 (data)
- **Lệnh:** `python -c "import json, pathlib; d = pathlib.Path('docs/implementation/mc/data'); seed = json.loads((d / 'sources_seed_mc.json').read_text(encoding='utf-8')); lab = json.loads((d / 'labeled_20.json').read_text(encoding='utf-8')); n = lambda v: len(v) if isinstance(v, list) else len(next(x for x in v.values() if isinstance(x, list))); assert n(seed) == 51 and n(lab) == 20, (n(seed), n(lab)); [json.loads((d / f).read_text(encoding='utf-8')) for f in ['sources_extra.json', 'hook_sources.json', 'sfx_sources.json', 'voice_profile.json']]; assert (d / 'narrative_formulas.md').is_file() and (d / 'heatcut.py').is_file(), 'thiếu tệp data'"`
- **Mã thoát:** 0
- **Kết quả:** Mã thoát 0: seed 51 mục, labeled 20 mục, 4 tệp JSON còn lại parse được, có narrative_formulas.md và heatcut.py.

### Bước 17: Kiểm tra ký tự CR
- **Lệnh:** `python -c "import pathlib; ps = ['docs/11-roadmap.md', 'docs/implementation/mc/plan.md', 'docs/implementation/mc/data/sources_seed_mc.json', 'docs/implementation/mc/data/sources_extra.json', 'docs/implementation/mc/data/hook_sources.json', 'docs/implementation/mc/data/sfx_sources.json', 'docs/implementation/mc/data/narrative_formulas.md', 'docs/implementation/mc/data/voice_profile.json', 'docs/implementation/mc/data/labeled_20.json', 'docs/implementation/mc/data/heatcut.py']; bad = [p for p in ps if bytes([13]) in pathlib.Path(p).read_bytes()]; assert not bad, ('tệp còn CR', bad)"`
- **Mã thoát:** 0
- **Kết quả:** Mã thoát 0: không tệp nào chứa byte CR.

## Kết quả 3 probe nội dung và các probe xác minh
- **Probe nội dung 1 (roadmap - bước 14):** Mã thoát 0 (roadmap có dòng M8, mục 28 và ghi chú mục 21).
- **Probe nội dung 2 (plan.md - bước 15):** Mã thoát 0 (đúng 31 heading MC- không trùng, có MC-PILOT và MC-E2E).
- **Probe nội dung 3 (data - bước 16):** Mã thoát 0 (seed 51 nguồn, labeled 20 bài, 4 tệp JSON còn lại parse được, có narrative_formulas.md và heatcut.py).
- **Probe SHA-256 (bước 13):** Mã thoát 0 (cả 10 tệp trùng sha256 bản tham chiếu).
- **Probe CR (bước 17):** Mã thoát 0 (toàn bộ LF, không chứa byte CR).

## Mục mở
- **Mã mục mở:** OI-MC-ROADMAP-M8
- **Chi tiết:** Chưa mở M8 trong policy của AI_SETUP (closures.M8, GATE-MC-E2E, IMPL-PLAN-MC), do Control làm sau bàn giao giai đoạn 1 khi Portfolio rảnh. Dữ liệu nghiên cứu là ảnh chụp ngày 04–05/11/2026; nguồn có thể đổi.
