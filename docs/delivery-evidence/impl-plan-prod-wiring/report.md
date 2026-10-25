# Báo cáo bằng chứng IMPL-PLAN-PROD-WIRING

Ngày thực hiện: 26/10/2026. Task: IMPL-PLAN-PROD-WIRING.

## Lệnh đã chạy

1. `git diff --check`
   - Mã thoát: 0
   - Kết quả: Không có lỗi khoảng trắng cuối dòng hoặc xung đột git.

2. `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/prod-wiring'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall('(?m)^### (PW-[0-9A-Z][0-9A-Z-]*): ', s); assert ids and len(ids) == len(set(ids)) and 'PW-E2E' in ids, ids; assert all(s.count('- ' + k + ':') >= len(ids) for k in ['ownedPaths', 'dependsOn', 'resourceLocks', 'bindingRefs', 'testCommands', 'acceptance', 'coveredIds']), 'each slice needs ownedPaths, dependsOn, resourceLocks, bindingRefs, testCommands, acceptance and coveredIds'; deps = re.findall('(?m)^- dependsOn:(.*)', s); bad = [x for x in deps if re.search('CP7-|M7-MILESTONE-CLOSE|GATE-|RS-13|CP-4B-UI-SCREENS-FIX4', x)]; assert not bad, ('forbidden dependency', bad); e = s.split('### PW-E2E: ', 1)[1].split(chr(10) + '### ', 1)[0]; ed = re.findall('(?m)^- dependsOn:(.*)', e); assert ed and all(i in ed[0] for i in ids if i != 'PW-E2E'), 'PW-E2E must depend on every other PW slice'; miss = [k for k in ['AppSession','cp_stage_runs','grant','outbox','ValidateVariant','ReserveVariant','waiting','media_select','ConfigRevision','Kokoro','inspector','PersistVideoOutput','credential_unavailable','PlanCollectionCycle','RegisterMediaDiscovery','launcher','Temporal','PW-E2E','OI-ADAPT-10','FR-AUD-007'] if k not in p]; assert not miss, ('plan.md must cover', miss); assert re.search('[Ạ-ỹ]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"`
   - Mã thoát: 0
   - Kết quả: Toàn bộ kiểm tra cấu trúc đạt: 32 slice ID duy nhất, đủ 7 trường bắt buộc mỗi slice, không phụ thuộc cấm, PW-E2E phụ thuộc đủ 31 slice còn lại trên một dòng, plan.md đủ từ khoá bắt buộc, tiếng Việt đủ dấu và 0 ký tự thay thế U+FFFD.

## Kết quả

- Số slice trong `slices.md`: 32 slice (PW-H0, PW-SCHEMA, PW-G1..PW-G4, PW-CAT1, PW-CAT2, PW-G5..PW-G7, PW-VERT, PW-D1..PW-D3, PW-E1..PW-E4, PW-F1..PW-F4, PW-I1, PW-I2, PW-A1..PW-A3, PW-B1, PW-W1, PW-W2, PW-E2E); năm slice chạm composition root hoặc migration (`PW-SCHEMA`, `PW-G1`, `PW-G3`, `PW-W1`, `PW-W2`) là `convergence_slice`, hai mươi bảy slice còn lại là `work_package_slice` (đã sửa ở vòng REVIEW_FINDINGS, finding F1).
- Xác nhận `PW-E2E` phụ thuộc đủ 31 slice còn lại trên đúng một dòng `dependsOn`, không chứa bất kỳ phụ thuộc cấm nào (CP7-*, M7-MILESTONE-CLOSE*, GATE-*, RS-13, CP-4B-UI-SCREENS-FIX4).
- Xác nhận hai mục CHƯA XÁC NHẬN đã được kiểm bằng mã và ghi ở `plan.md` mục 2: RetryStage (inventory mục 2, XÁC NHẬN LỖI tại `src/controlplane/application/orchestration/workflows/flow.py:189-196`, `:247-253`, `:153-164`) và observed_hash, observed_size_bytes (inventory mục 5, XÁC NHẬN THIẾU tại `0005_artifact_metadata.sql:38-39`, `storage_meta/__init__.py:76-81`, `:90-92`, `materialization.py:109`).

## Vòng REVIEW_FINDINGS (F1, F2)

- Danh sách thay đổi:
  - F1: đổi kind của năm slice (`PW-SCHEMA`, `PW-G1`, `PW-G3`, `PW-W1`, `PW-W2`) từ `work_package_slice` sang `convergence_slice`; bổ sung bullet loại slice ở Quy tắc chung của `slices.md` cùng đoạn ở `plan.md` mục 5.
  - F2: thêm bullet tránh xung đột `ADAPT-PROD-FIX3` ở Quy tắc chung, mục (4) và lệnh kiểm mới ở `PW-W2`, mục 10 «Gói sửa của chủ sở hữu» ở `plan.md`.
  - MINOR: mục Gói sửa của chủ sở hữu (mục 10 của `plan.md`).

- Bảng lệnh đã chạy ở bước 12-15:
  1. `git diff --check`
     - Mã thoát: 0
     - Kết quả: Mã thoát 0, không có lỗi khoảng trắng cuối dòng hoặc xung đột git.
  2. `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/prod-wiring'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall('(?m)^### (PW-[0-9A-Z][0-9A-Z-]*): ', s); assert ids and len(ids) == len(set(ids)) and 'PW-E2E' in ids, ids; assert all(s.count('- ' + k + ':') >= len(ids) for k in ['ownedPaths', 'dependsOn', 'resourceLocks', 'bindingRefs', 'testCommands', 'acceptance', 'coveredIds']), 'each slice needs ownedPaths, dependsOn, resourceLocks, bindingRefs, testCommands, acceptance and coveredIds'; deps = re.findall('(?m)^- dependsOn:(.*)', s); bad = [x for x in deps if re.search('CP7-|M7-MILESTONE-CLOSE|GATE-|RS-13|CP-4B-UI-SCREENS-FIX4', x)]; assert not bad, ('forbidden dependency', bad); e = s.split('### PW-E2E: ', 1)[1].split(chr(10) + '### ', 1)[0]; ed = re.findall('(?m)^- dependsOn:(.*)', e); assert ed and all(i in ed[0] for i in ids if i != 'PW-E2E'), 'PW-E2E must depend on every other PW slice'; miss = [k for k in ['AppSession','cp_stage_runs','grant','outbox','ValidateVariant','ReserveVariant','waiting','media_select','ConfigRevision','Kokoro','inspector','PersistVideoOutput','credential_unavailable','PlanCollectionCycle','RegisterMediaDiscovery','launcher','Temporal','PW-E2E','OI-ADAPT-10','FR-AUD-007'] if k not in p]; assert not miss, ('plan.md must cover', miss); assert re.search('[\u1ea0-\u1ef9]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"`
     - Mã thoát: 0
     - Kết quả: Mã thoát 0, kiểm tra toàn bộ 32 slice đạt, đủ 7 trường bắt buộc, không phụ thuộc cấm, PW-E2E phụ thuộc đủ 31 slice, plan.md đủ từ khoá, tiếng Việt đủ dấu.
  3. `python -c "import pathlib, re; s = pathlib.Path('docs/implementation/prod-wiring/slices.md').read_text(encoding='utf-8'); parts = s.split(chr(10) + '### ')[1:]; assert len(parts) == 32, len(parts); bad = [x.split(':')[0] for x in parts if re.search('api/wiring/|launcher[.]py|/migrations/', x.split('- ownedPaths:')[1].split('- dependsOn:')[0]) and '- kind: convergence_slice' not in x]; assert not bad, bad; assert s.count('- kind: convergence_slice') == 5 and s.count('- kind: work_package_slice') == 27, 'kind counts'"`
     - Mã thoát: 0
     - Kết quả: Mã thoát 0, danh sách bad rỗng; đúng 5 convergence_slice (PW-SCHEMA, PW-G1, PW-G3, PW-W1, PW-W2) và 27 work_package_slice.
  4. `python -c "import pathlib, re; s = pathlib.Path('docs/implementation/prod-wiring/slices.md').read_text(encoding='utf-8'); p = pathlib.Path('docs/implementation/prod-wiring/plan.md').read_text(encoding='utf-8'); w = s.split('### PW-W2: ', 1)[1].split(chr(10) + '### ', 1)[0]; assert 'ADAPT-PROD-FIX3' in s.split('### PW-H0: ', 1)[0] and 'ADAPT-PROD-FIX3' in w and 'test_adapt_prod_app.py' in w and 'ADAPT-PROD-FIX3' in p and re.search('## 10[.] G', p), 'F2'"`
     - Mã thoát: 0
     - Kết quả: Mã thoát 0, xác nhận ADAPT-PROD-FIX3 có mặt ở quy tắc chung, PW-W2 và plan.md; PW-W2 có test_adapt_prod_app.py; plan.md có mục 10.

## Mục mở

- OI-PW-01: OI-CP7-03 (bỏ scheduler cloud theo U1) vẫn chờ user ghi nhận ở R1; không chặn kế hoạch.
- OI-PW-02: vòng lô chạy video tuần tự. 100 video trong 12 giờ cần trung bình tối đa 7,2 phút mỗi video. `PW-E2E` ghi số đo thời gian từng stage; nếu vượt thì Control lập slice chạy song song hai video theo 2 khe GPU.
- OI-PW-03: quyết định OI-ADAPT-10 làm hết hiệu lực mặc định UNVERIFIED ở `docs/implementation/adapt/plan.md:274,321` và mục `rights_unverified_excluded` của CP7-14; Control sửa các chỗ đó trước khi chạy CP7-14.
- OI-PW-04: nếu muốn khoá route riêng cho `production_plan` thì Control thêm khoá `plan` vào `ai.route_model_refs` (`tools/launcher/prod/profile.json:122-130`) bằng slice riêng.
- OI-PW-05: TTL grant theo hàng đợi dùng giá trị mặc định do `PW-G3` ghi; Control đưa vào profile nếu muốn chỉnh.
- OI-PW-06: nguồn nhạc nền do `PW-E4` khảo sát và chọn; cách hiểu lời user "giai đoạn đầu tự tìm nguồn sinh nhạc nền" (hệ thống tự tìm và thu thập nhạc, không AI sáng tác) đã báo user và chờ user sửa nếu sai.
- OI-PW-07: `PW-SCHEMA` sửa `tests/integration/convergence/test_cp3_migration_sequence.py` vì số migration đổi từ 18 sang 19; Control xác nhận quyền sửa khi giao slice.
- pendingUserCheckpoint: không có mục mới do kế hoạch này tạo; OI-CP7-03 vẫn chờ.
