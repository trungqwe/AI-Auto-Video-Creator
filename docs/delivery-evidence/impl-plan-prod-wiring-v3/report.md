# Báo cáo sửa kế hoạch IMPL-PLAN-PROD-WIRING (lần 3, PW-CAT1)

Ngày thực hiện: 26/10/2026. Task: IMPL-PLAN-PROD-WIRING-V3. Milestone: M7.

## Finding đã xử lý

1. F1 (MAJOR, Auditor rủi ro, job impl-prod-wiring-r2-1792979693565 phần 1/3): acceptance PW-CAT1 trước đây tự mâu thuẫn vì `ValidateVariant` phải có ở cả stage `plan` và `qc` nhưng binding chỉ có một `stage_type`, còn test `test_bindings_follow_the_catalog` so chặt `binding.stage_type == stage_name`; đã xử lý bằng trường `extra_stage_types: tuple[str, ...] = ()` của `ActivityBinding`, `ValidateVariant` có `stage_type` = `plan` và `extra_stage_types` = `('qc',)`.
2. V3-F1 (MAJOR): mệnh đề hàng đợi theo `route_stage` ở `qc` không thực hiện được trong ownedPaths vì `definitions.py:84`, `flow.py:277` và `workflow.py:235` đọc `binding.queue`; đã thay bằng: hàng đợi của `ValidateVariant` ở cả hai stage là `binding.queue` = `route_stage('plan')`, không đổi theo stage.

## Dòng đã sửa của slices.md

Mục PW-CAT1 (dòng 171-173): requirement (2) (câu `GenerateOutputMetadata` chuyển sang `plan`, `ValidateVariant` chạy hai stage, nguồn hàng đợi), requirement (5) (ngoại lệ đóng của `test_bindings_follow_the_catalog`), instrument, counterexample; ownedPaths, dependsOn, resourceLocks, bindingRefs, testCommands, coveredIds của PW-CAT1 và mọi mục khác của slices.md, plan.md không đổi.

### Dòng test đã nghiệm thu được phép đổi

Dòng `assert binding.stage_type == stage_name` (dòng 158 của `tests/integration/convergence/test_cp6_workflow_catalog.py`, hàm `test_bindings_follow_the_catalog`) sẽ được đổi ở slice PW-CAT1 (không phải ở task này) thành `assert stage_name in (binding.stage_type, *binding.extra_stage_types)` kèm hai assertion chặt; lý do: `ValidateVariant` là activity duy nhất chạy ở hai stage, ngoại lệ đóng, không nới oracle.

## Lệnh đã chạy

1. Bước 5: Kiểm tra khoảng trắng git diff sau khi sửa slices.md
   - Lệnh:
```bash
git diff --check
```
   - Mã thoát: 0
   - Kết quả: Đạt, không có lỗi khoảng trắng thừa.

2. Bước 6: Kiểm tra cấu trúc kế hoạch PW, từ khoá plan.md và tiếng Việt có dấu (probe cấu trúc xác nhận 32 slice)
   - Lệnh:
```bash
python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/prod-wiring'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall('(?m)^### (PW-[0-9A-Z][0-9A-Z-]*): ', s); assert ids and len(ids) == len(set(ids)) and 'PW-E2E' in ids, ids; assert all(s.count('- ' + k + ':') >= len(ids) for k in ['ownedPaths', 'dependsOn', 'resourceLocks', 'bindingRefs', 'testCommands', 'acceptance', 'coveredIds']), 'each slice needs ownedPaths, dependsOn, resourceLocks, bindingRefs, testCommands, acceptance and coveredIds'; deps = re.findall('(?m)^- dependsOn:(.*)', s); bad = [x for x in deps if re.search('CP7-|M7-MILESTONE-CLOSE|GATE-|RS-13|CP-4B-UI-SCREENS-FIX4', x)]; assert not bad, ('forbidden dependency', bad); e = s.split('### PW-E2E: ', 1)[1].split(chr(10) + '### ', 1)[0]; ed = re.findall('(?m)^- dependsOn:(.*)', e); assert ed and all(i in ed[0] for i in ids if i != 'PW-E2E'), 'PW-E2E must depend on every other PW slice'; miss = [k for k in ['AppSession','cp_stage_runs','grant','outbox','ValidateVariant','ReserveVariant','waiting','media_select','ConfigRevision','Kokoro','inspector','PersistVideoOutput','credential_unavailable','PlanCollectionCycle','RegisterMediaDiscovery','launcher','Temporal','PW-E2E','OI-ADAPT-10','FR-AUD-007'] if k not in p]; assert not miss, ('plan.md must cover', miss); assert re.search('[Ạ-ỹ]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"
```
   - Mã thoát: 0
   - Kết quả: Đạt toàn bộ ràng buộc kế hoạch, xác nhận đúng 32 slice, từ khoá và tiếng Việt có dấu.

3. Bước 7: Probe riêng cho PW-CAT1 trước khi viết lại report
   - Lệnh:
```bash
python -c "import pathlib, re, unicodedata; s = unicodedata.normalize('NFC', pathlib.Path('docs/implementation/prod-wiring/slices.md').read_text(encoding='utf-8')); c = s.split('### PW-CAT1: ', 1)[1].split(chr(10) + '### ', 1)[0]; q = chr(39); assert 'extra_stage_types' in c and 'test_bindings_follow_the_catalog' in c, 'PW-CAT1 model'; assert 'route_stage(' + q + 'qc' + q + ')' not in c, 'qc queue clause still present'; assert 'route_stage(' + q + 'plan' + q + ')' in c and 'definitions.py:84' in c and 'flow.py:277' in c and 'workflow.py:235' in c, 'queue source not stated'; assert not re.search('ValidateVariant.{1,8}GenerateOutputMetadata', c), 'PW-CAT1 contradiction'; assert 'test_pw_cat1_catalog.py -q -p no:cacheprovider' in c and 'coveredIds: PW-CAT1-01..05, CT-WF-009, CT-ORC-012, CT-AI-008' in c, 'PW-CAT1 testCommands or coveredIds changed'; assert len(re.findall('(?m)^### (PW-[0-9A-Z][0-9A-Z-]*): ', s)) == 32, 'slice count'"
```
   - Mã thoát: 0
   - Kết quả: Đạt, kiểm tra mô hình PW-CAT1, không còn mệnh đề hàng đợi qc, nguồn hàng đợi đầy đủ, không còn mâu thuẫn, giữ nguyên 32 slice.

## Kết quả kiểm sau khi ghi report

1. Bước 9: Kiểm tra PW-CAT1 và tệp report.md
   - Lệnh:
```bash
python -c "import pathlib, re, unicodedata; s = unicodedata.normalize('NFC', pathlib.Path('docs/implementation/prod-wiring/slices.md').read_text(encoding='utf-8')); c = s.split('### PW-CAT1: ', 1)[1].split(chr(10) + '### ', 1)[0]; assert 'extra_stage_types' in c and 'test_bindings_follow_the_catalog' in c and 'route_stage' in c, 'PW-CAT1 model'; assert not re.search('ValidateVariant.{1,8}GenerateOutputMetadata', c), 'PW-CAT1 contradiction'; r = pathlib.Path('docs/delivery-evidence/impl-plan-prod-wiring-v3/report.md').read_text(encoding='utf-8'); assert 'PW-CAT1' in r and 'F1' in r, 'report'"
```
   - Mã thoát: 0
   - Kết quả: Đạt, report.md chứa PW-CAT1 và F1, mô hình PW-CAT1 hợp lệ.

2. Bước 10: Probe targetDirective kiểm tra mô hình PW-CAT1, nguồn hàng đợi và nội dung report.md
   - Lệnh:
```bash
python -c "import pathlib, re, unicodedata; s = unicodedata.normalize('NFC', pathlib.Path('docs/implementation/prod-wiring/slices.md').read_text(encoding='utf-8')); c = s.split('### PW-CAT1: ', 1)[1].split(chr(10) + '### ', 1)[0]; q = chr(39); assert 'extra_stage_types' in c and 'test_bindings_follow_the_catalog' in c, 'PW-CAT1 model'; assert 'route_stage(' + q + 'qc' + q + ')' not in c, 'qc queue clause still present'; assert 'route_stage(' + q + 'plan' + q + ')' in c and 'definitions.py:84' in c and 'flow.py:277' in c and 'workflow.py:235' in c, 'queue source not stated'; assert not re.search('ValidateVariant.{1,8}GenerateOutputMetadata', c), 'PW-CAT1 contradiction'; r = unicodedata.normalize('NFC', pathlib.Path('docs/delivery-evidence/impl-plan-prod-wiring-v3/report.md').read_text(encoding='utf-8')); assert 'V3-F1' in r and 'PW-CAT1' in r and 'F1' in r, 'report'; assert 'mâu thu' + 'ấn' not in r and '33' + ' slice' not in r and chr(65533) not in r, 'report typo or wrong count'; assert re.search('[Ạ-ỹ]', r), 'report lost diacritics'"
```
   - Mã thoát: 0
   - Kết quả: Đạt, không còn mệnh đề hàng đợi qc, nguồn hàng đợi definitions.py:84, flow.py:277, workflow.py:235 đầy đủ, report.md đạt toàn bộ điều kiện kiểm tra.

3. Bước 12: Kiểm tra lại khoảng trắng git diff lần cuối
   - Lệnh:
```bash
git diff --check
```
   - Mã thoát: 0
   - Kết quả: Đạt, không có lỗi khoảng trắng thừa.

## Chưa kiểm

Không chạy pytest vì task chỉ sửa tài liệu kế hoạch, test thật của PW-CAT1 chạy ở slice PW-CAT1.
