# Báo cáo CP7-REAL-RESOURCES (kế hoạch)

- **Mã gói**: CP7-REAL-RESOURCES (planning_package)
- **Ngày lập**: 25/10/2026
- **Cơ sở**: HEAD 9cb0d0a1fbe7e9e6362af86c479d685d1b9547d
- **Nguồn quyền**: Ủy quyền AI_SETUP (AI_PM_DELEGATED_AUTHORITY_RULES.md), chỉ thị user duyệt Phần B ngày 18/10/2026, quyết định user 20/10/2026 và quyết định D5 ngày 22/10/2026. PRODUCTION_ACTIVATION_BLOCKED giữ nguyên tới nghiệm thu cuối; không push, không merge.

## Môi trường

- **Hệ điều hành**: Windows 11
- **Interpreter khoá**: C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe (Python 3.13.15)
- **HEAD commit**: 9cb0d0a1fbe7e9e6362af86c479d685d1b9547d
- **Ngày**: 25/10/2026

## Tệp đã tạo

- docs/implementation/cp7/plan.md: Kế hoạch kiểm trên tài nguyên thật và user nghiệm thu, gồm 13 gate tài nguyên thật (RG-01 đến RG-13) và 6 gate user nghiệm thu (R1 đến R6).
- docs/implementation/cp7/slices.md: Danh mục 14 work package slice (CP7-1 đến CP7-14) kiểm trên tài nguyên thật, chỉ thêm 	ests/real/**, 	ools/real/** và báo cáo bằng chứng; mỗi slice đều có LOCK-CP7, Trần chi phí, Cách dừng, ownedPaths và 	estCommands hợp lệ.
- docs/delivery-evidence/cp7-real-resources/report.md: Báo cáo bằng chứng của gói lập kế hoạch.

## Lệnh kiểm và kết quả

| Bước | Lệnh | Exit code | Kết quả |
| --- | --- | --- | --- |
| 29 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/cp7'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (CP7-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, testCommands and acceptance'; assert re.search('[Ạ-ỹ]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'" | 0 | PASS (14 slice định danh duy nhất, đủ 4 trường bắt buộc, tiếng Việt NFC đầy đủ dấu, không ký tự thay thế) |
| 30 | git diff --check | 0 | PASS (không có lỗi khoảng trắng cuối dòng hoặc xung đột) |
| 31 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/cp7'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); need = ['M3-EG7', 'M3-REAL', 'M4-EG5', 'M4-EG6', 'M5-EG7', 'M5-REAL', 'M6-EG1', 'M6-EG5', 'M6-EG6', 'M7-R5-EG1', 'M7-R6', 'M2-USER-CHECKPOINT-P8-P9', 'USER-CKPT-D9-D10', 'test_h36_m1_regression', 'safe-error-modal.spec.ts', 'OI-ADAPT-10', 'ROADMAP-OPEN-009', 't\xe0i nguy\xean', 'nghiệm thu'] + ['RG-' + format(i, '02d') for i in range(1, 14)] + ['R' + str(i) + ' ' for i in range(1, 7)]; miss = [k for k in need if k not in p]; assert not miss, miss; ids = re.findall(r'(?m)^### (CP7-[0-9A-Z][0-9A-Z-]*)', s); assert ids == ['CP7-' + str(i) for i in range(1, 15)], ids; q = chr(96); item = q + '([^' + q + ']+)' + q; blocks = re.split(r'(?m)^### CP7-', s)[1:]; ok = r'tests/real/\S+|tools/real/\S+|docs/delivery-evidence/cp7-[0-9]+/report[.]md'; bad = [i for i, b in enumerate(blocks, 1) if 'kind: work_package_slice' not in b or 'LOCK-CP7' not in b or 'Trần chi ph\xed' not in b or 'C\xe1ch dừng' not in b]; assert not bad, bad; own = [re.search(r'ownedPaths:[ ]*\r?\n((?:[ ]+- ' + item + r'[ ]*\r?\n)+)', b) for b in blocks]; assert all(own), 'ownedPaths list'; wrong = [x for m in own for x in re.findall(item, m.group(1)) if not re.fullmatch(ok, x)]; assert not wrong, wrong; cmd = [re.search(r'testCommands:[ ]*\r?\n((?:[ ]+- ' + item + r'[ ]*\r?\n?)+)', b) for b in blocks]; assert all(cmd), 'testCommands list'; badc = [x for m in cmd for x in re.findall(item, m.group(1)) if not re.match(r'git diff --check|python -m pytest tests/real/|python -c |node --check tools/real/', x)]; assert not badc, badc; assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN|ya29[.]', p + s), 'secret pattern'" | 0 | PASS (11 mã chờ, 13 gate RG, 6 gate user R1–R6, 14 slice CP7-1..CP7-14 đúng định dạng, ownedPaths và testCommands hợp lệ, không chứa secret pattern) |

## Đối chiếu pendingUserCheckpoint

Đối chiếu đầy đủ 11 mã chờ từ năm báo cáo đóng milestone M3–M7 sang các gate kế hoạch theo docs/implementation/cp7/plan.md mục 3:

| Lane đóng | Mã chờ | Nội dung | Loại | Gate kế hoạch |
| --- | --- | --- | --- | --- |
| M3-MILESTONE-CLOSE | M3-EG7 | User duyệt phân hệ A-B và R1 Content Alpha | user | R1 |
| M3-MILESTONE-CLOSE | M3-REAL | RSS/web thật; scheduler cloud khi desktop offline | tài nguyên thật | RG-04, R1, OI-CP7-03 |
| M4-MILESTONE-CLOSE | M4-EG5 | Drive/OAuth/integrity phần M4 của G04 trên tài khoản thật | tài nguyên thật | RG-02 |
| M4-MILESTONE-CLOSE | M4-EG6 | User duyệt C-I và R2 Media Alpha | user | R2 |
| M5-MILESTONE-CLOSE-R2 | M5-EG7 | User duyệt D và R3 Creative Alpha | user | R3 |
| M5-MILESTONE-CLOSE-R2 | M5-REAL | AI trả phí thật; mẫu user chấm topic ≥ 90%, event-link ≥ 95%, media/hook ≥ 90%; holdout khóa | tài nguyên và user | RG-03, RG-04, R3 |
| M6-MILESTONE-CLOSE-R2 | M6-EG1 | R4 Video Alpha theo luồng giám sát từ snapshot đến completion | tài nguyên thật | RG-09 |
| M6-MILESTONE-CLOSE-R2 | M6-EG5 | G06 phần TTS/timing/media và G07 phần output/QC có evidence | tài nguyên thật | RG-05, RG-06, RG-07 |
| M6-MILESTONE-CLOSE-R2 | M6-EG6 | User duyệt E-F và 5 preset; nghe mẫu, duyệt hình | user | R4 |
| M7-MILESTONE-CLOSE | M7-R5-EG1 | Batch không giám sát trên workload đại diện với nhà cung cấp thật | tài nguyên thật | RG-10, R5 |
| M7-MILESTONE-CLOSE | M7-R6 | R6 Operational Baseline (G01–G07, 100 video/12 giờ, ≥ 95%, hiệu năng, chất lượng, chi phí, runbook, nghiệm thu) | tài nguyên và user | RG-10 đến RG-13, R6 |

Các mục chờ liên quan ngoài năm báo cáo đóng:
- M2-USER-CHECKPOINT-P8-P9: Gộp vào nghiệm thu cuối R6 kèm ngoại lệ safe-error-modal.spec.ts của CP-2C.
- USER-CKPT-D9-D10: Thư viện và cách dựng lại runtime; CP7 không tự đóng, nhắc ở R6.
- 	est_h36_m1_regression: Hoãn sang CP7 (U6) -> RG-08, OI-CP7-05.
- OI-ADAPT-10 -> R2; ROADMAP-OPEN-009 -> R4; ROADMAP-OPEN-006, ROADMAP-OPEN-007, ROADMAP-OPEN-008 -> RG-06, RG-07, RG-05.
- CP7-ADAPT-01..11: Phân bổ tương ứng sang các gate RG-01..RG-13.

## GIẢ ĐỊNH và giới hạn

1. **Bản chất tài liệu kế hoạch**: Đây là kế hoạch kiểm thử và nghiệm thu, chưa trực tiếp chạy tài nguyên thật hay kích hoạt sản xuất.
2. **Các slice thực thi**: Các tệp mã kiểm thử và công cụ đo trong 	ests/real/** và 	ools/real/** chưa tồn tại trong lane này; chúng sẽ được tạo khi Control mở từng slice tương ứng của CP7.
3. **An toàn bí mật**: Không đọc thư mục Credentials/, không đọc, sao chép hoặc in bất kỳ token, khóa bí mật hay mật khẩu nào. Bí mật chỉ được truy cập qua secret broker của phân hệ J khi các slice CP7 thực thi.
4. **Mục mở và quyết định**: Toàn bộ 11 mục mở OI-CP7-01 đến OI-CP7-11 được ghi nhận tại docs/implementation/cp7/plan.md mục 8. Không có mục nào được ghi là user đã duyệt khi chưa có xác nhận chính thức từ user.
5. **Không chứa bí mật**: Báo cáo này không chứa bất kỳ secret, token hoặc capability nào.
