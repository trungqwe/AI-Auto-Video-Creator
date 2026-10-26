# Báo cáo sửa kế hoạch IMPL-PLAN-PROD-WIRING (lần 2)

Ngày thực hiện: 26/10/2026. Task: IMPL-PLAN-PROD-WIRING-FIX2. Milestone: M7.

## Đã sửa

1. Finding F1 phần 1/2:
   - `PW-SCHEMA`: Bổ sung 8 tệp test persistence (`tests/integration/persistence/{a,b,d,e,f,g,i,j}/test_persist_<chữ>_postgres.py`) vào `ownedPaths`; bổ sung lệnh kiểm `python -m pytest tests/integration/persistence -q -p no:cacheprovider` và probe quét mẫu `range(1, 19)` cùng `len(forward) == 18`; cập nhật `acceptance` (requirement 6 nêu chi tiết các vị trí cần sửa sang 19, instrument kiểm toàn bộ persistence xanh, counterexample bắt việc bỏ sót test persistence).
   - `PW-G1`: Bổ sung `tests/integration/adapt/launch/test_adapt_launch_cli.py` vào `ownedPaths` và `testCommands`; requirement (2) nêu rõ epoch ghi `1` ở lần đầu (kể cả lần restore đầu tiên khi chưa có tệp epoch), requirement (5) nêu sửa dòng 548 thành `"1"` và bổ sung assertion `"2"` sau lần restore thứ hai; counterexample và instrument cập nhật kiểm tra epoch `1` rồi `2`.
   - `PW-G5`: Bổ sung `tests/integration/convergence/test_cp6_video_production_flow.py` vào `ownedPaths`; cập nhật `testCommands` chạy thêm `test_cp6_video_production_flow.py` và `test_cp6_workflow_catalog.py`; requirement (4, 5) quy định xử lý khi `payload['jobs']` có sẵn, mở rộng `FakeBatchGateway` đúng các phương thức mới cho `FinalizeBatch` và giữ nguyên mọi assertion cũ.
   - Cùng mẫu F1 đã rà soát và bổ sung ở các slice liên quan:
     - `PW-CAT2`: Bổ sung `tests/integration/convergence/test_cp6_video_production_flow.py` vào `ownedPaths`, bổ sung requirement (5) chỉ sửa assertion đỏ vì waiting, RetryStage hoặc fan-out, giữ nguyên test.
     - `PW-W1`: Bổ sung `tests/integration/adapt/launch/test_adapt_launch_cli.py` vào `ownedPaths` và `testCommands`; requirement (6) bổ sung monkeypatch cho các service mới để `test_worker_stop_waits_for_the_worker_thread_not_a_lost_future` vẫn xanh.
     - `PW-W2`: Bổ sung `tests/integration/adapt/launch/test_adapt_launch_cli.py` vào `ownedPaths` và `testCommands`; requirement (5) chỉ sửa assertion đỏ do nối D, E, F trong `launcher.py`.

2. Finding F1 phần 2/2:
   - `PW-A3`: Bổ sung `tests/integration/convergence/test_cp6_video_production_flow.py` vào `ownedPaths` và `testCommands`; requirement (4) nêu rõ `assert flow.unbound` đổi thành `['dedup', 'enrich_ai', 'index']` do stage `media` đã có `RegisterMediaDiscovery`; `InProcessGateway` xử lý activity mới.
   - `PW-W1`: Bổ sung `PW-D1` vào `dependsOn` (thành `- dependsOn: `PW-A3`, `PW-B1`, `PW-D1`, `PW-I2`, `PW-VERT``) do tiêu chí seed sáu prompt gọi `seed_default_prompts` do `PW-D1` tạo.

3. Finding F2 phần 2/2:
   - `PW-E4`: Cập nhật requirement (2) quy định rõ khoá gốc `sources` của `music_sources.json` chứa đúng hai phần tử (`primary` và `fallback`) với đầy đủ các trường `source_id`, `role`, `url` (https cố định của tệp mẫu), `license` (không chứa NC), `attribution`, `author`, `sha256` (64 ký tự hex đo thật); instrument và lệnh kiểm tra trong `testCommands` assert chặt chẽ `len(s) == 2`, đúng hai role và đầy đủ trường hợp lệ.

4. Đồng bộ `docs/implementation/prod-wiring/plan.md`:
   - DQ-03: Cập nhật quy tắc epoch ghi `1` lần đầu, đọc giá trị cũ `rec-...` thành số lớn nhất cộng 1, nêu `PW-G1` sở hữu test launcher.
   - Mục 4: Cập nhật `PW-W1` có `dependsOn` gồm `PW-D1`.
   - Mục 8 (OI-PW-07): Ghi nhận `PW-SCHEMA` sửa 8 test persistence và test cp3.
   - Mục 10: Đổi tiêu đề thành «Các điểm giao với tệp đã có chủ...» và bổ sung ba bullet mô tả chi tiết quyền sở hữu các test đã nghiệm thu (tám test persistence, test launcher CLI, test cp6 video production flow).

## Lệnh đã chạy

1. Bước 18: Kiểm tra khoảng trắng git diff
   - Lệnh: `git diff --check`
   - Mã thoát: 0
   - Kết quả: Không có lỗi khoảng trắng thừa hoặc định dạng dòng.

2. Bước 19: Lệnh kiểm bắt buộc của task (cấu trúc slice, dependencies, từ khoá bắt buộc plan.md, tiếng Việt có dấu)
   - Lệnh: `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/prod-wiring'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall('(?m)^### (PW-[0-9A-Z][0-9A-Z-]*): ', s); assert ids and len(ids) == len(set(ids)) and 'PW-E2E' in ids, ids; assert all(s.count('- ' + k + ':') >= len(ids) for k in ['ownedPaths', 'dependsOn', 'resourceLocks', 'bindingRefs', 'testCommands', 'acceptance', 'coveredIds']), 'each slice needs ownedPaths, dependsOn, resourceLocks, bindingRefs, testCommands, acceptance and coveredIds'; deps = re.findall('(?m)^- dependsOn:(.*)', s); bad = [x for x in deps if re.search('CP7-|M7-MILESTONE-CLOSE|GATE-|RS-13|CP-4B-UI-SCREENS-FIX4', x)]; assert not bad, ('forbidden dependency', bad); e = s.split('### PW-E2E: ', 1)[1].split(chr(10) + '### ', 1)[0]; ed = re.findall('(?m)^- dependsOn:(.*)', e); assert ed and all(i in ed[0] for i in ids if i != 'PW-E2E'), 'PW-E2E must depend on every other PW slice'; miss = [k for k in ['AppSession','cp_stage_runs','grant','outbox','ValidateVariant','ReserveVariant','waiting','media_select','ConfigRevision','Kokoro','inspector','PersistVideoOutput','credential_unavailable','PlanCollectionCycle','RegisterMediaDiscovery','launcher','Temporal','PW-E2E','OI-ADAPT-10','FR-AUD-007'] if k not in p]; assert not miss, ('plan.md must cover', miss); assert re.search('[Ạ-ỹ]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"`
   - Mã thoát: 0
   - Kết quả: Đạt toàn bộ ràng buộc cấu trúc slice, 33 slice hợp lệ, PW-E2E phụ thuộc mọi slice khác, không có phụ thuộc cấm, đủ mọi từ khoá bắt buộc trong plan.md, không có ký tự lỗi replacement.

3. Bước 20: Probe kiểm tra slices.md đã có đủ tệp sở hữu, lệnh kiểm và dependsOn mới
   - Lệnh: `python -c "import pathlib, re; s = pathlib.Path('docs/implementation/prod-wiring/slices.md').read_text(encoding='utf-8'); sec = lambda i: s.split('### ' + i + ': ', 1)[1].split(chr(10) + '### ', 1)[0]; cli = 'tests/integration/adapt/launch/test_adapt_launch_cli.py'; cp6 = 'tests/integration/convergence/test_cp6_video_production_flow.py'; assert all('tests/integration/persistence/' + k + '/test_persist_' + k + '_postgres.py' in sec('PW-SCHEMA') for k in 'abdefgij'), 'schema owned'; assert 'tests/integration/persistence -q' in sec('PW-SCHEMA'), 'schema cmd'; assert all(cli in sec(i) for i in ['PW-G1', 'PW-W1', 'PW-W2']), 'cli'; assert all(cp6 in sec(i) for i in ['PW-CAT1', 'PW-CAT2', 'PW-G5', 'PW-A3']), 'cp6'; assert 'PW-D1' in re.search('(?m)^- dependsOn:(.*)', sec('PW-W1')).group(1), 'W1 dep'; assert 'len(s) == 2' in sec('PW-E4'), 'E4'"`
   - Mã thoát: 0
   - Kết quả: PW-SCHEMA sở hữu 8 tệp persistence và lệnh pytest persistence; PW-G1, PW-W1, PW-W2 sở hữu test launcher; PW-CAT1, PW-CAT2, PW-G5, PW-A3 sở hữu test cp6 flow; PW-W1 phụ thuộc PW-D1; PW-E4 kiểm tra đúng 2 nguồn nhạc.

4. Bước 21: Probe kiểm tra plan.md đồng bộ với slices.md
   - Lệnh: `python -c "import pathlib; p = pathlib.Path('docs/implementation/prod-wiring/plan.md').read_text(encoding='utf-8'); assert 'test_adapt_launch_cli.py' in p and 'test_cp6_video_production_flow.py' in p and 'seed_default_prompts' in p and 'test_persist_' in p, 'plan F1'"`
   - Mã thoát: 0
   - Kết quả: plan.md phản ánh đầy đủ các tệp test launcher CLI, test cp6 flow, seed_default_prompts và test persistence theo đúng finding F1.

5. Bước 23: Kiểm tra khoảng trắng git diff sau khi tạo báo cáo
   - Lệnh: `git diff --check`
   - Mã thoát: 0
   - Kết quả: Toàn bộ thay đổi và tệp báo cáo sạch khoảng trắng thừa.

## Chưa kiểm

Không chạy pytest hay full suite kiểm thử mã nguồn vì tác vụ IMPL-PLAN-PROD-WIRING-FIX2 chỉ thuộc phạm vi sửa đổi tài liệu kế hoạch (owned paths). Các test đã nghiệm thu khác ngoài mẫu finding F1 chưa được rà soát trong đợt này.
